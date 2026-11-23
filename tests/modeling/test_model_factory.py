"""
Tests for Model Factory.
Verifies instantiations of Random Forest, XGBoost, LightGBM, and baseline models
with deterministic random seed propagation and invalid model rejection.
"""

import pytest
from modeling.config import TaskType, DEFAULT_PARAM_GRIDS
from modeling.model_factory import create_model


def test_create_random_forest_classifier():
    model = create_model("random_forest", TaskType.BINARY_CLASSIFICATION, random_state=42)
    assert hasattr(model, "fit")
    assert hasattr(model, "predict_proba")
    assert model.random_state == 42


def test_create_xgboost_regressor():
    model = create_model("xgboost", TaskType.REGRESSION, random_state=42)
    assert hasattr(model, "fit")
    assert hasattr(model, "predict")
    assert model.random_state == 42


def test_create_lightgbm_forecaster():
    model = create_model("lightgbm", TaskType.TIME_SERIES_REGRESSION, random_state=42)
    assert hasattr(model, "fit")
    assert hasattr(model, "predict")
    assert model.random_state == 42


def test_create_unsupported_model_raises():
    with pytest.raises(ValueError, match="is not supported for task type"):
        create_model("non_existent_algorithm_xyz", TaskType.REGRESSION)


def test_get_default_hyperparameter_grids():
    assert "random_forest" in DEFAULT_PARAM_GRIDS
    assert "xgboost" in DEFAULT_PARAM_GRIDS
    assert "lightgbm" in DEFAULT_PARAM_GRIDS
