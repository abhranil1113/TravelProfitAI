"""
optimization/predictions/model_registry.py

Artifact loading and registry service for Phase 4 champion models.
Provides checksum verification, artifact schema validation, database-aware
champion resolution, and cache invalidation.
"""

import hashlib
import json
import logging
import os
import threading
from typing import Dict, Any, Tuple, Optional
import joblib
from optimization.exceptions import ModelInferenceError

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Manages loading and metadata verification of serialized Phase 4 models."""

    DEFAULT_BASE_DIR = "data/models"
    _CLASS_CACHE: Dict[str, Tuple[Any, Any, Dict[str, Any]]] = {}
    _TASK_GENERATIONS: Dict[str, int] = {}
    _GLOBAL_GENERATION = 0
    _CACHE_LOCK = threading.RLock()

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR, db: Optional[Any] = None):
        self.base_dir = base_dir
        self.db = db

    @classmethod
    def invalidate_cache(cls, task_name: Optional[str] = None) -> None:
        """Invalidates in-memory cached model artifacts across all instances in a thread-safe manner."""
        with cls._CACHE_LOCK:
            if task_name:
                task_value = getattr(task_name, "value", task_name)
                task_norm = str(task_value).lower().strip()
                cls._TASK_GENERATIONS[task_norm] = cls._TASK_GENERATIONS.get(task_norm, 0) + 1
                if task_norm in cls._CLASS_CACHE:
                    del cls._CLASS_CACHE[task_norm]
                    logger.info("Invalidated model cache for task: %s (gen=%d)", task_norm, cls._TASK_GENERATIONS[task_norm])
            else:
                cls._GLOBAL_GENERATION += 1
                for k in list(cls._TASK_GENERATIONS.keys()):
                    cls._TASK_GENERATIONS[k] += 1
                cls._CLASS_CACHE.clear()
                logger.info("Cleared entire ModelRegistry artifact cache.")

    def clear_cache(self, task_name: Optional[str] = None) -> None:
        """Instance alias for cache invalidation."""
        self.invalidate_cache(task_name)

    @staticmethod
    def compute_file_sha256(filepath: str) -> str:
        """Computes SHA-256 hash of a serialized artifact file."""
        if not os.path.exists(filepath):
            return ""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _resolve_task_artifact(self, task_name: str) -> Tuple[str, Dict[str, Any]]:
        """
        Resolves the artifact directory for the given task.
        Database-backed inference must use a registered champion; it never falls back
        to a disk convention when the champion record is missing or invalid.
        """
        task_norm = task_name.lower().strip()

        if self.db is not None:
            try:
                from backend.app.models.schema import MLModel
                model_records = self.db.query(MLModel).execution_options(populate_existing=True).filter(
                    MLModel.model_type == task_norm,
                    MLModel.is_champion == True,
                ).all()
            except Exception as exc:
                raise ModelInferenceError(
                    f"Unable to resolve the registered champion for task '{task_norm}': {exc}"
                ) from exc
            if len(model_records) != 1:
                raise ModelInferenceError(
                    f"Expected exactly one registered champion for task '{task_norm}', found {len(model_records)}."
                )
            model_rec = model_records[0]
            if not model_rec.artifact_dir or not os.path.isdir(model_rec.artifact_dir):
                raise ModelInferenceError(
                    f"Champion artifact directory is unavailable for task '{task_norm}'."
                )
            artifact = os.path.abspath(model_rec.artifact_dir)
            return artifact, {
                "_registry_model_id": model_rec.id,
                "_registry_model_name": model_rec.algorithm,
                "_registry_model_version": str(model_rec.version),
                "_registry_model_type": task_norm,
                "_registry_artifact_checksum": model_rec.artifact_checksum,
            }

        standard_path = os.path.join(self.base_dir, task_norm)
        if os.path.isdir(standard_path):
            return os.path.abspath(standard_path), {}

        raise ModelInferenceError(f"Model directory not found for task '{task_name}' at {standard_path}")

    def get_model(self, task_name: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Loads (estimator, preprocessor, metadata) for the requested task.
        Caches in memory while confirming that the cached artifact belongs to the
        currently registered champion.
        """
        task_value = getattr(task_name, "value", task_name)
        task_norm = str(task_value).lower().strip()

        for _ in range(3):
            with self._CACHE_LOCK:
                start_gen = self._TASK_GENERATIONS.get(task_norm, 0)
                start_global_gen = self._GLOBAL_GENERATION

            task_dir, registry_metadata = self._resolve_task_artifact(task_norm)
            with self._CACHE_LOCK:
                if (
                    self._TASK_GENERATIONS.get(task_norm, 0) != start_gen
                    or self._GLOBAL_GENERATION != start_global_gen
                ):
                    continue
                cached = self._CLASS_CACHE.get(task_norm)
                if cached:
                    cached_metadata = cached[2]
                    same_artifact = (
                        os.path.abspath(cached_metadata.get("_artifact_dir", "")) == task_dir
                        and cached_metadata.get("_registry_model_id") == registry_metadata.get("_registry_model_id")
                        and cached_metadata.get("_registry_model_version") == registry_metadata.get("_registry_model_version")
                    )
                    if same_artifact:
                        return cached

            meta_path = os.path.join(task_dir, "metadata.json")
            est_path = os.path.join(task_dir, "estimator.joblib")
            prep_path = os.path.join(task_dir, "preprocessor.joblib")
            if not os.path.isfile(meta_path) or not os.path.isfile(est_path):
                raise ModelInferenceError(f"Missing required artifact files in {task_dir}")

            try:
                with open(meta_path, "r", encoding="utf-8") as metadata_file:
                    metadata = json.load(metadata_file)
                if not isinstance(metadata, dict):
                    raise ValueError("Artifact metadata must be a JSON object.")
                features = metadata.get("feature_names", metadata.get("features"))
                if not isinstance(features, list) or not features:
                    raise ValueError("Artifact metadata must include a non-empty feature list.")
                declared_task = metadata.get("task_name")
                if declared_task and str(declared_task).lower() != task_norm:
                    raise ValueError(
                        f"Artifact task '{declared_task}' does not match requested task '{task_norm}'."
                    )
                declared_name = metadata.get("model_name") or metadata.get("algorithm")
                if (
                    declared_name
                    and registry_metadata.get("_registry_model_name")
                    and str(declared_name).casefold()
                    != str(registry_metadata["_registry_model_name"]).casefold()
                ):
                    raise ValueError(
                        "Artifact model name does not match the registered champion algorithm."
                    )
                estimator = joblib.load(est_path)
                preprocessor = joblib.load(prep_path) if os.path.isfile(prep_path) else None
            except Exception as exc:
                raise ModelInferenceError(
                    f"Unable to load valid model artifacts for task '{task_norm}': {exc}"
                ) from exc

            est_hash = self.compute_file_sha256(est_path)
            expected_hash = registry_metadata.get("_registry_artifact_checksum")
            if expected_hash and est_hash.lower() != str(expected_hash).lower():
                raise ModelInferenceError(
                    f"Champion estimator checksum mismatch for task '{task_norm}'."
                )
            metadata.update(registry_metadata)
            metadata["_artifact_sha256"] = est_hash
            metadata["_artifact_dir"] = task_dir

            with self._CACHE_LOCK:
                if (
                    self._TASK_GENERATIONS.get(task_norm, 0) == start_gen
                    and self._GLOBAL_GENERATION == start_global_gen
                ):
                    self._CLASS_CACHE[task_norm] = (estimator, preprocessor, metadata)
                    logger.info(
                        "Successfully loaded and cached model artifacts for '%s' from %s",
                        task_norm,
                        task_dir,
                    )
                    return estimator, preprocessor, metadata

        raise ModelInferenceError(
            f"Champion for task '{task_norm}' changed repeatedly while its artifacts were loading."
        )
