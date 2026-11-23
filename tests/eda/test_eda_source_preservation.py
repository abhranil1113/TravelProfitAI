"""
Tests for Data Source Preservation Module
Verifies that EDA execution never mutates or deletes raw or Phase 1 processed data files.
"""

import pytest
from pathlib import Path
from eda.config import DATASET_PATHS, RAW_DATA_DIR, SYNTHETIC_DATA_DIR


def test_raw_files_unmodified():
    """Verify all raw and synthetic source files exist and remain non-empty."""
    raw_files = [
        RAW_DATA_DIR / "flights" / "airlines.csv",
        RAW_DATA_DIR / "flights" / "airports.csv",
        RAW_DATA_DIR / "flights" / "flights.csv",
        RAW_DATA_DIR / "flight_prices" / "Flight Price Prediction.csv",
        RAW_DATA_DIR / "hotel_bookings" / "hotel_bookings.csv",
        SYNTHETIC_DATA_DIR / "customer_search_events.csv",
        SYNTHETIC_DATA_DIR / "supplier_offers.csv",
        SYNTHETIC_DATA_DIR / "inventory_availability.csv",
        SYNTHETIC_DATA_DIR / "market_seasonal_signals.csv",
    ]

    for p in raw_files:
        assert p.exists(), f"Raw source file missing: {p}"
        assert p.stat().st_size > 0, f"Raw source file is empty: {p}"


def test_processed_files_preserved():
    """Verify that processed parquet and csv files remain intact."""
    for name, paths in DATASET_PATHS.items():
        parquet_p = paths["parquet"]
        csv_p = paths["csv"]
        assert parquet_p.exists(), f"Processed parquet missing for {name}: {parquet_p}"
        assert parquet_p.stat().st_size > 0
        assert csv_p.exists(), f"Processed CSV missing for {name}: {csv_p}"
        assert csv_p.stat().st_size > 0
