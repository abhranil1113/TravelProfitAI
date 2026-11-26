"""
ml_engine/monitoring/data_drift.py

Data quality and feature distribution drift detection.
Calculates Population Stability Index (PSI) and feature shift metrics.
Includes boundary extensions (-inf, +inf) to capture out-of-distribution drift.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


class DataDriftDetector:
    """Computes distribution divergence and feature drift across time windows."""

    @staticmethod
    def calculate_psi(
        baseline: np.ndarray,
        target: np.ndarray,
        num_buckets: int = 10,
        epsilon: float = 1e-4,
    ) -> float:
        """
        Calculates Population Stability Index (PSI) between baseline and target distributions.
        PSI < 0.1: No significant change
        0.1 <= PSI < 0.2: Moderate drift
        PSI >= 0.2: Significant drift, retrain recommended

        Uses open-ended outer buckets (-inf, +inf) so outlier target observations
        are properly counted in distribution divergence calculations.
        """
        b = np.asarray(baseline, dtype=float)
        t = np.asarray(target, dtype=float)

        b = b[np.isfinite(b)]
        t = t[np.isfinite(t)]

        if len(b) < 10 or len(t) < 10:
            return 0.0

        quantiles = np.linspace(0, 100, num_buckets + 1)
        bins = np.percentile(b, quantiles)
        bins = np.unique(bins)

        if len(bins) < 2:
            return 0.0

        # Extend outer bins to open boundaries to capture extreme values
        bins = bins.copy()
        bins[0] = -np.inf
        bins[-1] = np.inf

        b_counts, _ = np.histogram(b, bins=bins)
        t_counts, _ = np.histogram(t, bins=bins)

        b_pct = (b_counts / len(b)) + epsilon
        t_pct = (t_counts / len(t)) + epsilon

        psi_val = float(np.sum((t_pct - b_pct) * np.log(t_pct / b_pct)))
        return float(round(max(0.0, psi_val), 4))
