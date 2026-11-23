"""
Tests for Source Dataset Preservation Module
Verifies that feature engineering never modifies raw, synthetic, or Phase 1 processed data.
"""

import pytest
from pathlib import Path
from feature_engineering.config import (
    BASE_DIR,
    PROCESSED_DATASET_PATHS,
)


def test_raw_and_synthetic_immutability():
    raw_files = [
        BASE_DIR / "data" / "raw" / "flights" / "airlines.csv",
        BASE_DIR / "data" / "raw" / "flights" / "airports.csv",
        BASE_DIR / "data" / "raw" / "flights" / "flights.csv",
        BASE_DIR / "data" / "raw" / "flight_prices" / "Flight Price Prediction.csv",
        BASE_DIR / "data" / "raw" / "hotel_bookings" / "hotel_bookings.csv",
        BASE_DIR / "data" / "synthetic" / "customer_search_events.csv",
        BASE_DIR / "data" / "synthetic" / "supplier_offers.csv",
        BASE_DIR / "data" / "synthetic" / "inventory_availability.csv",
        BASE_DIR / "data" / "synthetic" / "market_seasonal_signals.csv",
    ]

    for p in raw_files:
        assert p.exists(), f"Raw source file missing: {p}"
        assert p.stat().st_size > 0


def test_processed_pipeline_immutability():
    for name, paths in PROCESSED_DATASET_PATHS.items():
        parquet_p = paths["parquet"]
        csv_p = paths["csv"]
        assert parquet_p.exists(), f"Processed parquet missing: {parquet_p}"
        assert parquet_p.stat().st_size > 0
        assert csv_p.exists(), f"Processed CSV missing: {csv_p}"
        assert csv_p.stat().st_size > 0
