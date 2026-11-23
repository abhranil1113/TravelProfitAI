"""
TBO InventoryIQ - Calendar & Date Feature Extraction (Phase 3)
Extracts temporal, cyclical, weekend, and seasonal indicators from date columns.
"""

from typing import List, Optional
import pandas as pd
import numpy as np

from feature_engineering.config import PEAK_MONTHS


def extract_calendar_features(
    df: pd.DataFrame,
    date_col: str,
    prefix: str = "",
    peak_months: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Extracts rich calendar, day-of-week, quarter, weekend, and peak season indicators.
    
    Args:
        df: Input DataFrame containing date_col.
        date_col: Name of date column to parse.
        prefix: Optional prefix for engineered column names (e.g. 'arrival_', 'departure_').
        peak_months: List of month integers representing peak travel seasonality.
    """
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found in DataFrame.")

    peak_months = peak_months or PEAK_MONTHS
    dt_series = pd.to_datetime(df[date_col], errors="coerce")

    features = pd.DataFrame(index=df.index)
    features[f"{prefix}year"] = dt_series.dt.year.fillna(-1).astype(int)
    features[f"{prefix}month"] = dt_series.dt.month.fillna(-1).astype(int)
    features[f"{prefix}day"] = dt_series.dt.day.fillna(-1).astype(int)
    features[f"{prefix}day_of_week"] = dt_series.dt.dayofweek.fillna(-1).astype(int)
    features[f"{prefix}week_of_year"] = dt_series.dt.isocalendar().week.fillna(-1).astype(int)
    features[f"{prefix}quarter"] = dt_series.dt.quarter.fillna(-1).astype(int)
    
    # Flags
    features[f"{prefix}is_weekend"] = dt_series.dt.dayofweek.isin([5, 6])
    features[f"{prefix}is_peak_season"] = dt_series.dt.month.isin(peak_months)
    features[f"{prefix}is_month_start"] = dt_series.dt.day <= 3
    features[f"{prefix}is_month_end"] = dt_series.dt.day >= 28

    return features
