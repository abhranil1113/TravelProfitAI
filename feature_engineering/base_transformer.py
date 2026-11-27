"""
TBO InventoryIQ - Base Transformer & Mathematical Helpers (Phase 3)
Provides reusable, safe mathematical primitives (safe divide, log transform,
date interval computation, and binning) protecting against ZeroDivisionError and NaN.
"""

from typing import Optional, List, Any
import numpy as np
import pandas as pd


def safe_divide(
    numerator: Any,
    denominator: Any,
    default: float = 0.0,
) -> Any:
    """
    Safely divides two values or series, replacing division by zero and NaNs with default.
    """
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        num_s = pd.to_numeric(numerator, errors="coerce")
        den_s = pd.to_numeric(denominator, errors="coerce")
        result = np.where((den_s != 0) & (~den_s.isna()) & (~num_s.isna()), num_s / den_s, default)
        return pd.Series(result, index=num_s.index if hasattr(num_s, "index") else None)
    
    if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
        return default
    return float(numerator / denominator)


def safe_log1p(series: pd.Series, clip_min: float = 0.0) -> pd.Series:
    """
    Computes natural log1p on non-negative values, safely clipping at clip_min.
    """
    numeric_s = pd.to_numeric(series, errors="coerce")
    clipped = np.maximum(numeric_s.fillna(clip_min), clip_min)
    return np.log1p(clipped)


def safe_date_diff_days(
    end_date: pd.Series,
    start_date: pd.Series,
) -> pd.Series:
    """
    Computes calendar day difference between end_date and start_date.
    Returns NaN for unparseable dates.
    """
    end_dt = pd.to_datetime(end_date, errors="coerce")
    start_dt = pd.to_datetime(start_date, errors="coerce")
    diff_days = (end_dt - start_dt).dt.total_seconds() / (24 * 3600)
    return diff_days


def bin_series(
    series: pd.Series,
    bins: List[float],
    labels: List[str],
) -> pd.Series:
    """
    Categorizes numeric values into predefined bins with fallback for out-of-range values.
    """
    numeric_s = pd.to_numeric(series, errors="coerce")
    binned = pd.cut(
        numeric_s,
        bins=bins,
        labels=labels,
        include_lowest=True,
        right=True,
    )
    return binned.astype("object").fillna("Unknown").astype(str)


class BaseFeatureTransformer:
    """
    Abstract base class for domain-specific feature transformers.
    """
    def __init__(self, name: str):
        self.name = name

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms input DataFrame and returns engineered feature DataFrame."""
        raise NotImplementedError("Subclasses must implement transform().")
