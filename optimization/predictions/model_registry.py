"""
optimization/predictions/model_registry.py

Artifact loading and registry service for Phase 4 champion models.
"""

import os
import json
from typing import Dict, Any, Tuple
import joblib
from optimization.exceptions import ModelInferenceError


class ModelRegistry:
    """Manages loading and metadata verification of serialized Phase 4 models."""

    DEFAULT_BASE_DIR = "data/models"

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR):
        self.base_dir = base_dir
        self._cache: Dict[str, Tuple[Any, Any, Dict[str, Any]]] = {}

    def get_model(self, task_name: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Loads (estimator, preprocessor, metadata) for the requested task.
        Caches in memory for fast repeated inference.
        """
        if task_name in self._cache:
            return self._cache[task_name]

        task_dir = os.path.join(self.base_dir, task_name)
        if not os.path.exists(task_dir):
            raise ModelInferenceError(f"Model directory not found for task '{task_name}' at {task_dir}")

        meta_path = os.path.join(task_dir, "metadata.json")
        est_path = os.path.join(task_dir, "estimator.joblib")
        prep_path = os.path.join(task_dir, "preprocessor.joblib")

        if not os.path.exists(meta_path) or not os.path.exists(est_path):
            raise ModelInferenceError(f"Missing required artifact files in {task_dir}")

        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        estimator = joblib.load(est_path)
        preprocessor = joblib.load(prep_path) if os.path.exists(prep_path) else None

        self._cache[task_name] = (estimator, preprocessor, metadata)
        return estimator, preprocessor, metadata
