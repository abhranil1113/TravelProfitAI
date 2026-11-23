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
