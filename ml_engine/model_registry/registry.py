"""
ml_engine/model_registry/registry.py

Artifact discovery, metadata validation, model versioning, and caching registry.
Provides unified model loading and caching for all Phase 4 models.
"""

import hashlib
import json
import logging
import os
from typing import Dict, Any, Tuple, Optional, List
import joblib

from ml_engine.config import MLEngineConfig
from ml_engine.exceptions import ModelNotFoundError, ArtifactCorruptedError
from ml_engine.model_registry.model_metadata import ModelMetadataValidator
from ml_engine.schemas import ModelMetadataSchema, PredictionTask

logger = logging.getLogger(__name__)


class ModelArtifactRegistry:
    """
    Manages discovery, validation, caching, and safe loading of Phase 4 model artifacts.
    Supports in-memory class caching and database champion lookup when a database session is provided.
    """

    DEFAULT_BASE_DIR = "data/models"
    _CLASS_CACHE: Dict[str, Tuple[Any, Any, Dict[str, Any]]] = {}

    def __init__(
        self,
        base_dir: str = DEFAULT_BASE_DIR,
        db: Optional[Any] = None,
        config: Optional[MLEngineConfig] = None,
    ):
        self.base_dir = base_dir
        self.db = db
        self.config = config or MLEngineConfig(base_model_dir=base_dir)

    @classmethod
    def invalidate_cache(cls, task_name: Optional[str] = None) -> None:
        """Invalidates in-memory cached model artifacts across all instances."""
        if task_name:
            task_norm = task_name.lower().strip()
            if task_norm in cls._CLASS_CACHE:
                del cls._CLASS_CACHE[task_norm]
                logger.info("Invalidated ML Engine model cache for task: %s", task_norm)
        else:
            cls._CLASS_CACHE.clear()
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
        return sha256.hexdigest()

    def discover_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discovers all available model directories and metadata across standard and candidate paths.
        """
        discovered: Dict[str, List[Dict[str, Any]]] = {}
        search_roots = [
            self.base_dir,
            os.path.join(self.base_dir, "candidates"),
            os.path.join(self.base_dir, "candidates_stage_4c"),
        ]

        for root in search_roots:
            if not os.path.exists(root):
                continue
            for item in os.listdir(root):
                dir_path = os.path.join(root, item)
                meta_path = os.path.join(dir_path, "metadata.json")
                if os.path.isdir(dir_path) and os.path.exists(meta_path):
                    try:
                        schema, raw = ModelMetadataValidator.load_and_validate(meta_path)
                        task_name = schema.task_name
                        info = {
                            "task_name": task_name,
                            "path": dir_path,
                            "model_name": schema.model_name,
                            "saved_timestamp": schema.saved_timestamp,
                            "feature_count": schema.feature_count,
                            "metrics": schema.test_metrics,
                        }
                        discovered.setdefault(task_name, []).append(info)
                    except Exception as exc:
                        logger.debug("Skipping unparseable model at %s: %s", dir_path, exc)

        return discovered

    def resolve_task_dir(self, task_name: str) -> str:
        """
        Resolves the artifact directory for the given task.
        Prioritizes live database champion record if available, falling back to disk paths.
        """
        task_norm = task_name.lower().strip()

        # 1. Query database champion if DB session is available
        if self.db is not None:
            try:
                from backend.app.models.schema import MLModel
                model_rec = (
                    self.db.query(MLModel)
                    .filter(
                        MLModel.model_type == task_norm,
                        MLModel.is_champion == True,
                    )
                    .first()
                )
                if model_rec and model_rec.artifact_dir and os.path.exists(model_rec.artifact_dir):
                    return model_rec.artifact_dir
            except Exception as e:
                logger.debug("Database champion lookup skipped for %s: %s", task_norm, e)

        # 2. Check standard base_dir
        standard_path = os.path.join(self.base_dir, task_norm)
        if os.path.exists(standard_path):
            return standard_path

        # 3. Check stage 4c candidates
        candidates_4c_path = os.path.join(self.base_dir, "candidates_stage_4c", task_norm)
        if os.path.exists(candidates_4c_path):
            return candidates_4c_path

        # 4. Check base candidates
        candidates_path = os.path.join(self.base_dir, "candidates", task_norm)
        if os.path.exists(candidates_path):
            return candidates_path

        raise ModelNotFoundError(
            f"Artifact directory not found for ML task '{task_name}' at {standard_path}"
        )

    def get_model(self, task_name: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Loads (estimator, preprocessor, metadata_dict) for the requested task.
        Caches in memory for fast repeated inference.
        """
        task_norm = task_name.lower().strip()
        if self.config.cache_models and task_norm in self._CLASS_CACHE:
            return self._CLASS_CACHE[task_norm]

        task_dir = self.resolve_task_dir(task_norm)
        meta_path = os.path.join(task_dir, "metadata.json")

        schema, raw_metadata = ModelMetadataValidator.load_and_validate(meta_path)
        est_path, prep_path = ModelMetadataValidator.verify_artifacts_exist(task_dir, schema)

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
        if self.config.cache_models:
            self._CLASS_CACHE[task_norm] = cached_tuple

        logger.info(
            "Successfully loaded model for task '%s' (%s) from '%s'",
            task_norm, schema.model_name, task_dir
        )
        return cached_tuple
