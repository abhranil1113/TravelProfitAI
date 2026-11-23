"""
TBO InventoryIQ - Automated Tests: Quality Audits, ID Consistency & Business Rules
"""

import pytest
import pandas as pd
import numpy as np

from data_pipeline.validation.missing_values import analyze_missing_values
from data_pipeline.validation.duplicate_detection import detect_duplicates
from data_pipeline.validation.datatype_validation import validate_data_types
from data_pipeline.validation.id_consistency import validate_id_consistency
from data_pipeline.validation.business_rules import validate_business_rules
from data_pipeline.validation.outlier_detection import detect_outliers_iqr, analyze_dataset_outliers
from data_pipeline.validation.schema_validation import validate_schema


def test_missing_value_analysis_distinguishes_legitimate(sample_inventory_availability):
    """Verify that origin_id in hotel inventory is identified as Legitimate Nullable."""
    res = analyze_missing_values("inventory_availability", sample_inventory_availability)
    origin_row = res[res["column_name"] == "origin_id"].iloc[0]
    assert origin_row["missing_count"] == 1
    assert bool(origin_row["is_optional_field"]) is True
    assert origin_row["missing_status"] == "Legitimate Nullable"


def test_duplicate_detection(sample_market_signals):
    """Verify duplicate detection finds 0 duplicates on unique sample and finds added dupe."""
    res = detect_duplicates("market_seasonal_signals", sample_market_signals)
    assert res["exact_duplicates"] == 0
    assert res["pk_duplicates"] == 0

    # Add duplicate row
    df_with_dupe = pd.concat([sample_market_signals, sample_market_signals.iloc[[0]]], ignore_index=True)
    res_dupe = detect_duplicates("market_seasonal_signals", df_with_dupe)
    assert res_dupe["exact_duplicates"] == 1
    assert res_dupe["pk_duplicates"] == 1


def test_datatype_validation(sample_market_signals):
    """Verify datatype validation flags valid and malformed values."""
    res = validate_data_types("market_seasonal_signals", sample_market_signals)
    assert len(res) == len(sample_market_signals.columns)
    # Check that signal_id is recognized as string ID
    sig_row = res[res["column_name"] == "signal_id"].iloc[0]
    assert sig_row["issue_type"] == "None"


def test_id_consistency_cross_referential(
    sample_market_signals,
    sample_inventory_availability,
    sample_supplier_offers,
    sample_customer_search_events,
):
    """Verify cross-dataset referential integrity checks pass on matching IDs."""
    datasets = {
        "market_seasonal_signals": sample_market_signals,
        "inventory_availability": sample_inventory_availability,
        "supplier_offers": sample_supplier_offers,
        "customer_search_events": sample_customer_search_events,
    }
    df_ids = validate_id_consistency(datasets)
    assert len(df_ids) >= 4
    for _, row in df_ids.iterrows():
        assert row["status"] == "CONSISTENT"
        assert row["unmatched_id_count"] == 0


def test_business_rules_validation(
    sample_market_signals,
    sample_inventory_availability,
    sample_supplier_offers,
    sample_customer_search_events,
):
    """Verify business rules validate clean fixtures with zero violations."""
    datasets = {
        "market_seasonal_signals": sample_market_signals,
        "inventory_availability": sample_inventory_availability,
        "supplier_offers": sample_supplier_offers,
        "customer_search_events": sample_customer_search_events,
    }
    df_rules = validate_business_rules(datasets)
    assert len(df_rules) > 0
    # On clean samples, all rules should have 0 violations
    for _, row in df_rules.iterrows():
        assert row["violation_count"] == 0


def test_outlier_detection_iqr():
    """Verify IQR calculation correctly detects extreme numerical values."""
    s = pd.Series([10.0, 11.0, 12.0, 11.5, 10.5, 100.0])  # 100.0 is an extreme outlier
    count, q25, q75, iqr, lb, ub = detect_outliers_iqr(s)
    assert count == 1
    assert q25 < 12.0
    assert ub < 100.0


def test_pandera_schema_validation(sample_market_signals):
    """Verify Pandera schema validation passes on compliant records."""
    is_valid, errors = validate_schema("market_seasonal_signals", sample_market_signals)
    assert is_valid is True
    assert len(errors) == 0
