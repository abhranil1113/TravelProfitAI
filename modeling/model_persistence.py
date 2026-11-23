"""
TBO InventoryIQ - Model Serialization & Persistence Engine (Phase 4)
Safely serializes and deserializes champion model artifacts, fitted preprocessing
pipelines, feature order catalogs, and provenance metadata.
"""

from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import json
import datetime
import logging
import joblib
import sklearn
import xgboost as xgb
import lightgbm as lgb
import pandas as pd

from modeling.config import MODELS_DIR, RANDOM_SEED, TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.trainer import ModelArtifact

logger = logging.getLogger(__name__)


def save_model_artifact(
    artifact: ModelArtifact,
    task_config: TaskConfig,
    cv_summary: Dict[str, Any],
    test_metrics: Dict[str, Any],
    selection_rationale: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Serializes a trained ModelArtifact and its complete inference metadata.
    
    Structure:
      data/models/<task_name>/
      ├── estimator.joblib
      ├── preprocessor.joblib
      └── metadata.json
    """
    target_dir = output_dir or (MODELS_DIR / task_config.task_name)
    target_dir.mkdir(parents=True, exist_ok=True)

    estimator_path = target_dir / "estimator.joblib"
    preprocessor_path = target_dir / "preprocessor.joblib"
    metadata_path = target_dir / "metadata.json"

    # 1. Save Estimator
    joblib.dump(artifact.estimator, estimator_path, compress=3)

    # 2. Save Preprocessor
    if artifact.preprocessor is not None:
        joblib.dump(artifact.preprocessor, preprocessor_path, compress=3)

    # 3. Construct and Save Provenance Metadata
    metadata = {
        "task_name": task_config.task_name,
        "task_type": task_config.task_type.value,
        "dataset_name": task_config.dataset_name,
        "model_name": artifact.model_name,
        "target_column": task_config.target_column,
        "feature_names": artifact.feature_names,
        "feature_count": len(artifact.feature_names),
        "saved_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "random_seed": RANDOM_SEED,
        "packages": {
            "sklearn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "lightgbm": lgb.__version__,
            "joblib": joblib.__version__,
        },
        "fit_time_seconds": artifact.fit_time_seconds,
        "cv_summary": cv_summary,
        "test_metrics": test_metrics,
        "selection_rationale": selection_rationale,
        "business_params": task_config.business_params,
        "estimator_artifact": str(estimator_path.name),
        "preprocessor_artifact": str(preprocessor_path.name) if artifact.preprocessor is not None else None,
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        f"Persisted champion model for '{task_config.task_name}' ({artifact.model_name}) "
        f"to {target_dir}"
    )
    return target_dir


def load_model_artifact(
    task_name: str,
    models_root: Optional[Path] = None,
) -> Tuple[ModelArtifact, Dict[str, Any]]:
    """
    Safely loads a persisted model container and its provenance metadata.
    
    SECURITY NOTE:
    Joblib deserializes Python bytecodes. Only load model artifacts from trusted,
    internally verified storage environments.
    """
    target_dir = (models_root or MODELS_DIR) / task_name
    if not target_dir.exists():
        raise FileNotFoundError(f"Model directory not found for task '{task_name}': {target_dir}")

    estimator_path = target_dir / "estimator.joblib"
    preprocessor_path = target_dir / "preprocessor.joblib"
    metadata_path = target_dir / "metadata.json"

    if not estimator_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            f"Corrupted model artifact directory for '{task_name}'. Missing estimator or metadata."
        )

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    estimator = joblib.load(estimator_path)
    preprocessor = joblib.load(preprocessor_path) if preprocessor_path.exists() else None

    artifact = ModelArtifact(
        estimator=estimator,
        preprocessor=preprocessor,
        feature_names=metadata["feature_names"],
        task_type=TaskType(metadata["task_type"]),
        fit_time_seconds=metadata.get("fit_time_seconds", 0.0),
        model_name=metadata["model_name"],
    )

    logger.info(f"Loaded champion model for '{task_name}' ({metadata['model_name']}) from {target_dir}")
    return artifact, metadata
