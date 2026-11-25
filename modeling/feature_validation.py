"""
TBO InventoryIQ - Modeling Feature Validation (Phase 4)
Validates predictor matrix integrity: checks for infinite values,
high missingness, zero variance (constant features), and invalid types.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def validate_modeling_features(
    X: pd.DataFrame,
    max_missing_pct: float = 50.0,
    check_constants: bool = True,
    fail_closed: bool = True,
) -> Dict[str, Any]:
    """
    Audits candidate predictor matrix X before model training.
    Returns structured validation report with detected anomalies.
    If fail_closed is True, raises ValueError when critical violations are found.
    """
    n_rows, n_cols = X.shape
    if n_rows == 0 or n_cols == 0:
        raise ValueError(f"Predictor matrix X is empty: {n_rows} rows, {n_cols} columns.")

    # 1. Missing Value Checks
    missing_counts = X.isnull().sum()
    missing_pcts = (missing_counts / n_rows) * 100.0
    high_missing_cols = missing_pcts[missing_pcts > max_missing_pct].to_dict()

    # 2. Infinite Value Checks on Numerical Columns
    num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    inf_cols = {}
    if num_cols:
        inf_counts = np.isinf(X[num_cols]).sum()
        inf_cols = inf_counts[inf_counts > 0].to_dict()

    # 3. Constant Features (Zero Variance)
    constant_cols = []
    if check_constants:
        for c in X.columns:
            if X[c].nunique(dropna=False) <= 1:
                constant_cols.append(c)

    # 4. Partition Categorical vs Numerical
    cat_cols = X.select_dtypes(include=["object", "category", "string", "bool"]).columns.tolist()

    is_valid = len(high_missing_cols) == 0 and len(inf_cols) == 0

    report = {
        "is_valid": is_valid,
        "row_count": n_rows,
        "column_count": n_cols,
        "numerical_columns_count": len(num_cols),
        "categorical_columns_count": len(cat_cols),
        "numerical_columns": num_cols,
        "categorical_columns": cat_cols,
        "high_missing_columns": high_missing_cols,
        "infinite_value_columns": inf_cols,
        "constant_columns": constant_cols,
    }

    if not is_valid:
        msg = f"Feature validation flagged issues: high_missing={high_missing_cols}, inf={inf_cols}"
        logger.warning(msg)
        if fail_closed:
            raise ValueError(f"Feature validation gate failed: {msg}")

    return report
