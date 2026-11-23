"""
Tests for Baseline Models.
Verifies DummyClassifier, LogisticRegression, DummyRegressor, LinearRegression,
NaiveForecaster, and SeasonalNaiveForecaster implementations.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.baselines import (
    NaiveForecaster,
    SeasonalNaiveForecaster,
    create_baseline_model,
)
from modeling.config import TaskType


def test_naive_forecaster_fit_predict():
    forecaster = NaiveForecaster()
    y_train = np.array([10.0, 15.0, 20.0, 25.0])
    forecaster.fit(None, y_train)

    preds = forecaster.predict(np.zeros((3, 1)))
    assert len(preds) == 3
    assert np.all(preds == 25.0)


def test_naive_forecaster_lag_col():
    forecaster = NaiveForecaster(lag_col="lag_1")
    X = pd.DataFrame({"lag_1": [12.0, 14.0, 16.0]})
    preds = forecaster.predict(X)
    assert np.all(preds == [12.0, 14.0, 16.0])


def test_seasonal_naive_forecaster_fit_predict():
    forecaster = SeasonalNaiveForecaster(seasonal_period=3, lag_col="lag_7")
    y_train = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    forecaster.fit(None, y_train)

    preds = forecaster.predict(np.zeros((5, 1)))
    assert len(preds) == 5
    expected = np.array([4.0, 5.0, 6.0, 4.0, 5.0])
    assert np.allclose(preds, expected)


def test_create_baseline_model_classification():
    dummy = create_baseline_model("dummy", TaskType.BINARY_CLASSIFICATION, strategy="most_frequent")
    X = np.array([[1], [2], [3], [4]])
    y = np.array([0, 0, 0, 1])
    dummy.fit(X, y)
    preds = dummy.predict(X)
    assert len(preds) == 4
    assert np.all(preds == 0)


def test_create_baseline_model_regression():
    dummy = create_baseline_model("dummy", TaskType.REGRESSION)
    X = np.array([[1], [2], [3], [4]])
    y = np.array([10.0, 20.0, 30.0, 40.0])
    dummy.fit(X, y)
    preds = dummy.predict(X)
    assert np.allclose(preds, 25.0)


def test_invalid_baseline_model_name():
    with pytest.raises(ValueError, match="Unknown regression baseline"):
        create_baseline_model("non_existent_baseline", TaskType.REGRESSION)
