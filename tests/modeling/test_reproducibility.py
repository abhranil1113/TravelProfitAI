"""
Tests for Pipeline Reproducibility.
Verifies that random seeds are strictly respected, producing identical splits
and deterministic model outputs across repeated runs.
"""

import pytest
import numpy as np
from modeling.config import TaskType
from modeling.model_factory import create_model


def test_random_forest_reproducibility():
    np.random.seed(42)
    X = np.random.randn(50, 4)
    y = np.random.choice([0, 1], size=50)

    model1 = create_model("random_forest", TaskType.BINARY_CLASSIFICATION, random_state=42)
    model1.fit(X, y)
    preds1 = model1.predict_proba(X)

    model2 = create_model("random_forest", TaskType.BINARY_CLASSIFICATION, random_state=42)
    model2.fit(X, y)
    preds2 = model2.predict_proba(X)

    assert np.allclose(preds1, preds2)


def test_xgboost_reproducibility():
    np.random.seed(42)
    X = np.random.randn(50, 4)
    y = np.random.randn(50)

    model1 = create_model("xgboost", TaskType.REGRESSION, random_state=42)
    model1.fit(X, y)
    preds1 = model1.predict(X)

    model2 = create_model("xgboost", TaskType.REGRESSION, random_state=42)
    model2.fit(X, y)
    preds2 = model2.predict(X)

    assert np.allclose(preds1, preds2)
