"""
Tests for Model Persistence (Saving and Loading Model Artifacts).
Verifies that models, preprocessors, and metadata are saved and reloaded accurately,
yielding identical predictions before and after serialization.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.model_factory import create_model
from modeling.preprocessing import build_preprocessor
from modeling.trainer import ModelArtifact
from modeling.model_persistence import save_model_artifact, load_model_artifact


def test_save_and_load_model_artifact(tmp_path):
    task_cfg = TaskConfig(
        task_name="test_persist_task",
        dataset_name="dummy_ds",
        task_type=TaskType.REGRESSION,
        target_column="target",
        feature_columns=["f1", "f2"],
        categorical_columns=[],
        numerical_columns=["f1", "f2"],
    )

    X_train = pd.DataFrame({"f1": [1.0, 2.0, 3.0, 4.0], "f2": [10.0, 20.0, 30.0, 40.0]})
    y_train = pd.Series([2.0, 4.0, 6.0, 8.0])

    preprocessor = build_preprocessor(
        numerical_cols=["f1", "f2"],
        categorical_cols=[],
    )
    X_trans = preprocessor.fit_transform(X_train)

    model = create_model("linear_regression", TaskType.REGRESSION)
    model.fit(X_trans, y_train)

    artifact = ModelArtifact(
        estimator=model,
        preprocessor=preprocessor,
        feature_names=["f1", "f2"],
        task_type=TaskType.REGRESSION,
        model_name="linear_regression",
    )

    task_dir = tmp_path / "test_persist_task"

    # Save artifact
    save_path = save_model_artifact(
        artifact=artifact,
        task_config=task_cfg,
        cv_summary={"cv_folds": 3, "mean_mae": 0.05},
        test_metrics={"mae": 0.04, "rmse": 0.06},
        selection_rationale="Test linear persistence",
        output_dir=task_dir,
    )
    assert save_path.exists()
    assert (task_dir / "estimator.joblib").exists()
    assert (task_dir / "preprocessor.joblib").exists()
    assert (task_dir / "metadata.json").exists()

    # Load artifact
    loaded_artifact, loaded_metadata = load_model_artifact(
        task_name="test_persist_task",
        models_root=tmp_path,
    )
    assert loaded_metadata["model_name"] == "linear_regression"
    assert loaded_metadata["task_name"] == "test_persist_task"

    # Verify predictions match exactly
    X_test = pd.DataFrame({"f1": [5.0], "f2": [50.0]})
    pred_orig, _ = artifact.predict(X_test)
    pred_loaded, _ = loaded_artifact.predict(X_test)
    assert np.isclose(pred_orig[0], pred_loaded[0])


def test_atomic_save_and_enriched_metadata(tmp_path):
    task_cfg = TaskConfig(
        task_name="test_gov_task",
        dataset_name="dummy_ds",
        task_type=TaskType.REGRESSION,
        target_column="target",
        feature_columns=["f1", "f2"],
        categorical_columns=[],
        numerical_columns=["f1", "f2"],
    )

    X_train = pd.DataFrame({"f1": [1.0, 2.0], "f2": [10.0, 20.0]})
    y_train = pd.Series([2.0, 4.0])

    model = create_model("linear_regression", TaskType.REGRESSION)
    model.fit(X_train, y_train)

    artifact = ModelArtifact(
        estimator=model,
        preprocessor=None,
        feature_names=["f1", "f2"],
        task_type=TaskType.REGRESSION,
        model_name="linear_regression",
    )

    task_dir = tmp_path / "test_gov_task"
    save_path = save_model_artifact(
        artifact=artifact,
        task_config=task_cfg,
        cv_summary={"mean_mae": 0.05},
        test_metrics={"mae": 0.04},
        selection_rationale="Governance test",
        output_dir=task_dir,
        dataset_records_count=2,
    )

    # Check atomic write: .tmp files must have been cleaned up via atomic rename
    assert not (task_dir / "estimator.joblib.tmp").exists()
    assert not (task_dir / "metadata.json.tmp").exists()

    # Check enriched metadata
    import json
    with open(task_dir / "metadata.json", "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["feature_schema_version"] == "1.0.0"
    assert "dataset_fingerprint" in meta
    assert "schema_digest_sha256" in meta["dataset_fingerprint"]
    assert "schema_fingerprint" in meta
    assert "content_fingerprint" in meta
    assert meta["schema_fingerprint"]["fingerprint_type"] == "schema_digest"
    assert meta["schema_fingerprint"]["algorithm"] == "sha256"
    assert "system_environment" in meta
    assert "packages" in meta
    assert "pandas" in meta["packages"]
    assert "numpy" in meta["packages"]


def test_staging_directory_promotion_and_fingerprints(tmp_path):
    from modeling.model_persistence import (
        compute_schema_fingerprint,
        compute_dataset_content_fingerprint,
        compute_dataset_fingerprint,
    )
    # 1. Test fingerprint separation
    schema_fp = compute_schema_fingerprint(["feat_a", "feat_b"], record_count=100, dataset_name="test_ds")
    assert schema_fp["fingerprint_type"] == "schema_digest"
    assert schema_fp["algorithm"] == "sha256"
    assert "digest" in schema_fp

    df = pd.DataFrame({"feat_a": [1.0, 2.0], "feat_b": [3.0, 4.0]})
    content_fp = compute_dataset_content_fingerprint(df)
    assert content_fp["fingerprint_type"] == "deterministic_content_digest"
    assert content_fp["algorithm"] == "sha256"
    assert content_fp["sample_rows_hashed"] == 2

    # 2. Test multi-file atomic persistence promotion on overwrite
    task_cfg = TaskConfig(
        task_name="test_staging_task",
        dataset_name="test_ds",
        task_type=TaskType.REGRESSION,
        target_column="target",
        feature_columns=["feat_a", "feat_b"],
        categorical_columns=[],
        numerical_columns=["feat_a", "feat_b"],
    )
    model = create_model("linear_regression", TaskType.REGRESSION)
    model.fit(df, pd.Series([10.0, 20.0]))
    artifact = ModelArtifact(
        estimator=model,
        preprocessor=None,
        feature_names=["feat_a", "feat_b"],
        task_type=TaskType.REGRESSION,
        model_name="linear_regression",
    )
    task_dir = tmp_path / "test_staging_task"

    # Initial save
    save_model_artifact(
        artifact=artifact,
        task_config=task_cfg,
        cv_summary={"mean_mae": 0.1},
        test_metrics={"mae": 0.08},
        selection_rationale="Initial save",
        output_dir=task_dir,
        df_for_content_hash=df,
    )
    assert (task_dir / "estimator.joblib").exists()
    assert (task_dir / "metadata.json").exists()

    # Second save (overwrite existing directory atomically via staging and backup)
    save_model_artifact(
        artifact=artifact,
        task_config=task_cfg,
        cv_summary={"mean_mae": 0.09},
        test_metrics={"mae": 0.07},
        selection_rationale="Second save overwrite",
        output_dir=task_dir,
        overwrite=True,
        df_for_content_hash=df,
    )
    assert (task_dir / "estimator.joblib").exists()
    # Confirm no staging or backup directories left behind
    parent_dirs = [p.name for p in tmp_path.iterdir() if p.is_dir()]
    assert not any(d.startswith(".staging") for d in parent_dirs)
    assert not any(d.startswith(".backup") for d in parent_dirs)

