"""
Tests for Feature Matrix Validation.
Verifies missing value detection, infinite value handling, constant column identification,
and validation error reporting.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.feature_validation import validate_modeling_features


def test_validate_clean_matrix():
    df = pd.DataFrame({
        "feat_a": [1.0, 2.0, 3.0, 4.0],
        "feat_b": [10.0, 20.0, 30.0, 40.0],
    })
    report = validate_modeling_features(df, max_missing_pct=50.0, check_constants=True)
    assert report["is_valid"] is True
    assert len(report["high_missing_columns"]) == 0
    assert len(report["infinite_value_columns"]) == 0
    assert len(report["constant_columns"]) == 0


def test_detect_infinite_values():
    df = pd.DataFrame({
        "feat_a": [1.0, np.inf, 3.0, 4.0],
        "feat_b": [10.0, 20.0, 30.0, 40.0],
    })
    report = validate_modeling_features(df)
    assert report["is_valid"] is False
    assert "feat_a" in report["infinite_value_columns"]


def test_detect_constant_columns():
    df = pd.DataFrame({
        "feat_a": [1.0, 1.0, 1.0, 1.0],  # Constant
        "feat_b": [10.0, 20.0, 30.0, 40.0],
    })
    report = validate_modeling_features(df, check_constants=True)
    assert "feat_a" in report["constant_columns"]


def test_detect_high_missingness():
    # 75% missingness (3 out of 4)
    df = pd.DataFrame({
        "feat_a": [1.0, np.nan, np.nan, np.nan],
        "feat_b": [10.0, 20.0, 30.0, 40.0],
    })
    report = validate_modeling_features(df, max_missing_pct=50.0)
    assert report["is_valid"] is False
    assert "feat_a" in report["high_missing_columns"]


def test_empty_dataframe_raises():
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="is empty"):
        validate_modeling_features(df)
