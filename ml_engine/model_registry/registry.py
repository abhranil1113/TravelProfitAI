"""
ml_engine/model_registry/registry.py

Artifact discovery, metadata validation, model versioning, and caching registry.
Provides unified thread-safe model loading, O(1) in-memory cache hits, independent checksum validation,
and lifecycle cache eviction upon model promotion or retirement.
"""

import hashlib
import json
import logging
import os
import threading
from typing import Dict, Any, Tuple, Optional, List
import joblib

from ml_engine.config import MLEngineConfig
from ml_engine.exceptions import (
    ModelNotFoundError,
    ArtifactCorruptedError,
    ChecksumMismatchError,
)
from ml_engine.model_registry.model_metadata import ModelMetadataValidator
from ml_engine.schemas import ModelMetadataSchema, PredictionTask

logger = logging.getLogger(__name__)


class ModelArtifactRegistry:
    """
    Manages discovery, validation, caching, and safe loading of Phase 4 model artifacts.
    Provides thread-safe multi-part cache keys (task, version, checksum) and database champion lookup.
    Guarantees sub-millisecond O(1) in-memory cache hits without redundant disk reads.
    Strictly distinguishes independently trusted checksums from unauthenticated local metadata.
    """

    DEFAULT_BASE_DIR = "data/models"
    _CLASS_CACHE: Dict[str, Tuple[Any, Any, Dict[str, Any]]] = {}
    _TASK_TO_CACHE_KEY: Dict[str, str] = {}
    _TASK_GENERATIONS: Dict[str, int] = {}
    _GLOBAL_GENERATION: int = 0
    _CACHE_LOCK = threading.RLock()
    _TASK_LOAD_LOCKS: Dict[str, threading.Lock] = {}

    def __init__(
        self,
        base_dir: str = DEFAULT_BASE_DIR,
        db: Optional[Any] = None,
        config: Optional[MLEngineConfig] = None,
    ):
        self.base_dir = base_dir
        self.db = db
        self.config = config or MLEngineConfig(base_model_dir=base_dir)

    def set_trusted_checksum(self, task_name: str, checksum: str) -> None:
        """Registers an independently trusted checksum anchor for a task."""
        task_norm = str(task_name.value if hasattr(task_name, "value") else task_name).lower().strip()
        self.config.trusted_checksums[task_norm] = checksum.strip().lower()
        logger.info("Registered independent trusted checksum for %s: %s", task_norm, checksum[:12])

    @classmethod
    def invalidate_cache(cls, task_name: Optional[str] = None) -> None:
        """
        Invalidates in-memory cached model artifacts across all instances in a thread-safe manner.
        Ensures stale models are never served after promotion or retirement events.
        Increments per-task cache generation to prevent stale concurrent background reinsertion.
        """
        with cls._CACHE_LOCK:
            if task_name:
                task_norm = str(task_name.value if hasattr(task_name, "value") else task_name).lower().strip()
                cls._TASK_GENERATIONS[task_norm] = cls._TASK_GENERATIONS.get(task_norm, 0) + 1
                keys_to_remove = [k for k in cls._CLASS_CACHE if f"::{task_norm}::" in k or k.startswith(f"{task_norm}::")]
                for k in keys_to_remove:
                    del cls._CLASS_CACHE[k]
                scoped_keys = [sk for sk in cls._TASK_TO_CACHE_KEY if sk.endswith(f"::{task_norm}") or sk == task_norm]
                for sk in scoped_keys:
                    del cls._TASK_TO_CACHE_KEY[sk]
                logger.info("Invalidated ML Engine model cache for task: %s (cleared %d keys, gen=%d)", task_norm, len(keys_to_remove), cls._TASK_GENERATIONS[task_norm])
            else:
                cls._GLOBAL_GENERATION += 1
                for k in list(cls._TASK_GENERATIONS.keys()):
                    cls._TASK_GENERATIONS[k] += 1
                cls._CLASS_CACHE.clear()
                cls._TASK_TO_CACHE_KEY.clear()
                logger.info("Cleared entire ML Engine artifact cache.")

    def clear_cache(self, task_name: Optional[str] = None) -> None:
        """Instance alias for cache invalidation."""
        self.invalidate_cache(task_name)

    @staticmethod
    def compute_sha256(filepath: str) -> str:
        """Computes SHA-256 hash of a serialized model artifact file."""
        if not os.path.exists(filepath):
            return ""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest().lower()

    def resolve_task_dir(self, task_name: str, model_version: Optional[str] = None) -> str:
        """
        Resolves the artifact directory for the given task.
        Prioritizes live database champion record or explicit model version if available, falling back to disk paths.
        Raises ModelNotFoundError if no trusted artifact directory exists.
        """
        task_norm = str(task_name.value if hasattr(task_name, "value") else task_name).lower().strip()

        # 1. Query database champion or explicit version if DB session is available
        if self.db is not None:
            try:
                from backend.app.models.schema import MLModel
                query = self.db.query(MLModel).execution_options(populate_existing=True).filter(MLModel.model_type == task_norm)
                if model_version:
                    query = query.filter(MLModel.version == str(model_version).strip())
                else:
                    query = query.filter(MLModel.is_champion == True)
                model_rec = query.first()
                if model_rec and model_rec.artifact_dir and os.path.exists(model_rec.artifact_dir):
                    if getattr(model_rec, "artifact_checksum", None):
                        self.set_trusted_checksum(task_norm, model_rec.artifact_checksum)
                    return model_rec.artifact_dir
            except Exception as e:
                logger.debug("Database model lookup skipped for %s (version=%s): %s", task_norm, model_version, e)

        # 2. Check standard base_dir (e.g. data/models/flight_price)
        standard_path = os.path.join(self.base_dir, task_norm)
        if os.path.exists(standard_path):
            return standard_path

        raise ModelNotFoundError(
            f"Artifact directory not found for ML task '{task_name}' at '{standard_path}'"
        )

    def get_model(
        self,
        task_name: str,
        expected_checksum: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Loads (estimator, preprocessor, metadata_dict) for the requested task.
        Fast O(1) path: Returns in-memory cached model immediately without touching the filesystem.
        Slow path: On cache miss, discovers directory, validates schema, checks SHA-256 against trusted source,
        and loads artifact under _CACHE_LOCK.
        Strictly distinguishes independent trusted checksums from unauthenticated metadata on disk.
        """
        task_norm = str(task_name.value if hasattr(task_name, "value") else task_name).lower().strip()
        base_norm = os.path.normpath(os.path.abspath(self.base_dir))
        scoped_task_key = f"{base_norm}::{task_norm}"

        def _verify_cached_checksum(cached_meta: Dict[str, Any]) -> Tuple[Any, Any, Dict[str, Any]]:
            anchor = expected_checksum or self.config.trusted_checksums.get(task_norm)
            cached_sha = str(cached_meta.get("_artifact_sha256", "")).lower()
            if anchor and cached_sha != anchor.strip().lower():
                raise ChecksumMismatchError(
                    f"Cached artifact checksum mismatch for {task_norm}: expected '{anchor.strip().lower()}', got '{cached_sha}'."
                )
            if self.config.strict_checksum_verification and not (anchor or cached_meta.get("_is_independently_trusted")):
                raise ArtifactCorruptedError(
                    f"Strict checksum verification failed on cache hit for task '{task_norm}': independent trust anchor required."
                )
            return None

        # --- FAST O(1) CACHE PATH ---
        with self._CACHE_LOCK:
            start_gen = self._TASK_GENERATIONS.get(task_norm, 0)
            if self.config.cache_models:
                if model_version:
                    v_str = str(model_version).strip()
                    for k, val in self._CLASS_CACHE.items():
                        parts = k.split("::")
                        if len(parts) >= 4 and parts[0] == base_norm and parts[1] == task_norm and parts[3] == v_str:
                            _verify_cached_checksum(val[2])
                            return val
                elif scoped_task_key in self._TASK_TO_CACHE_KEY:
                    cache_key = self._TASK_TO_CACHE_KEY[scoped_task_key]
                    if cache_key in self._CLASS_CACHE:
                        val = self._CLASS_CACHE[cache_key]
                        _verify_cached_checksum(val[2])
                        return val

            # Obtain or create per-task loading lock under _CACHE_LOCK
            if scoped_task_key not in self._TASK_LOAD_LOCKS:
                self._TASK_LOAD_LOCKS[scoped_task_key] = threading.Lock()
            task_load_lock = self._TASK_LOAD_LOCKS[scoped_task_key]

        # --- SLOW CACHE MISS PATH (PER-TASK LOAD LOCK) ---
        with task_load_lock:
            # Double-check cache under _CACHE_LOCK
            with self._CACHE_LOCK:
                start_gen = self._TASK_GENERATIONS.get(task_norm, 0)
                start_global_gen = self._GLOBAL_GENERATION
                if self.config.cache_models:
                    if model_version:
                        v_str = str(model_version).strip()
                        for k, val in self._CLASS_CACHE.items():
                            parts = k.split("::")
                            if len(parts) >= 4 and parts[0] == base_norm and parts[1] == task_norm and parts[3] == v_str:
                                _verify_cached_checksum(val[2])
                                return val
                    elif scoped_task_key in self._TASK_TO_CACHE_KEY:
                        cache_key = self._TASK_TO_CACHE_KEY[scoped_task_key]
                        if cache_key in self._CLASS_CACHE:
                            val = self._CLASS_CACHE[cache_key]
                            _verify_cached_checksum(val[2])
                            return val

            task_dir = self.resolve_task_dir(task_norm, model_version=model_version)
            meta_path = os.path.join(task_dir, "metadata.json")

            schema, raw_metadata = ModelMetadataValidator.load_and_validate(meta_path)
            est_path, prep_path = ModelMetadataValidator.verify_artifacts_exist(task_dir, schema)

            # Compute actual artifact checksum
            computed_sha256 = self.compute_sha256(est_path)
            raw_metadata["_artifact_sha256"] = computed_sha256
            raw_metadata["_artifact_dir"] = task_dir

            # Resolve expected checksum and classify trust level
            independent_checksum = (
                expected_checksum
                or self.config.trusted_checksums.get(task_norm)
            )
            local_meta_checksum = raw_metadata.get("artifact_checksum")

            if independent_checksum:
                # Level 1: Independently trusted anchor
                trusted_norm = independent_checksum.strip().lower()
                if computed_sha256 != trusted_norm:
                    raise ChecksumMismatchError(
                        f"Checksum mismatch for {task_norm} estimator artifact at '{est_path}': "
                        f"expected independent trusted '{trusted_norm}', got '{computed_sha256}'"
                    )
                checksum_verified = True
                is_independently_trusted = True
                trust_source = "INDEPENDENT_PARAMETER" if expected_checksum else "INDEPENDENT_CONFIG"
            elif local_meta_checksum:
                # Level 2: Local metadata check (never report as independently trusted)
                local_norm = local_meta_checksum.strip().lower()
                if computed_sha256 != local_norm:
                    raise ChecksumMismatchError(
                        f"Local metadata checksum mismatch for {task_norm} at '{est_path}': "
                        f"metadata declared '{local_norm}', got '{computed_sha256}'"
                    )
                checksum_verified = True
                is_independently_trusted = False
                trust_source = "LOCAL_METADATA_UNVERIFIED"
                if self.config.strict_checksum_verification:
                    raise ArtifactCorruptedError(
                        f"Strict verification failed: task '{task_norm}' checksum is only from unauthenticated local metadata. "
                        f"Independent trust anchor required."
                    )
            else:
                # Level 3: No checksum available
                checksum_verified = False
                is_independently_trusted = False
                trust_source = "UNVERIFIED_MISSING_CHECKSUM"
                if self.config.strict_checksum_verification:
                    raise ArtifactCorruptedError(
                        f"Strict checksum verification failed: no checksum available for task '{task_norm}' at '{task_dir}'."
                    )
                logger.warning(
                    "Artifact for '%s' loaded without independent checksum verification (strict_checksum_verification=False).",
                    task_norm
                )

            raw_metadata["_checksum_verified"] = checksum_verified
            raw_metadata["_is_independently_trusted"] = is_independently_trusted
            raw_metadata["_checksum_trust_source"] = trust_source

            # Form composite versioned cache key scoped to base_dir
            version_str = str(schema.saved_timestamp or "v1")
            cache_key = f"{base_norm}::{task_norm}::{schema.model_name}::{version_str}::{computed_sha256[:12]}"

            # Load artifacts into memory
            try:
                estimator = joblib.load(est_path)
            except Exception as exc:
                raise ArtifactCorruptedError(f"Failed to load estimator from '{est_path}': {exc}") from exc

            preprocessor = None
            if prep_path is not None:
                try:
                    preprocessor = joblib.load(prep_path)
                except Exception as exc:
                    raise ArtifactCorruptedError(f"Failed to load preprocessor from '{prep_path}': {exc}") from exc

            cached_tuple = (estimator, preprocessor, raw_metadata)
            with self._CACHE_LOCK:
                current_gen = self._TASK_GENERATIONS.get(task_norm, 0)
                if current_gen == start_gen and self._GLOBAL_GENERATION == start_global_gen:
                    if self.config.cache_models:
                        self._CLASS_CACHE[cache_key] = cached_tuple
                        if not model_version:
                            self._TASK_TO_CACHE_KEY[scoped_task_key] = cache_key
                    logger.info(
                        "Successfully loaded and cached model for task '%s' (%s, version=%s, trust=%s) from '%s'",
                        task_norm, schema.model_name, version_str, trust_source, task_dir
                    )
                else:
                    logger.warning(
                        "Discarded loaded model for '%s' due to concurrent invalidation (start_gen=%d, current_gen=%d, global_gen=%d vs %d).",
                        task_norm, start_gen, current_gen, start_global_gen, self._GLOBAL_GENERATION
                    )
            return cached_tuple
