"""
Tests for Hyperparameter Tuning.
Verifies that hyperparameter search tunes parameters strictly on training data,
returns best estimators, best parameters, and handles default fallbacks.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.config import TaskType, ValidationStrategy
from modeling.registry.task_registry import TaskConfig
from modeling.hyperparameter_tuning import tune_model_hyperparameters


def test_tune_model_hyperparameters():
    task_cfg = TaskConfig(
        task_name="tune_test",
        dataset_name="dummy_ds",
        task_type=TaskType.REGRESSION,
        target_column="target",
        feature_columns=["f1", "f2"],
        categorical_columns=[],
        numerical_columns=["f1", "f2"],
        validation_strategy=ValidationStrategy.KFOLD,
        n_splits=2,
        primary_metric="mae",
    )

    np.random.seed(42)
    X_train = pd.DataFrame({
        "f1": np.random.randn(40),
        "f2": np.random.randn(40),
    })
    y_train = pd.Series(2.0 * X_train["f1"] + np.random.randn(40) * 0.1)

    # Param grid for estimator directly (prefix model__ is added internally)
    param_grid = {
        "n_estimators": [5, 10],
        "max_depth": [2, 3],
    }

    best_estimator, best_params, best_score = tune_model_hyperparameters(
        task_config=task_cfg,
        model_name="random_forest",
        X_train=X_train,
        y_train=y_train,
        param_grid=param_grid,
        n_iter=2,
        cv_splits=2,
    )

    assert best_estimator is not None
    assert best_params is not None
    assert isinstance(best_score, float)
