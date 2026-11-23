"""
Tests for EDA Profiling Module
Verifies numerical summarization, IQR calculation, categorical cardinality, and date profiling.
"""

import pytest
import pandas as pd
import numpy as np
from eda.profiling import (
    generate_numerical_summary,
    generate_categorical_summary,
    generate_missing_summary,
    generate_date_span_summary,
    profile_dataset,
)


def test_generate_numerical_summary():
    """Verify numerical statistics generation."""
    test_df = pd.DataFrame({
        "num1": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "num2": [1.5, 2.5, 3.5, np.nan, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5],
        "cat1": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
    })
    summary = generate_numerical_summary(test_df, "test")
    assert len(summary) == 2
    assert "num1" in summary["column"].values
    assert "num2" in summary["column"].values
    
    num1_row = summary[summary["column"] == "num1"].iloc[0]
    assert num1_row["count"] == 10
    assert num1_row["mean"] == 55.0
    assert num1_row["min"] == 10.0
    assert num1_row["max"] == 100.0
    assert num1_row["iqr"] == 45.0


def test_generate_categorical_summary():
    """Verify categorical summary calculation."""
    test_df = pd.DataFrame({
        "category": ["hotel", "flight", "hotel", "hotel", "package", np.nan],
    })
    summary = generate_categorical_summary(test_df, "test")
    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["unique_count"] == 3
    assert row["top_value"] == "hotel"
    assert row["top_freq"] == 3
    assert row["missing_count"] == 1


def test_generate_missing_summary():
    """Verify missing values report."""
    test_df = pd.DataFrame({
        "col_a": [1, 2, np.nan, 4],
        "col_b": ["x", np.nan, np.nan, "y"],
    })
    missing_df = generate_missing_summary(test_df, "test")
    assert len(missing_df) == 2
    a_row = missing_df[missing_df["column"] == "col_a"].iloc[0]
    assert a_row["missing_count"] == 1
    assert a_row["missing_pct"] == 25.0


def test_generate_date_span_summary():
    """Verify calendar date range and day span computation."""
    test_df = pd.DataFrame({
        "date_col": ["2026-01-01", "2026-01-10", "2026-01-05"],
    })
    span = generate_date_span_summary(test_df, "date_col", "test")
    assert span["min_date"] == "2026-01-01"
    assert span["max_date"] == "2026-01-10"
    assert span["calendar_span_days"] == 10
    assert span["unique_dates"] == 3


def test_profile_dataset():
    """Verify full profiling bundle."""
    test_df = pd.DataFrame({
        "num": [1, 2, 3],
        "cat": ["x", "y", "z"],
        "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
    })
    profile = profile_dataset(test_df, "test", date_cols=["date"])
    assert profile["total_rows"] == 3
    assert profile["total_cols"] == 3
    assert "date" in profile["date_profiles"]
