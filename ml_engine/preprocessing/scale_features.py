"""
ml_engine/preprocessing/scale_features.py

Numerical feature scaling, boundary clamping, and finite-value validation.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd


class NumericScalerValidator:
    """Clamps numeric outliers and bounds features within production domains."""

    @staticmethod
    def clamp_numeric_bounds(
        df: pd.DataFrame,
        bounds: Dict[str, Tuple[Optional[float], Optional[float]]],
    ) -> pd.DataFrame:
        """
        Clamps numeric features between optional (min_val, max_val).
        """
        out = df.copy()
        for col, (min_val, max_val) in bounds.items():
            if col in out.columns:
                if min_val is not None:
                    out[col] = out[col].clip(lower=min_val)
                if max_val is not None:
                    out[col] = out[col].clip(upper=max_val)
        return out
