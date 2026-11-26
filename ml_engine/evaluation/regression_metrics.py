"""
ml_engine/evaluation/regression_metrics.py

Comprehensive regression evaluation metrics with zero-denominator safeguards.
"""

from typing import Dict, Any, Union
import numpy as np


class RegressionMetrics:
    """Calculates evaluation metrics for continuous regression and forecasting predictions."""

    @staticmethod
    def calculate_all(y_true: Union[np.ndarray, list], y_pred: Union[np.ndarray, list]) -> Dict[str, float]:
        """
        Computes MAE, RMSE, R2, MAPE, WAPE, SMAPE, and Forecast Bias.
        """
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)

        if len(yt) == 0:
            return {"mae": 0.0, "rmse": 0.0, "r2": 0.0, "wape": 0.0, "smape": 0.0, "bias": 0.0}

        errors = yt - yp
        abs_errors = np.abs(errors)

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        bias = float(np.mean(yp - yt))

        # R-squared
        ss_res = float(np.sum(errors ** 2))
        ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
        r2 = float(1.0 - (ss_res / max(1e-9, ss_tot)))

        # WAPE (Weighted Absolute Percentage Error): sum(|yt - yp|) / sum(|yt|)
        sum_actual = float(np.sum(np.abs(yt)))
        wape = float((np.sum(abs_errors) / max(1e-9, sum_actual)) * 100.0)

        # SMAPE: 2 * |yt - yp| / (|yt| + |yp|)
        denom = np.abs(yt) + np.abs(yp)
        nonzero_mask = denom > 1e-9
        smape = float(np.mean(2.0 * abs_errors[nonzero_mask] / denom[nonzero_mask]) * 100.0) if np.any(nonzero_mask) else 0.0

        # MAPE (masked for actual > 0)
        pos_mask = np.abs(yt) > 1e-6
        mape = float(np.mean(abs_errors[pos_mask] / np.abs(yt[pos_mask])) * 100.0) if np.any(pos_mask) else 0.0

        return {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "r2": round(r2, 4),
            "mape": round(mape, 2),
            "wape": round(wape, 2),
            "smape": round(smape, 2),
            "forecast_bias": round(bias, 4),
        }
