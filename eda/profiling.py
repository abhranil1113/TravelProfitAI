"""
TBO InventoryIQ - Systematic Data Profiling Library (Phase 2)
Produces statistical summaries, missingness analysis, cardinality checks,
and date range distributions across processed datasets.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np


def generate_numerical_summary(df: pd.DataFrame, dataset_name: str = "") -> pd.DataFrame:
    """
    Computes comprehensive numerical statistics including standard quantiles,
    interquartile range (IQR), skewness, and kurtosis.
    """
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return pd.DataFrame()

    summary_records = []
    total_rows = len(df)

    for col in numeric_df.columns:
        s = numeric_df[col].dropna()
        n = len(s)
        missing = total_rows - n
        missing_pct = round((missing / total_rows) * 100, 2) if total_rows > 0 else 0.0

        if n > 0:
            mean_val = s.mean()
            std_val = s.std()
            min_val = s.min()
            q25 = s.quantile(0.25)
            median_val = s.median()
            q75 = s.quantile(0.75)
            max_val = s.max()
            iqr = q75 - q25
            skew = s.skew() if n >= 3 else np.nan
            kurt = s.kurtosis() if n >= 4 else np.nan
        else:
            mean_val = std_val = min_val = q25 = median_val = q75 = max_val = iqr = skew = kurt = np.nan

        summary_records.append({
            "dataset": dataset_name,
            "column": col,
            "count": n,
            "missing_count": missing,
            "missing_pct": missing_pct,
            "mean": round(mean_val, 4) if pd.notnull(mean_val) else np.nan,
            "std": round(std_val, 4) if pd.notnull(std_val) else np.nan,
            "min": round(min_val, 4) if pd.notnull(min_val) else np.nan,
            "25%": round(q25, 4) if pd.notnull(q25) else np.nan,
            "50%": round(median_val, 4) if pd.notnull(median_val) else np.nan,
            "75%": round(q75, 4) if pd.notnull(q75) else np.nan,
            "max": round(max_val, 4) if pd.notnull(max_val) else np.nan,
            "iqr": round(iqr, 4) if pd.notnull(iqr) else np.nan,
            "skewness": round(skew, 4) if pd.notnull(skew) else np.nan,
            "kurtosis": round(kurt, 4) if pd.notnull(kurt) else np.nan,
        })

    return pd.DataFrame(summary_records)


def generate_categorical_summary(df: pd.DataFrame, dataset_name: str = "") -> pd.DataFrame:
    """
    Computes cardinality and top frequency metrics for categorical/string columns.
    """
    cat_df = df.select_dtypes(include=["object", "category", "bool"])
    if cat_df.empty:
        return pd.DataFrame()

    total_rows = len(df)
    summary_records = []

    for col in cat_df.columns:
        s = cat_df[col]
        missing = int(s.isnull().sum())
        missing_pct = round((missing / total_rows) * 100, 2) if total_rows > 0 else 0.0
        unique_cnt = int(s.nunique(dropna=True))
        unique_pct = round((unique_cnt / total_rows) * 100, 2) if total_rows > 0 else 0.0

        val_counts = s.value_counts(dropna=True)
        if not val_counts.empty:
            top_val = str(val_counts.index[0])
            top_freq = int(val_counts.iloc[0])
            top_pct = round((top_freq / total_rows) * 100, 2) if total_rows > 0 else 0.0
        else:
            top_val = "N/A"
            top_freq = 0
            top_pct = 0.0

        summary_records.append({
            "dataset": dataset_name,
            "column": col,
            "unique_count": unique_cnt,
            "unique_pct": unique_pct,
            "top_value": top_val,
            "top_freq": top_freq,
            "top_pct": top_pct,
            "missing_count": missing,
            "missing_pct": missing_pct,
        })

    return pd.DataFrame(summary_records)


def generate_missing_summary(df: pd.DataFrame, dataset_name: str = "") -> pd.DataFrame:
    """
    Generates a missing-value report for all columns in the dataset.
    """
    total_rows = len(df)
    records = []
    for col in df.columns:
        missing = int(df[col].isnull().sum())
        missing_pct = round((missing / total_rows) * 100, 2) if total_rows > 0 else 0.0
        records.append({
            "dataset": dataset_name,
            "column": col,
            "dtype": str(df[col].dtype),
            "total_rows": total_rows,
            "missing_count": missing,
            "missing_pct": missing_pct,
        })
    return pd.DataFrame(records)


def generate_date_span_summary(
    df: pd.DataFrame,
    date_col: str,
    dataset_name: str = "",
) -> Dict[str, Any]:
    """
    Calculates date span bounds, total elapsed calendar days, and density.
    """
    if date_col not in df.columns:
        return {"error": f"Column {date_col} not found in {dataset_name}"}

    dt_series = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if dt_series.empty:
        return {
            "dataset": dataset_name,
            "date_column": date_col,
            "status": "No valid dates found",
            "min_date": None,
            "max_date": None,
            "calendar_span_days": 0,
            "unique_dates": 0,
        }

    min_date = dt_series.min()
    max_date = dt_series.max()
    span_days = (max_date - min_date).days + 1
    unique_dates = int(dt_series.dt.date.nunique())

    return {
        "dataset": dataset_name,
        "date_column": date_col,
        "min_date": min_date.strftime("%Y-%m-%d"),
        "max_date": max_date.strftime("%Y-%m-%d"),
        "calendar_span_days": span_days,
        "unique_dates": unique_dates,
        "total_records": len(dt_series),
    }


def profile_dataset(
    df: pd.DataFrame,
    dataset_name: str,
    date_cols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates a complete profiling bundle for a single dataset.
    """
    date_profiles = {}
    if date_cols:
        for dc in date_cols:
            if dc in df.columns:
                date_profiles[dc] = generate_date_span_summary(df, dc, dataset_name)

    return {
        "dataset_name": dataset_name,
        "total_rows": len(df),
        "total_cols": len(df.columns),
        "numerical_summary": generate_numerical_summary(df, dataset_name),
        "categorical_summary": generate_categorical_summary(df, dataset_name),
        "missing_summary": generate_missing_summary(df, dataset_name),
        "date_profiles": date_profiles,
    }
