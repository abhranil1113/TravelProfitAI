"""
Tests for Cross-Validation Engine.
Verifies fold execution, fold metric collection, mean and std calculation,
and out-of-fold predictions.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.config import TaskType, ValidationStrategy
from modeling.registry.task_registry import TaskConfig
from modeling.cross_validator import execute_cross_validation, CrossValidationResult


def test_cross_validation_classification():
    task_cfg = TaskConfig(
        task_name="cv_clf_test",
        dataset_name="dummy_ds",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="target",
        feature_columns=["f1", "f2"],
        numerical_columns=["f1", "f2"],
        validation_strategy=ValidationStrategy.STRATIFIED_KFOLD,
        n_splits=3,
        primary_metric="f1_score",
    )

    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(60, 2), columns=["f1", "f2"])
    y = pd.Series([0] * 30 + [1] * 30)

    cv_result = execute_cross_validation(
        task_config=task_cfg,
        model_name="dummy",
        X=X,
        y=y,
    )

    assert isinstance(cv_result, CrossValidationResult)
    assert cv_result.model_name == "dummy"
    assert len(cv_result.fold_metrics) == 3
    assert "accuracy" in cv_result.mean_metrics
    assert "f1_score" in cv_result.mean_metrics
    assert cv_result.oof_predictions is not None


def test_cross_validation_regression():
    task_cfg = TaskConfig(
        task_name="cv_reg_test",
        dataset_name="dummy_ds",
        task_type=TaskType.REGRESSION,
        target_column="target",
        feature_columns=["f1", "f2"],
        numerical_columns=["f1", "f2"],
        validation_strategy=ValidationStrategy.KFOLD,
        n_splits=3,
        primary_metric="mae",
    )

    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(45, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.uniform(10, 50, 45))

    cv_result = execute_cross_validation(
        task_config=task_cfg,
        model_name="dummy",
        X=X,
        y=y,
    )

    assert len(cv_result.fold_metrics) == 3
    assert "mae" in cv_result.mean_metrics
    assert "rmse" in cv_result.mean_metrics
    assert cv_result.std_metrics["mae"] >= 0.0
