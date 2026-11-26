"""
TBO InventoryIQ - EDA Edge-Case Verification Suite
Covers empty dataframes, zero-denominators, zero variance distributions,
and non-finite statistical values across EDA engines.
"""

import pytest
import pandas as pd
import numpy as np

from eda.kpi_calculations import (
    safe_divide,
    compute_search_kpis,
    compute_inventory_kpis,
    compute_supplier_kpis,
    compute_hotel_kpis,
    compute_flight_operations_kpis,
    compute_flight_price_kpis,
)
from eda.statistical_analysis import (
    detect_outliers_iqr,
    detect_outliers_zscore,
    compute_correlation_matrix,
)


def test_safe_divide_edge_cases():
    """Verify safe_divide behaves correctly on all mathematical boundary values."""
    assert safe_divide(0.0, 0.0) == 0.0
    assert safe_divide(100.0, 0.0, default=-1.0) == -1.0
    assert safe_divide(float("nan"), 10.0) == 0.0
    assert safe_divide(10.0, float("nan")) == 0.0
    assert safe_divide(-50.0, 5.0) == -10.0
    assert safe_divide(-50.0, -5.0) == 10.0


def test_search_kpis_empty_dataset():
    """Verify compute_search_kpis handles 0-row dataset safely."""
    df_empty = pd.DataFrame()
    res = compute_search_kpis(df_empty)
    assert res["total_searches"] == 0
    assert res["status"] == "empty_dataset"


def test_search_kpis_zero_clicks_conversion():
    """Verify zero clicks do not cause ZeroDivisionError in click_to_book_pct."""
    df_zero_clicks = pd.DataFrame({
        "search_id": ["s1", "s2"],
        "destination_id": ["DEL", "BOM"],
        "clicked": [0, 0],
        "booking_completed": [0, 0],
        "search_price": [5000.0, 6000.0],
    })
    res = compute_search_kpis(df_zero_clicks)
    assert res["total_searches"] == 2
    assert res["total_clicks"] == 0
    assert res["total_bookings"] == 0
    assert res["search_to_click_pct"] == 0.0
    assert res["click_to_book_pct"] == 0.0
    assert res["search_to_book_pct"] == 0.0


def test_inventory_kpis_empty_dataset():
    """Verify compute_inventory_kpis handles 0-row dataset safely."""
    df_empty = pd.DataFrame()
    res = compute_inventory_kpis(df_empty)
    assert res["total_inventory_records"] == 0
    assert res["status"] == "empty_dataset"


def test_supplier_kpis_empty_dataset():
    """Verify compute_supplier_kpis handles 0-row dataset safely."""
    df_empty = pd.DataFrame()
    res = compute_supplier_kpis(df_empty)
    assert res["total_offers"] == 0
    assert res["status"] == "empty_dataset"


def test_hotel_kpis_empty_dataset():
    """Verify compute_hotel_kpis handles 0-row dataset safely."""
    df_empty = pd.DataFrame()
    res = compute_hotel_kpis(df_empty)
    assert res["total_bookings"] == 0
    assert res["status"] == "empty_dataset"


def test_flight_operations_kpis_empty_dataset():
    """Verify compute_flight_operations_kpis handles 0-row dataset safely."""
    df_empty = pd.DataFrame()
    res = compute_flight_operations_kpis(df_empty)
    assert res["total_flights"] == 0
    assert res["status"] == "empty_dataset"


def test_flight_price_kpis_empty_dataset():
    """Verify compute_flight_price_kpis handles 0-row dataset safely."""
    df_empty = pd.DataFrame()
    res = compute_flight_price_kpis(df_empty)
    assert res["total_price_quotes"] == 0
    assert res["status"] == "empty_dataset"


def test_statistical_outliers_iqr_empty():
    """Verify detect_outliers_iqr on empty Series."""
    s = pd.Series(dtype=float)
    res = detect_outliers_iqr(s)
    assert res["total_records"] == 0
    assert res["outlier_count"] == 0
    assert res["outlier_pct"] == 0.0


def test_statistical_outliers_zscore_zero_variance():
    """Verify detect_outliers_zscore with constant values returns 0 outliers."""
    s = pd.Series([10.0, 10.0, 10.0, 10.0, 10.0])
    res = detect_outliers_zscore(s)
    assert res["outlier_count"] == 0
    assert res["outlier_pct"] == 0.0


def test_statistical_correlation_matrix_constant_column():
    """Verify compute_correlation_matrix handles constant features without raising unhandled errors."""
    df = pd.DataFrame({
        "const_feat": [1.0, 1.0, 1.0, 1.0],
        "var_feat": [1.0, 2.0, 3.0, 4.0],
    })
    corr = compute_correlation_matrix(df, method="pearson")
    assert isinstance(corr, pd.DataFrame)
    assert corr.shape == (2, 2)
