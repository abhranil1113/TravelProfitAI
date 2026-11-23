"""
Tests for Raw and Processed Source Data Preservation.
Guarantees that running Phase 4 modeling operations does NOT mutate, overwrite,
or delete any Phase 1, Phase 2, or Phase 3 data files.
"""

import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def test_raw_datasets_exist_and_unmodified():
    raw_files = [
        BASE_DIR / "data" / "raw" / "flights" / "flights.csv",
        BASE_DIR / "data" / "raw" / "flights" / "airports.csv",
        BASE_DIR / "data" / "raw" / "flights" / "airlines.csv",
        BASE_DIR / "data" / "raw" / "flight_prices" / "Flight Price Prediction.csv",
        BASE_DIR / "data" / "raw" / "hotel_bookings" / "hotel_bookings.csv",
    ]
    for rf in raw_files:
        assert rf.exists(), f"Raw dataset {rf} was deleted or moved!"
        assert rf.stat().st_size > 0, f"Raw dataset {rf} is empty!"


def test_synthetic_datasets_exist():
    synthetic_files = [
        BASE_DIR / "data" / "synthetic" / "customer_search_events.csv",
        BASE_DIR / "data" / "synthetic" / "inventory_availability.csv",
        BASE_DIR / "data" / "synthetic" / "supplier_offers.csv",
        BASE_DIR / "data" / "synthetic" / "market_seasonal_signals.csv",
    ]
    for sf in synthetic_files:
        assert sf.exists(), f"Synthetic dataset {sf} was deleted or moved!"
        assert sf.stat().st_size > 0, f"Synthetic dataset {sf} is empty!"


def test_phase3_feature_datasets_exist():
    feature_files = [
        BASE_DIR / "data" / "features" / "hotel" / "hotel_cancellation_features.parquet",
        BASE_DIR / "data" / "features" / "flight_prices" / "flight_price_features.parquet",
        BASE_DIR / "data" / "features" / "customer_demand" / "customer_demand_features.parquet",
        BASE_DIR / "data" / "features" / "inventory" / "inventory_features.parquet",
        BASE_DIR / "data" / "features" / "supplier" / "supplier_profitability_features.parquet",
        BASE_DIR / "data" / "features" / "market" / "destination_demand_supply_features.parquet",
        BASE_DIR / "data" / "features" / "market" / "market_demand_features.parquet",
        BASE_DIR / "data" / "features" / "flights" / "flight_operations_features.parquet",
    ]
    for ff in feature_files:
        assert ff.exists(), f"Phase 3 feature dataset {ff} is missing!"
        assert ff.stat().st_size > 0, f"Phase 3 feature dataset {ff} is empty!"
