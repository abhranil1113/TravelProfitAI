"""
TBO InventoryIQ - Feature Validation & Quality Assurance (Phase 3)
Audits engineered features for mathematical consistency, nulls, infinities,
forbidden negative values, bounded rates, and key uniqueness.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np


def validate_feature_dataset(
    df: pd.DataFrame,
    dataset_name: str,
    key_columns: Optional[List[str]] = None,
    non_negative_columns: Optional[List[str]] = None,
    rate_columns_0_to_1: Optional[List[str]] = None,
    rate_columns_0_to_100: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Performs comprehensive quality, boundary, and mathematical validation on an engineered dataset.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    issues: List[str] = []

    if total_rows == 0:
        return {
            "dataset_name": dataset_name,
            "status": "FAILED",
            "error": "Dataset is empty.",
            "total_rows": 0,
            "total_cols": total_cols,
        }

    # 1. Key Uniqueness Check
    duplicate_keys_count = 0
    if key_columns:
        valid_keys = [k for k in key_columns if k in df.columns]
        if valid_keys:
            duplicate_keys_count = int(df.duplicated(subset=valid_keys).sum())
            if duplicate_keys_count > 0:
                issues.append(f"Found {duplicate_keys_count} duplicate keys on {valid_keys}.")

    # 2. Infinite Values Check
    numeric_df = df.select_dtypes(include=[np.number])
    inf_counts = {}
    for col in numeric_df.columns:
        infs = int(np.isinf(numeric_df[col]).sum())
        if infs > 0:
            inf_counts[col] = infs
            issues.append(f"Column '{col}' contains {infs} infinite values.")

    # 3. Missingness Audit
    missing_summary = {}
    for col in df.columns:
        n_missing = int(df[col].isnull().sum())
        pct = round((n_missing / total_rows) * 100, 2)
        if n_missing > 0:
            missing_summary[col] = {"missing_count": n_missing, "missing_pct": pct}

    # 4. Non-Negative Constraints Check
    negative_violations = {}
    if non_negative_columns:
        for col in non_negative_columns:
            if col in df.columns:
                negs = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())
                if negs > 0:
                    negative_violations[col] = negs
                    issues.append(f"Column '{col}' has {negs} invalid negative values.")

    # 5. Rate Bounds Checks
    rate_violations = {}
    if rate_columns_0_to_1:
        for col in rate_columns_0_to_1:
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                out_of_bounds = int(((vals < 0.0) | (vals > 1.0)).sum())
                if out_of_bounds > 0:
                    rate_violations[col] = out_of_bounds
                    issues.append(f"Rate column '{col}' has {out_of_bounds} values outside [0.0, 1.0].")

    if rate_columns_0_to_100:
        for col in rate_columns_0_to_100:
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                out_of_bounds = int(((vals < 0.0) | (vals > 100.0)).sum())
                if out_of_bounds > 0:
                    rate_violations[col] = out_of_bounds
                    issues.append(f"Percentage column '{col}' has {out_of_bounds} values outside [0, 100].")

    status = "PASSED" if len(issues) == 0 else "PASSED_WITH_WARNINGS"

    return {
        "dataset_name": dataset_name,
        "status": status,
        "total_rows": total_rows,
        "total_cols": total_cols,
        "duplicate_keys": duplicate_keys_count,
        "infinite_values": inf_counts,
        "missing_columns_count": len(missing_summary),
        "missing_details": missing_summary,
        "negative_violations": negative_violations,
        "rate_violations": rate_violations,
        "issues": issues,
    }
