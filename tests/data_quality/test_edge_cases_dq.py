"""
TBO InventoryIQ - Data Quality Edge-Case Verification Suite
Covers empty datasets, extreme nulls, single-row inputs, and corrupted records.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from data_pipeline.ingestion.dataset_loader import load_dataset
from data_pipeline.validation.missing_values import analyze_missing_values
from data_pipeline.validation.duplicate_detection import detect_duplicates
from data_pipeline.validation.outlier_detection import detect_outliers_iqr
from data_pipeline.validation.business_rules import validate_business_rules


def test_missing_values_empty_dataframe():
    """Verify analyze_missing_values handles empty dataframe without division-by-zero."""
    df_empty = pd.DataFrame(columns=["col_a", "col_b"])
    report = analyze_missing_values("generic_dataset", df_empty)
    assert isinstance(report, pd.DataFrame)
    assert len(report) == 2
    assert (report["missing_percentage"] == 0.0).all()
    assert (report["missing_count"] == 0).all()


def test_missing_values_all_nulls():
    """Verify analyze_missing_values computes 100% missingness accurately."""
    df_nulls = pd.DataFrame({
        "col_a": [None, np.nan, None],
        "col_b": [1.0, 2.0, 3.0],
    })
    report = analyze_missing_values("generic_dataset", df_nulls)
    col_a_row = report[report["column_name"] == "col_a"].iloc[0]
    assert col_a_row["missing_count"] == 3
    assert col_a_row["missing_percentage"] == 100.0
    assert bool(col_a_row["is_excessive_missing"]) is True


def test_duplicate_detection_empty_dataframe():
    """Verify duplicate detection on empty dataframe returns zero counts."""
    df_empty = pd.DataFrame(columns=["flight_id", "airline"])
    res = detect_duplicates("flights", df_empty)
    assert res["total_rows"] == 0
    assert res["exact_duplicates"] == 0
    assert res["pk_duplicates"] == 0


def test_duplicate_detection_single_row():
    """Verify single-row dataframe produces 0 duplicates."""
    df_single = pd.DataFrame([{"signal_id": "SIG001", "travel_date": "2026-06-01"}])
    res = detect_duplicates("market_seasonal_signals", df_single)
    assert res["total_rows"] == 1
    assert res["exact_duplicates"] == 0
    assert res["pk_duplicates"] == 0


def test_outlier_detection_iqr_all_nans():
    """Verify IQR outlier detection handles all-NaN series cleanly."""
    nan_series = pd.Series([np.nan, np.nan, np.nan])
    count, q25, q75, iqr, lower, upper = detect_outliers_iqr(nan_series)
    assert count == 0
    assert q25 == 0.0
    assert q75 == 0.0
    assert iqr == 0.0


def test_outlier_detection_iqr_zero_variance():
    """Verify constant numerical series produces zero outliers."""
    const_series = pd.Series([500.0] * 20)
    count, q25, q75, iqr, lower, upper = detect_outliers_iqr(const_series)
    assert count == 0
    assert iqr == 0.0
    assert lower == 500.0
    assert upper == 500.0


def test_business_rules_empty_dataset_dict():
    """Verify validate_business_rules runs cleanly on empty dataset dictionary."""
    violations = validate_business_rules({})
    assert isinstance(violations, pd.DataFrame)
    assert len(violations) == 0


def test_business_rules_partial_datasets():
    """Verify validate_business_rules handles subset of datasets without KeyError."""
    partial = {
        "customer_search_events": pd.DataFrame({
            "search_id": ["S1", "S2"],
            "search_date": ["2026-01-01", "2026-01-02"],
            "travel_date": ["2026-01-05", "2026-01-06"],
            "inventory_type": ["HOTEL", "FLIGHT"],
            "travellers_count": [1, 2],
            "clicked": [1, 0],
            "booking_completed": [1, 0],
            "search_price": [1000.0, 2000.0],
        })
    }
    violations = validate_business_rules(partial)
    assert isinstance(violations, pd.DataFrame)
    assert len(violations) > 0
    assert (violations["violation_count"] == 0).all()


def test_load_dataset_nonexistent_custom_path(tmp_path):
    """Verify load_dataset raises FileNotFoundError for missing custom path."""
    bad_path = tmp_path / "missing_file.csv"
    with pytest.raises(FileNotFoundError):
        load_dataset("airlines", custom_path=bad_path)
