"""
TBO InventoryIQ - Comprehensive Model Evaluator (Phase 4)
Computes diagnostic evaluations on untouched test sets: residuals,
confusion matrices, threshold comparisons, and domain-specific breakdown analyses.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report

from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.trainer import ModelArtifact
from modeling.metrics import compute_metrics, MetricResult, optimize_classification_threshold, evaluate_regression_metrics


def evaluate_test_set(
    task_config: TaskConfig,
    artifact: ModelArtifact,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    frozen_threshold: Optional[float] = None,
    threshold_selection_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes full offline evaluation on an untouched test holdout set.
    Zero-leakage guarantee: decision thresholds are passed as frozen values
    selected on validation data; final test labels are never used to optimize thresholds.
    """
    y_test_arr = y_test.to_numpy()
    preds, inf_time = artifact.predict(X_test)
    probs = artifact.predict_proba(X_test) if task_config.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION] else None

    # Apply frozen decision threshold if provided for binary classification
    applied_threshold = 0.50
    if task_config.task_type == TaskType.BINARY_CLASSIFICATION and frozen_threshold is not None and probs is not None:
        applied_threshold = float(frozen_threshold)
        pos_probs = probs[:, 1] if probs.ndim == 2 else probs
        preds = (pos_probs >= applied_threshold).astype(int)

    # 1. Base Metrics
    metrics_obj = compute_metrics(
        task_config.task_type,
        y_test_arr,
        preds,
        y_prob=probs,
        business_params=task_config.business_params,
    )
    metric_values = {k: v.value for k, v in metrics_obj.items()}

    evaluation_report = {
        "task_name": task_config.task_name,
        "model_name": artifact.model_name,
        "test_records_count": len(X_test),
        "inference_duration_seconds": round(inf_time, 4),
        "applied_decision_threshold": round(applied_threshold, 4),
        "metrics": metric_values,
    }

    # 2. Classification Diagnostics
    if task_config.task_type == TaskType.BINARY_CLASSIFICATION:
        cm = confusion_matrix(y_test_arr, preds)
        evaluation_report["confusion_matrix"] = cm.tolist()
        evaluation_report["classification_report"] = classification_report(
            y_test_arr, preds, output_dict=True, zero_division=0
        )
        if threshold_selection_metadata is not None:
            evaluation_report["threshold_provenance"] = threshold_selection_metadata

    # 3. Regression & Flight Price Diagnostics
    elif task_config.task_type == TaskType.REGRESSION:
        residuals = preds - y_test_arr
        evaluation_report["residual_diagnostics"] = {
            "mean_residual": round(float(np.mean(residuals)), 4),
            "std_residual": round(float(np.std(residuals)), 4),
            "median_residual": round(float(np.median(residuals)), 4),
        }
        # Check for booking horizon breakdown if present
        if "days_left" in X_test.columns:
            horizon_errors = {}
            for label, mask in [
                ("immediate_1_7d", X_test["days_left"] <= 7),
                ("intermediate_8_14d", (X_test["days_left"] >= 8) & (X_test["days_left"] <= 14)),
                ("advance_15d_plus", X_test["days_left"] >= 15),
            ]:
                if mask.any():
                    sub_mae = float(np.mean(np.abs(preds[mask] - y_test_arr[mask])))
                    horizon_errors[label] = round(sub_mae, 2)
            evaluation_report["horizon_mae_inr"] = horizon_errors

    # 4. Demand & Inventory Forecasting Diagnostics
    elif task_config.task_type == TaskType.TIME_SERIES_REGRESSION:
        residuals = preds - y_test_arr
        evaluation_report["forecast_diagnostics"] = {
            "mean_bias": round(float(np.mean(residuals)), 4),
            "overprediction_rate": round(float((residuals > 0).mean()), 4),
            "underprediction_rate": round(float((residuals < 0).mean()), 4),
        }

        # Deterministic safeguard: track silent all-zero predictions
        is_all_zero = bool(np.all(preds == 0.0))
        zero_pred_pct = round(float(np.mean(preds == 0.0) * 100), 2)
        nonzero_targets = int(np.sum(y_test_arr > 0))
        if is_all_zero and nonzero_targets > 0:
            logger.critical(
                f"SAFEGUARD TRIGGERED: Model '{artifact.model_name}' produced all-zero predictions "
                f"(100% 0.0) on test set containing {nonzero_targets} non-zero demand events!"
            )
        evaluation_report["zero_prediction_diagnostics"] = {
            "is_all_zero_predictions": is_all_zero,
            "zero_prediction_pct": zero_pred_pct,
            "actual_zero_target_pct": round(float(np.mean(y_test_arr == 0.0) * 100), 2),
            "nonzero_target_count": nonzero_targets,
        }

        # Nonzero demand performance metrics
        nonzero_mask = (y_test_arr > 0)
        if np.any(nonzero_mask):
            nz_true = y_test_arr[nonzero_mask]
            nz_pred = preds[nonzero_mask]
            evaluation_report["nonzero_demand_diagnostics"] = {
                "count": int(nonzero_mask.sum()),
                "mae": round(float(np.mean(np.abs(nz_true - nz_pred))), 4),
                "rmse": round(float(np.sqrt(np.mean((nz_true - nz_pred)**2))), 4),
                "wape": round(float(np.sum(np.abs(nz_true - nz_pred)) / np.sum(nz_true) * 100), 2),
                "bias": round(float(np.mean(nz_pred - nz_true)), 4),
            }

        if "stockout_recall" in metric_values:
            evaluation_report["stockout_diagnostics"] = {
                "stockout_threshold": (
                    task_config.business_params.get("stockout_threshold_units")
                    or task_config.business_params.get("stockout_threshold", 5.0)
                ),
                "stockout_recall": metric_values.get("stockout_recall"),
                "stockout_precision": metric_values.get("stockout_precision"),
                "stockout_f1": metric_values.get("stockout_f1"),
            }
        # Separate evaluation for room-night vs flight-seat units
        if "unit_type" in X_test.columns:
            unit_eval = {}
            for utype in X_test["unit_type"].unique():
                u_mask = (X_test["unit_type"] == utype).to_numpy()
                if np.any(u_mask):
                    u_true = y_test_arr[u_mask]
                    u_pred = preds[u_mask]
                    u_metrics = evaluate_regression_metrics(
                        u_true,
                        u_pred,
                        is_time_series=True,
                        stockout_threshold=(
                            task_config.business_params.get("stockout_threshold_units")
                            or task_config.business_params.get("stockout_threshold", 5.0)
                        ),
                    )
                    unit_eval[str(utype)] = {k: v.value for k, v in u_metrics.items()}
            evaluation_report["unit_type_breakdown"] = unit_eval

    return evaluation_report
