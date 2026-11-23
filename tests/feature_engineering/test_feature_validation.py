"""
Tests for Feature Validation & Quality Assurance Module
"""

import pytest
import pandas as pd
import numpy as np
from feature_engineering.feature_validation import validate_feature_dataset


def test_validate_feature_dataset_passed():
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "lead_time": [10, 20, 30],
        "occupancy_rate": [0.2, 0.5, 0.8],
        "margin_pct": [10.0, 25.0, 50.0],
    })
    res = validate_feature_dataset(
        df,
        "test_dataset",
        key_columns=["id"],
        non_negative_columns=["lead_time"],
        rate_columns_0_to_1=["occupancy_rate"],
        rate_columns_0_to_100=["margin_pct"],
    )
    assert res["status"] == "PASSED"
    assert res["duplicate_keys"] == 0
    assert len(res["issues"]) == 0


def test_validate_feature_dataset_with_violations():
    df = pd.DataFrame({
        "id": [1, 1],  # Duplicate key
        "price": [-50.0, 100.0],  # Negative violation
        "rate": [1.5, 0.5],  # Out of [0, 1] bounds
        "inf_col": [np.inf, 2.0],  # Infinite value
    })
    res = validate_feature_dataset(
        df,
        "test_violation",
        key_columns=["id"],
        non_negative_columns=["price"],
        rate_columns_0_to_1=["rate"],
    )
    assert res["status"] == "PASSED_WITH_WARNINGS"
    assert res["duplicate_keys"] == 1
    assert "price" in res["negative_violations"]
    assert "rate" in res["rate_violations"]
    assert "inf_col" in res["infinite_values"]
