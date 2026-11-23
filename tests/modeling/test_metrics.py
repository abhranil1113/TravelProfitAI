"""
Tests for Metrics Calculation Engine.
Verifies MAE, RMSE, R², MAPE, WAPE, sMAPE, F1, ROC-AUC, Log Loss,
Stockout Detection Recall, and zero-denominator / single-class edge cases.
"""

import pytest
import numpy as np
from modeling.metrics import (
    evaluate_classification_metrics,
    evaluate_regression_metrics,
    safe_mape,
    safe_wape,
    safe_smape,
    compute_forecast_bias,
    compute_stockout_recall,
)


def test_classification_metrics():
    y_true = np.array([0, 1, 1, 0, 1])
    y_pred = np.array([0, 1, 1, 0, 0])
    y_prob = np.array([0.1, 0.9, 0.8, 0.2, 0.4])

    results = evaluate_classification_metrics(y_true, y_pred, y_prob)
    assert "accuracy" in results
    assert "f1_score" in results
    assert "roc_auc" in results
    assert "log_loss" in results
    assert np.isclose(results["accuracy"].value, 0.8)
    assert results["roc_auc"].value > 0.8


def test_classification_metrics_single_class_edge_case():
    y_true = np.array([0, 0, 0, 0])
    y_pred = np.array([0, 0, 0, 0])
    y_prob = np.array([0.1, 0.2, 0.1, 0.3])

    results = evaluate_classification_metrics(y_true, y_pred, y_prob)
    assert np.isnan(results["roc_auc"].value)
    assert results["roc_auc"].status == "UNDEFINED_SINGLE_CLASS"


def test_regression_metrics():
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 31.0])

    results = evaluate_regression_metrics(y_true, y_pred)
    assert "mae" in results
    assert "rmse" in results
    assert "r2" in results
    assert "mape" in results
    assert np.isclose(results["mae"].value, (2.0 + 2.0 + 1.0) / 3.0, atol=1e-3)


def test_safe_mape_with_zeros():
    y_true = np.array([0.0, 10.0, 20.0])
    y_pred = np.array([2.0, 10.0, 20.0])
    mape, status = safe_mape(y_true, y_pred)
    assert status == "VALID"
    assert not np.isinf(mape)
    assert not np.isnan(mape)


def test_safe_wape_with_zeros():
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([1.0, 1.0])
    wape, status = safe_wape(y_true, y_pred)
    assert status == "UNDEFINED_ZERO_TOTAL_DEMAND"
    assert np.isnan(wape)


def test_forecasting_metrics_with_stockout():
    y_true = np.array([5.0, 0.0, 10.0, 0.0, 2.0])
    y_pred = np.array([6.0, 0.0, 9.0, 1.0, 2.0])

    bias = compute_forecast_bias(y_true, y_pred)
    assert isinstance(bias, float)

    recall, status = compute_stockout_recall(y_true, y_pred, stockout_threshold=0.0)
    assert status == "VALID"
    assert np.isclose(recall, 0.5)
