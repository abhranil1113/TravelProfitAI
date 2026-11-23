"""
TBO InventoryIQ - Missing Value Detection & Analysis
Calculates missing-value metrics, flags excessive missingness, and evaluates business legitimacy.
"""

from typing import Dict, List, Any
import pandas as pd
from data_pipeline.config import LEGITIMATE_NULL_FIELDS


def analyze_missing_values(
    dataset_name: str,
    df: pd.DataFrame,
    stage: str = "raw",
    excessive_threshold_pct: float = 50.0,
) -> pd.DataFrame:
    """
    Analyzes missing values for a given dataset at a specific pipeline stage (raw or processed).
    Returns a DataFrame with column-by-column missing statistics and classification.
    """
    total_rows = len(df)
    results = []

    legitimate_dict = LEGITIMATE_NULL_FIELDS.get(dataset_name, {})

    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        # Exact formula: missing_percentage = (missing_count / total_rows) * 100
        null_pct = round((null_count / total_rows * 100), 4) if total_rows > 0 else 0.0

        is_legitimate = col in legitimate_dict
        justification = legitimate_dict.get(col, "Mandatory field / unexpected missing value")

        is_excessive = null_pct >= excessive_threshold_pct
        status = "Clean"
        if null_count > 0:
            if is_legitimate:
                status = "Legitimate Nullable"
            else:
                status = "Unexpected Missing"

        results.append({
            "stage": stage,
            "dataset_name": dataset_name,
            "column_name": col,
            "total_rows": total_rows,
            "missing_count": null_count,
            "missing_percentage": null_pct,
            "is_optional_field": bool(is_legitimate),
            "is_excessive_missing": bool(is_excessive),
            "missing_status": status,
            "business_justification": justification if null_count > 0 else "N/A - Fully Populated",
        })

    return pd.DataFrame(results)


def analyze_all_missing_values(
    datasets: Dict[str, pd.DataFrame],
    stage: str = "raw",
    excessive_threshold_pct: float = 50.0,
) -> pd.DataFrame:
    """
    Run missing value analysis across all datasets and combine into a single report DataFrame.
    """
    reports = []
    for name, df in datasets.items():
        rep = analyze_missing_values(name, df, stage=stage, excessive_threshold_pct=excessive_threshold_pct)
        reports.append(rep)
    
    if reports:
        return pd.concat(reports, ignore_index=True)
    return pd.DataFrame()
