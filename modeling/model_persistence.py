"""
TBO InventoryIQ - Model Serialization & Persistence Engine (Phase 4)
Safely serializes and deserializes champion model artifacts, fitted preprocessing
pipelines, feature order catalogs, and provenance metadata.
"""

from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import os
import shutil
import json
import hashlib
import platform
import sys
import datetime
import logging
import joblib
import sklearn
import xgboost as xgb
import lightgbm as lgb
import pandas as pd
import numpy as np

from modeling.config import MODELS_DIR, RANDOM_SEED, TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.trainer import ModelArtifact

logger = logging.getLogger(__name__)


def compute_schema_fingerprint(
    feature_names: List[str],
    record_count: Optional[int] = None,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates a reproducible SHA-256 fingerprint for dataset schema structure."""
    schema_str = f"{dataset_name}:{record_count}:{','.join(sorted(feature_names))}"
    digest = hashlib.sha256(schema_str.encode("utf-8")).hexdigest()
    return {
        "fingerprint_type": "schema_digest",
        "algorithm": "sha256",
        "digest": digest,
        "schema_digest_sha256": digest,
        "feature_count": len(feature_names),
        "record_count": record_count,
        "dataset_name": dataset_name,
    }


def compute_dataset_content_fingerprint(
    df: Optional[pd.DataFrame] = None,
    sample_rows: int = 1000,
) -> Dict[str, Any]:
    """Generates a reproducible SHA-256 fingerprint for dataset content values."""
    if df is None or len(df) == 0:
        return {
            "fingerprint_type": "deterministic_content_digest",
            "algorithm": "sha256",
            "digest": "NO_CONTENT_DATA",
            "sample_rows_hashed": 0,
            "total_records": 0,
        }

    n_sample = min(len(df), sample_rows)
    sample_df = df.iloc[:n_sample]
    content_repr = sample_df.to_csv(index=False)
    digest = hashlib.sha256(content_repr.encode("utf-8")).hexdigest()
    return {
        "fingerprint_type": "deterministic_content_digest",
        "algorithm": "sha256",
        "digest": digest,
        "sample_rows_hashed": n_sample,
        "total_records": len(df),
    }


def compute_dataset_fingerprint(
    feature_names: List[str],
    record_count: Optional[int] = None,
    dataset_name: Optional[str] = None,
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Generates dataset provenance fingerprints distinguishing schema from data content.
    """
    schema_fp = compute_schema_fingerprint(feature_names, record_count, dataset_name)
    content_fp = compute_dataset_content_fingerprint(df)
    return {
        "schema_digest_sha256": schema_fp["digest"],
        "schema_fingerprint": schema_fp,
        "content_fingerprint": content_fp,
        "feature_count": len(feature_names),
        "record_count": record_count,
    }


def save_model_artifact(
    artifact: ModelArtifact,
    task_config: TaskConfig,
    cv_summary: Dict[str, Any],
    test_metrics: Dict[str, Any],
    selection_rationale: str,
    output_dir: Optional[Path] = None,
    overwrite: bool = True,
    dataset_records_count: Optional[int] = None,
    date_ranges: Optional[Dict[str, str]] = None,
    threshold_provenance: Optional[Dict[str, Any]] = None,
    df_for_content_hash: Optional[pd.DataFrame] = None,
) -> Path:
    """
    Atomically serializes a complete model container bundle (estimator, preprocessor, metadata)
    using a dedicated staging directory to guarantee multi-file atomicity.
    
    Structure:
      data/models/<task_name>/
      ├── estimator.joblib
      ├── preprocessor.joblib
      └── metadata.json
    """
    target_dir = output_dir or (MODELS_DIR / task_config.task_name)
    target_dir = Path(target_dir)

    estimator_path = target_dir / "estimator.joblib"
    if not overwrite and estimator_path.exists():
        logger.warning(f"Preserving existing champion artifact at {target_dir}. Overwrite=False.")
        return target_dir

    target_parent = target_dir.parent
    target_parent.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    staging_dir = target_parent / f".staging_{task_config.task_name}_{timestamp_str}"
    backup_dir = target_parent / f".backup_{task_config.task_name}_{timestamp_str}"

    # Ensure staging dir is fresh
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1. Compute fingerprints distinguishing schema from content (F-08)
    schema_fp = compute_schema_fingerprint(
        artifact.feature_names,
        record_count=dataset_records_count,
        dataset_name=task_config.dataset_name,
    )
    content_fp = compute_dataset_content_fingerprint(df_for_content_hash)
    dataset_fp = {
        "schema_digest_sha256": schema_fp["digest"],
        "schema_fingerprint": schema_fp,
        "content_fingerprint": content_fp,
        "feature_count": len(artifact.feature_names),
        "record_count": dataset_records_count,
    }

    # 2. Build complete metadata dictionary
    metadata = {
        "task_name": task_config.task_name,
        "task_type": task_config.task_type.value,
        "dataset_name": task_config.dataset_name,
        "model_name": artifact.model_name,
        "target_column": task_config.target_column,
        "feature_schema_version": "1.0.0",
        "dataset_fingerprint": dataset_fp,
        "schema_fingerprint": schema_fp,
        "content_fingerprint": content_fp,
        "validation_strategy": task_config.validation_strategy.value,
        "split_policy": f"Deterministic {task_config.validation_strategy.value} (n_splits={task_config.n_splits})",
        "date_ranges": date_ranges or {},
        "threshold_provenance": threshold_provenance,
        "feature_names": artifact.feature_names,
        "feature_count": len(artifact.feature_names),
        "saved_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "random_seed": RANDOM_SEED,
        "system_environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "packages": {
            "sklearn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "lightgbm": lgb.__version__,
            "joblib": joblib.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "fit_time_seconds": artifact.fit_time_seconds,
        "cv_summary": cv_summary,
        "test_metrics": test_metrics,
        "selection_rationale": selection_rationale,
        "business_params": task_config.business_params,
        "estimator_artifact": "estimator.joblib",
        "preprocessor_artifact": "preprocessor.joblib" if artifact.preprocessor is not None else None,
    }

    # 3. Write all bundle components into staging directory
    try:
        staging_estimator = staging_dir / "estimator.joblib"
        staging_preprocessor = staging_dir / "preprocessor.joblib"
        staging_metadata = staging_dir / "metadata.json"

        joblib.dump(artifact.estimator, staging_estimator, compress=3)
        if artifact.preprocessor is not None:
            joblib.dump(artifact.preprocessor, staging_preprocessor, compress=3)
        with open(staging_metadata, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 4. Multi-File Atomic Promotion (F-07)
        if target_dir.exists():
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            target_dir.rename(backup_dir)
            try:
                staging_dir.rename(target_dir)
                shutil.rmtree(backup_dir, ignore_errors=True)
            except Exception as promo_exc:
                logger.error(f"Promotion failed for '{task_config.task_name}': {promo_exc}. Rolling back.")
                if backup_dir.exists() and not target_dir.exists():
                    backup_dir.rename(target_dir)
                raise IOError(f"Atomic promotion failed for model artifact: {promo_exc}") from promo_exc
        else:
            staging_dir.rename(target_dir)

    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    logger.info(
        f"Persisted champion model for '{task_config.task_name}' ({artifact.model_name}) "
        f"to {target_dir} (multi-file atomic staging promotion confirmed)"
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
