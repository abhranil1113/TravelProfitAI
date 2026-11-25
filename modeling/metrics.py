"""
TBO InventoryIQ - Centralized Metric Calculation Engine (Phase 4)
Computes mathematically rigorous, safe evaluation metrics across
classification, regression, demand forecasting, and inventory stockout detection.
"""

from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score,
    roc_auc_score,
    precision_score,
    recall_score,
    average_precision_score,
    accuracy_score,
    log_loss,
    confusion_matrix,
    mean_absolute_error,
    root_mean_squared_error,
    r2_score,
)

from modeling.config import TaskType, METRIC_DIRECTION_IS_HIGHER_BETTER


@dataclass
class MetricResult:
    """Encapsulates a computed metric value, optimization direction, and calculation status."""
    name: str
    value: float
    is_higher_better: bool
    status: str = "VALID"
    details: Optional[Dict[str, Any]] = None


# --- Custom Mathematical Metric Formulas with Safe Zero Handling ---

def safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, str]:
    """
    Computes Mean Absolute Percentage Error (MAPE).
    Filters out records where y_true == 0 to prevent division by zero.
    """
    mask = (y_true != 0) & np.isfinite(y_true) & np.isfinite(y_pred)
    if not np.any(mask):
        return float("nan"), "UNDEFINED_ZERO_DENOMINATOR"
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)
    return round(mape, 4), "VALID"


def safe_wape(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, str]:
    """
    Computes Weighted Absolute Percentage Error (WAPE):
    WAPE = sum(|y_true - y_pred|) / sum(y_true) * 100
    Returns NaN with explanatory status if sum(y_true) is zero.
    """
    sum_actual = float(np.sum(np.abs(y_true)))
    if sum_actual <= 0.0:
        return float("nan"), "UNDEFINED_ZERO_TOTAL_DEMAND"
    sum_error = float(np.sum(np.abs(y_true - y_pred)))
    wape = float((sum_error / sum_actual) * 100.0)
    return round(wape, 4), "VALID"


def safe_smape(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, str]:
    """
    Computes Symmetric Mean Absolute Percentage Error (sMAPE):
    sMAPE = 200 * mean(|y_true - y_pred| / (|y_true| + |y_pred|))
    Safely resolves 0 / 0 as 0.0 error.
    """
    denom = np.abs(y_true) + np.abs(y_pred)
    numer = np.abs(y_true - y_pred)
    
    # Where both are zero, error is 0.0
    zero_mask = (denom == 0)
    smape_terms = np.zeros_like(numer, dtype=float)
    non_zero = ~zero_mask
    if np.any(non_zero):
        smape_terms[non_zero] = (numer[non_zero] / denom[non_zero]) * 200.0
    
    return round(float(np.mean(smape_terms)), 4), "VALID"


