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
from modeling.metrics import compute_metrics, MetricResult


def evaluate_test_set(
    task_config: TaskConfig,
    artifact: ModelArtifact,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Dict[str, Any]:
    """
    Executes full offline evaluation on an untouched test holdout set.
    """
    y_test_arr = y_test.to_numpy()
    preds, inf_time = artifact.predict(X_test)
    probs = artifact.predict_proba(X_test) if task_config.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION] else None

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
        "metrics": metric_values,
    }

    # 2. Classification Diagnostics
    if task_config.task_type == TaskType.BINARY_CLASSIFICATION:
        cm = confusion_matrix(y_test_arr, preds)
        evaluation_report["confusion_matrix"] = cm.tolist()
        evaluation_report["classification_report"] = classification_report(
            y_test_arr, preds, output_dict=True, zero_division=0
        )
        if probs is not None:
            # Threshold sensitivity analysis
            threshold_analysis = []
            pos_probs = probs[:, 1] if probs.ndim == 2 else probs
            for th in [0.3, 0.4, 0.5, 0.6, 0.7]:
                th_preds = (pos_probs >= th).astype(int)
                from sklearn.metrics import f1_score, precision_score, recall_score
                th_f1 = float(f1_score(y_test_arr, th_preds, zero_division=0))
                th_p = float(precision_score(y_test_arr, th_preds, zero_division=0))
                th_r = float(recall_score(y_test_arr, th_preds, zero_division=0))
                threshold_analysis.append({
                    "threshold": th,
                    "f1_score": round(th_f1, 4),
                    "precision": round(th_p, 4),
                    "recall": round(th_r, 4),
                })
            evaluation_report["threshold_sensitivity"] = threshold_analysis

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

    # 4. Demand Forecasting Diagnostics
    elif task_config.task_type == TaskType.TIME_SERIES_REGRESSION:
        residuals = preds - y_test_arr
        evaluation_report["forecast_diagnostics"] = {
            "mean_bias": round(float(np.mean(residuals)), 4),
            "overprediction_rate": round(float((residuals > 0).mean()), 4),
            "underprediction_rate": round(float((residuals < 0).mean()), 4),
        }
        if "stockout_recall" in metric_values:
            evaluation_report["stockout_diagnostics"] = {
                "stockout_threshold": task_config.business_params.get("stockout_threshold_units", 5.0),
                "stockout_recall": metric_values["stockout_recall"],
            }

    return evaluation_report
