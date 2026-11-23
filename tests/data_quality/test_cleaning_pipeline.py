"""
TBO InventoryIQ - Automated Tests: Cleaning Pipeline, Idempotency & Persistence
"""

import pytest
import pandas as pd
import numpy as np

from data_pipeline.cleaning.clean_market_signals import clean_market_signals
from data_pipeline.cleaning.clean_inventory import clean_inventory_availability
from data_pipeline.cleaning.clean_supplier_offers import clean_supplier_offers
from data_pipeline.cleaning.clean_search_events import clean_search_events
from data_pipeline.cleaning.clean_hotel_bookings import clean_hotel_bookings
from data_pipeline.cleaning.clean_flight_prices import clean_flight_prices
from data_pipeline.cleaning.cleaning_pipeline import run_cleaning_pipeline
from data_pipeline.config import PROCESSED_PATHS, REPORT_PATHS


def test_clean_hotel_bookings_removes_errors(sample_dirty_hotel_bookings):
    """
    Verify clean_hotel_bookings removes proven data errors:
    - 1 negative ADR row (-6.38)
    - 1 extreme ADR outlier row (5400.0)
    - 1 zero-occupancy row (0+0+0 occupants)
    When deduplicate_identical_rows=False, preserves duplicate feature copies with flag.
    When deduplicate_identical_rows=True, removes the duplicate row as well.
    """
    initial_count = len(sample_dirty_hotel_bookings)
    assert initial_count == 5

    # Test with default preservation of duplicate feature sets
    cleaned, meta = clean_hotel_bookings(sample_dirty_hotel_bookings, filter_data_errors=True, deduplicate_identical_rows=False)
    assert len(cleaned) == 2  # Row 0 (valid) and Row 1 (duplicate copy) kept with audit flag
    assert cleaned["is_duplicate_feature_copy"].sum() == 1
    assert meta["negative_adr_detected"] == 1
    assert meta["extreme_adr_outliers_detected"] == 1
    assert "arrival_date" in cleaned.columns
    assert "total_stay_nights" in cleaned.columns
    assert "total_guests" in cleaned.columns

    # Test with explicit deduplication enabled
    cleaned_deduped, meta_deduped = clean_hotel_bookings(sample_dirty_hotel_bookings, filter_data_errors=True, deduplicate_identical_rows=True)
    assert len(cleaned_deduped) == 1
    assert meta_deduped["exact_duplicates_removed"] == 1


def test_cleaning_idempotency(sample_market_signals):
    """Verify executing cleaning multiple times produces identical idempotent results."""
    cleaned_once, _ = clean_market_signals(sample_market_signals)
    cleaned_twice, _ = clean_market_signals(cleaned_once)
    pd.testing.assert_frame_equal(cleaned_once, cleaned_twice)


def test_clean_inventory_availability_balance(sample_inventory_availability):
    """Verify inventory availability cleaning enforces capacity equation."""
    cleaned, meta = clean_inventory_availability(sample_inventory_availability)
    for _, row in cleaned.iterrows():
        assert row["available_quantity"] == row["total_capacity"] - row["booked_quantity"]
        assert row["sold_out"] == (row["available_quantity"] == 0)


def test_clean_supplier_offers_negative_margin_handling(sample_supplier_offers):
    """Verify negative margin offers are flagged but not deleted."""
    # Add negative margin offer (purchase 8000, selling 7000)
    loss_offer = sample_supplier_offers.iloc[[0]].copy()
    loss_offer["offer_id"] = "OFF_LOSS"
    loss_offer["purchase_cost"] = 8000.0
    loss_offer["selling_price"] = 7000.0
    df_offers = pd.concat([sample_supplier_offers, loss_offer], ignore_index=True)

    cleaned, meta = clean_supplier_offers(df_offers)
    assert len(cleaned) == len(df_offers)
    assert "is_negative_margin" in cleaned.columns
    flagged = cleaned[cleaned["offer_id"] == "OFF_LOSS"].iloc[0]
    assert flagged["is_negative_margin"] == True
    assert flagged["unit_margin"] == -1000.0


def test_clean_search_events_funnel_sync(sample_customer_search_events):
    """Verify conversion funnel audit flag (booked implies clicked audit without destructive mutation)."""
    # Create search where booked is True but clicked is False
    df = sample_customer_search_events.copy()
    df.loc[0, "booking_completed"] = True
    df.loc[0, "clicked"] = False

    cleaned, meta = clean_search_events(df)
    # Observed clicked value is preserved as False (non-destructive)
    assert cleaned.loc[0, "clicked"] == False
    # Diagnostic flag is raised
    assert cleaned.loc[0, "has_funnel_anomaly"] == True
    assert meta["funnel_anomalies_detected"] == 1
    assert "search_lead_days" in cleaned.columns


def test_end_to_end_pipeline_execution():
    """Verify end-to-end cleaning pipeline completes and writes all artifacts."""
    results = run_cleaning_pipeline(flight_sample_rows=1000)
    assert "cleaned_datasets" in results
    assert "cleaning_summaries" in results

    # Verify all reports exist
    for rep_name, path in REPORT_PATHS.items():
        assert path.exists(), f"Report file missing: {path}"
        assert path.stat().st_size > 0, f"Report file is empty: {path}"

    # Verify all processed files exist
    for ds_name, p_dict in PROCESSED_PATHS.items():
        assert p_dict["csv"].exists(), f"Processed CSV missing for {ds_name}"
        assert p_dict["parquet"].exists(), f"Processed Parquet missing for {ds_name}"