def compute_forecast_bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Forecast Error: mean(y_pred - y_true). Positive = overprediction."""
    return round(float(np.mean(y_pred - y_true)), 4)


def compute_stockout_recall(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    stockout_threshold: float = 5.0,
) -> Tuple[float, str]:
    """
    Calculates stockout detection recall.
    Actual stockout condition: y_true <= stockout_threshold.
    Predicted stockout condition: y_pred <= stockout_threshold.
    """
    actual_stockout = (y_true <= stockout_threshold).astype(int)
    pred_stockout = (y_pred <= stockout_threshold).astype(int)

    n_actual = int(actual_stockout.sum())
    if n_actual == 0:
        return float("nan"), "NO_ACTUAL_STOCKOUTS"

    rec = float(recall_score(actual_stockout, pred_stockout, zero_division=0))
    return round(rec, 4), "VALID"


def compute_stockout_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    stockout_threshold: float = 5.0,
) -> Dict[str, Tuple[float, str]]:
    """
    Calculates stockout detection recall, precision, and F1 score.
    Actual stockout condition: y_true <= stockout_threshold.
    Predicted stockout condition: y_pred <= stockout_threshold.
    """
    actual_stockout = (y_true <= stockout_threshold).astype(int)
    pred_stockout = (y_pred <= stockout_threshold).astype(int)

    n_actual = int(actual_stockout.sum())
    if n_actual == 0:
        nan_tuple = (float("nan"), "NO_ACTUAL_STOCKOUTS")
        return {
            "stockout_recall": nan_tuple,
            "stockout_precision": nan_tuple,
            "stockout_f1": nan_tuple,
        }

    rec = float(recall_score(actual_stockout, pred_stockout, zero_division=0))
    prec = float(precision_score(actual_stockout, pred_stockout, zero_division=0))
    f1 = float(f1_score(actual_stockout, pred_stockout, zero_division=0))
    return {
        "stockout_recall": (round(rec, 4), "VALID"),
        "stockout_precision": (round(prec, 4), "VALID"),
        "stockout_f1": (round(f1, 4), "VALID"),
    }


def optimize_classification_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    cost_fn: float = 3.0,
    cost_fp: float = 1.0,
    step: float = 0.02,
) -> Dict[str, Any]:
    """
    Searches candidate decision thresholds T in [0.05, 0.95] to minimize total expected business cost:
      Cost(T) = cost_fn * FN + cost_fp * FP
    Returns optimal threshold, minimal cost, and sensitivity curve.
    """
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(y_prob, dtype=float)
    if probs.ndim == 2:
        probs = probs[:, 1]

    n = len(y_true)
    best_th = 0.50
    min_cost = float("inf")
    curve = []

    thresholds = np.arange(0.05, 0.96, step)
    for th in thresholds:
        th_round = round(float(th), 4)
        preds = (probs >= th).astype(int)
        fn = int(((y_true == 1) & (preds == 0)).sum())
        fp = int(((y_true == 0) & (preds == 1)).sum())
        tp = int(((y_true == 1) & (preds == 1)).sum())
        tn = int(((y_true == 0) & (preds == 0)).sum())

        total_cost = float(cost_fn * fn + cost_fp * fp)
        cost_per_instance = float(total_cost / max(1, n))

        prec = float(precision_score(y_true, preds, zero_division=0))
        rec = float(recall_score(y_true, preds, zero_division=0))
        f1 = float(f1_score(y_true, preds, zero_division=0))

        point = {
            "threshold": th_round,
            "total_cost": round(total_cost, 2),
            "cost_per_instance": round(cost_per_instance, 4),
            "fn": fn,
            "fp": fp,
            "tp": tp,
            "tn": tn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
        }
        curve.append(point)

        if total_cost < min_cost:
            min_cost = total_cost
            best_th = th_round

    return {
        "optimal_threshold": best_th,
        "minimal_total_cost": round(min_cost, 2),
        "minimal_cost_per_instance": round(min_cost / max(1, n), 4),
        "cost_fn": cost_fn,
        "cost_fp": cost_fp,
        "threshold_curve": curve,
    }


# --- Master Metric Calculation Dispatchers ---

def evaluate_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
) -> Dict[str, MetricResult]:
    """
    Computes comprehensive classification metrics.
    Gracefully handles single-class folds without fabricating values.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    results = {}

    # Basic Counts
    unique_classes = np.unique(y_true)
    is_binary = len(unique_classes) <= 2

    # Accuracy
    acc = float(accuracy_score(y_true, y_pred))
    results["accuracy"] = MetricResult("accuracy", round(acc, 4), True)

    # Precision, Recall, F1
    avg_mode = "binary" if is_binary else "macro"
    prec = float(precision_score(y_true, y_pred, average=avg_mode, zero_division=0))
    rec = float(recall_score(y_true, y_pred, average=avg_mode, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, average=avg_mode, zero_division=0))

    results["precision"] = MetricResult("precision", round(prec, 4), True)
    results["recall"] = MetricResult("recall", round(rec, 4), True)
    results["f1_score"] = MetricResult("f1_score", round(f1, 4), True)

    # ROC-AUC & PR-AUC (Requires probabilities)
    if y_prob is not None:
        y_prob = np.asarray(y_prob)
        prob_positive = y_prob[:, 1] if y_prob.ndim == 2 and y_prob.shape[1] == 2 else y_prob

        # Single class check
        if len(unique_classes) < 2:
            results["roc_auc"] = MetricResult("roc_auc", float("nan"), True, "UNDEFINED_SINGLE_CLASS")
            results["pr_auc"] = MetricResult("pr_auc", float("nan"), True, "UNDEFINED_SINGLE_CLASS")
            results["log_loss"] = MetricResult("log_loss", float("nan"), False, "UNDEFINED_SINGLE_CLASS")
        else:
            try:
                auc_val = float(roc_auc_score(y_true, prob_positive))
                results["roc_auc"] = MetricResult("roc_auc", round(auc_val, 4), True)
            except Exception as e:
                results["roc_auc"] = MetricResult("roc_auc", float("nan"), True, str(e))

            try:
                pr_auc_val = float(average_precision_score(y_true, prob_positive))
                results["pr_auc"] = MetricResult("pr_auc", round(pr_auc_val, 4), True)
            except Exception as e:
                results["pr_auc"] = MetricResult("pr_auc", float("nan"), True, str(e))

            try:
                loss_val = float(log_loss(y_true, y_prob))
                results["log_loss"] = MetricResult("log_loss", round(loss_val, 4), False)
            except Exception as e:
                results["log_loss"] = MetricResult("log_loss", float("nan"), False, str(e))

    return results


