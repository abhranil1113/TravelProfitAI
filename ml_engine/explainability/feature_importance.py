"""
ml_engine/explainability/feature_importance.py

Tree and linear model feature importance extraction and ranking.
"""

from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd


class FeatureImportanceAnalyzer:
    """Extracts, normalizes, and ranks feature importances from trained estimators."""

    @staticmethod
    def extract_importance(
        estimator: Any,
        feature_names: List[str],
        top_n: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Extracts feature importances or coefficients and returns ranked list.
        """
        raw_importances = None

        if hasattr(estimator, "feature_importances_"):
            raw_importances = estimator.feature_importances_
        elif hasattr(estimator, "coef_"):
            raw_importances = np.abs(estimator.coef_).flatten()

        if raw_importances is None:
            return []

        total = float(np.sum(raw_importances)) if np.sum(raw_importances) > 0 else 1.0
        normalized = [float(val / total) for val in raw_importances]

        ranked = []
        for name, norm_val, raw_val in zip(feature_names, normalized, raw_importances):
            ranked.append({
                "feature_name": name,
                "importance_ratio": round(norm_val, 4),
                "raw_importance": float(raw_val),
            })

        ranked.sort(key=lambda x: x["raw_importance"], reverse=True)
        return ranked[:top_n]
