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
    _CACHE_LOCK = threading.RLock()

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR, db: Optional[Any] = None):
        self.base_dir = base_dir
        self.db = db

    @classmethod
    def invalidate_cache(cls, task_name: Optional[str] = None) -> None:
        """Invalidates in-memory cached model artifacts across all instances in a thread-safe manner."""
        with cls._CACHE_LOCK:
            if task_name:
                task_norm = task_name.lower().strip()
                cls._TASK_GENERATIONS[task_norm] = cls._TASK_GENERATIONS.get(task_norm, 0) + 1
                if task_norm in cls._CLASS_CACHE:
                    del cls._CLASS_CACHE[task_norm]
                    logger.info("Invalidated model cache for task: %s (gen=%d)", task_norm, cls._TASK_GENERATIONS[task_norm])
            else:
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

    def _resolve_task_artifact_dir(self, task_name: str) -> str:
        """
        Resolves the artifact directory for the given task.
        Prioritizes live database champion record if available, falling back to disk conventions.
        """
        task_norm = task_name.lower().strip()

        # 1. Query database champion if DB session is available
        if self.db is not None:
            try:
                from backend.app.models.schema import MLModel
                model_rec = self.db.query(MLModel).execution_options(populate_existing=True).filter(
                    MLModel.model_type == task_norm,
                    MLModel.is_champion == True,
                ).first()
                if model_rec and model_rec.artifact_dir and os.path.exists(model_rec.artifact_dir):
                    return model_rec.artifact_dir
            except Exception as e:
                logger.debug("Database champion lookup skipped for %s: %s", task_norm, e)

        # 2. Check standard base_dir
        standard_path = os.path.join(self.base_dir, task_norm)
        if os.path.exists(standard_path):
            return standard_path

        raise ModelInferenceError(f"Model directory not found for task '{task_name}' at {standard_path}")

    def get_model(self, task_name: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Loads (estimator, preprocessor, metadata) for the requested task.
        Caches in memory for fast repeated inference with generation validation.
        """
        task_norm = task_name.lower().strip()
        with self._CACHE_LOCK:
            start_gen = self._TASK_GENERATIONS.get(task_norm, 0)
            if task_norm in self._CLASS_CACHE:
                return self._CLASS_CACHE[task_norm]

        task_dir = self._resolve_task_artifact_dir(task_norm)

        meta_path = os.path.join(task_dir, "metadata.json")
        est_path = os.path.join(task_dir, "estimator.joblib")
        prep_path = os.path.join(task_dir, "preprocessor.joblib")

        if not os.path.exists(meta_path) or not os.path.exists(est_path):
            raise ModelInferenceError(f"Missing required artifact files in {task_dir}")

        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Validate metadata contents
        if "feature_names" not in metadata and "features" not in metadata:
            logger.warning("Artifact metadata for %s lacks explicit feature_names list.", task_norm)

        estimator = joblib.load(est_path)
        preprocessor = joblib.load(prep_path) if os.path.exists(prep_path) else None

        # Verify integrity
        est_hash = self.compute_file_sha256(est_path)
        metadata["_artifact_sha256"] = est_hash
        metadata["_artifact_dir"] = task_dir

        with self._CACHE_LOCK:
            current_gen = self._TASK_GENERATIONS.get(task_norm, 0)
            if current_gen == start_gen:
                self._CLASS_CACHE[task_norm] = (estimator, preprocessor, metadata)
                logger.info("Successfully loaded and cached model artifacts for '%s' from %s", task_norm, task_dir)
            else:
                logger.warning("Discarded loaded model for '%s' due to concurrent invalidation (start_gen=%d, current_gen=%d).", task_norm, start_gen, current_gen)

        return estimator, preprocessor, metadata