def evaluate_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    is_time_series: bool = False,
    stockout_threshold: Optional[float] = None,
) -> Dict[str, MetricResult]:
    """
    Computes comprehensive regression and time-series forecasting metrics.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    results = {}

    # 1. Standard Regression Metrics
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))

    results["mae"] = MetricResult("mae", round(mae, 4), False)
    results["rmse"] = MetricResult("rmse", round(rmse, 4), False)
    results["r2"] = MetricResult("r2", round(r2, 4), True)

    # 2. Percentage Errors
    mape_val, mape_status = safe_mape(y_true, y_pred)
    results["mape"] = MetricResult("mape", mape_val, False, mape_status)

    # 3. Forecasting Metrics
    wape_val, wape_status = safe_wape(y_true, y_pred)
    results["wape"] = MetricResult("wape", wape_val, False, wape_status)

    smape_val, smape_status = safe_smape(y_true, y_pred)
    results["smape"] = MetricResult("smape", smape_val, False, smape_status)

    bias = compute_forecast_bias(y_true, y_pred)
    results["forecast_bias"] = MetricResult("forecast_bias", bias, False)

    # 4. Stockout Detection Recall, Precision, and F1
    if stockout_threshold is not None:
        so_metrics = compute_stockout_metrics(y_true, y_pred, stockout_threshold)
        results["stockout_recall"] = MetricResult("stockout_recall", so_metrics["stockout_recall"][0], True, so_metrics["stockout_recall"][1])
        results["stockout_precision"] = MetricResult("stockout_precision", so_metrics["stockout_precision"][0], True, so_metrics["stockout_precision"][1])
        results["stockout_f1"] = MetricResult("stockout_f1", so_metrics["stockout_f1"][0], True, so_metrics["stockout_f1"][1])

    return results


def compute_metrics(
    task_type: TaskType,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
    business_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, MetricResult]:
    """
    Universal metric calculation dispatcher driven by TaskType.
    """
    bparams = business_params or {}

    if task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]:
        return evaluate_classification_metrics(y_true, y_pred, y_prob)

    elif task_type in [TaskType.REGRESSION, TaskType.TIME_SERIES_REGRESSION]:
        stockout_th = (
            bparams.get("stockout_threshold_units")
            if bparams.get("stockout_threshold_units") is not None
            else bparams.get("stockout_threshold", None)
        )
        is_ts = task_type == TaskType.TIME_SERIES_REGRESSION
        return evaluate_regression_metrics(
            y_true,
            y_pred,
            is_time_series=is_ts,
            stockout_threshold=stockout_th,
        )

    raise ValueError(f"Unknown task type for metrics computation: {task_type}")
