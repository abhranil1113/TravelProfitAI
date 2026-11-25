"""
TBO InventoryIQ - Feature Engineering Configuration & Settings (Phase 3)
Defines filesystem paths, currency maps, feature engineering thresholds,
leakage boundaries, and split configurations.
"""

from pathlib import Path
from typing import Dict, List, Any

# Root Directory Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
FEATURES_DATA_DIR = DATA_DIR / "features"

REPORTS_DIR = BASE_DIR / "reports" / "feature_engineering"

# Feature Subdirectories
FEATURE_DIRS: Dict[str, Path] = {
    "hotel": FEATURES_DATA_DIR / "hotel",
    "flight_prices": FEATURES_DATA_DIR / "flight_prices",
    "flights": FEATURES_DATA_DIR / "flights",
    "customer_demand": FEATURES_DATA_DIR / "customer_demand",
    "inventory": FEATURES_DATA_DIR / "inventory",
    "supplier": FEATURES_DATA_DIR / "supplier",
    "market": FEATURES_DATA_DIR / "market",
}

# Ensure all feature output directories and reports dir exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
for p in FEATURE_DIRS.values():
    p.mkdir(parents=True, exist_ok=True)

# Processed Source Dataset Paths
PROCESSED_DATASET_PATHS: Dict[str, Dict[str, Path]] = {
    "hotel_bookings": {
        "parquet": PROCESSED_DATA_DIR / "hotel_bookings" / "cleaned_hotel_bookings.parquet",
        "csv": PROCESSED_DATA_DIR / "hotel_bookings" / "cleaned_hotel_bookings.csv",
    },
    "flight_prices": {
        "parquet": PROCESSED_DATA_DIR / "flight_prices" / "cleaned_flight_prices.parquet",
        "csv": PROCESSED_DATA_DIR / "flight_prices" / "cleaned_flight_prices.csv",
    },
    "flights": {
        "parquet": PROCESSED_DATA_DIR / "flights" / "cleaned_flights.parquet",
        "csv": PROCESSED_DATA_DIR / "flights" / "cleaned_flights.csv",
    },
    "airlines": {
        "parquet": PROCESSED_DATA_DIR / "flights" / "cleaned_airlines.parquet",
        "csv": PROCESSED_DATA_DIR / "flights" / "cleaned_airlines.csv",
    },
    "airports": {
        "parquet": PROCESSED_DATA_DIR / "flights" / "cleaned_airports.parquet",
        "csv": PROCESSED_DATA_DIR / "flights" / "cleaned_airports.csv",
    },
    "customer_search_events": {
        "parquet": PROCESSED_DATA_DIR / "searches" / "cleaned_customer_search_events.parquet",
        "csv": PROCESSED_DATA_DIR / "searches" / "cleaned_customer_search_events.csv",
    },
    "supplier_offers": {
        "parquet": PROCESSED_DATA_DIR / "supplier_offers" / "cleaned_supplier_offers.parquet",
        "csv": PROCESSED_DATA_DIR / "supplier_offers" / "cleaned_supplier_offers.csv",
    },
    "inventory_availability": {
        "parquet": PROCESSED_DATA_DIR / "inventory" / "cleaned_inventory_availability.parquet",
        "csv": PROCESSED_DATA_DIR / "inventory" / "cleaned_inventory_availability.csv",
    },
    "market_seasonal_signals": {
        "parquet": PROCESSED_DATA_DIR / "market_signals" / "cleaned_market_seasonal_signals.parquet",
        "csv": PROCESSED_DATA_DIR / "market_signals" / "cleaned_market_seasonal_signals.csv",
    },
}

# Domain Currency Separation
CURRENCY_MAP: Dict[str, str] = {
    "hotel_cancellation_features": "EUR",
    "flight_price_features": "INR",
    "customer_demand_features": "INR",
    "inventory_features": "OPERATIONAL",
    "supplier_profitability_features": "INR",
    "flight_operations_features": "OPERATIONAL",
    "market_demand_features": "INDEX",
}

# Strict Unit Segregation
UNIT_TYPES: Dict[str, str] = {
    "hotel_room": "ROOM_NIGHT",
    "flight_seat": "SEAT",
}

# Target Leakage Quarantined Features (Explicitly excluded from predictive inputs)
# Features in LEAKAGE_EXCLUSIONS must NEVER be passed as model inputs for pre-event tasks
LEAKAGE_EXCLUSIONS: Dict[str, List[str]] = {
    "hotel_cancellation_features": [
        "reservation_status",
        "reservation_status_date",
        "assigned_room_type",                    # Operational check-in assignment (post-booking)
        "room_type_changed",                     # Operational room discrepancy observed at allocation
        "market_segment_historical_cancel_rate", # Global target encoding over full dataset (analytical reference only)
        "deposit_type_historical_cancel_rate",   # Global target encoding over full dataset (analytical reference only)
    ],
    "flight_price_features": [
        # Target is price; no post-booking features in dataset
    ],
    "customer_demand_features": [
        "clicked",             # Post-search customer click event
        "booking_completed",   # Post-search customer booking conversion
        "has_funnel_anomaly",  # Derived post-search outcome anomaly
    ],
    "inventory_features": [
        # Future snapshot observations are strictly excluded via temporal lag masking
    ],
    "flight_operations_features": [
        "DEPARTURE_TIME",
        "DEPARTURE_DELAY",
        "TAXI_OUT",
        "WHEELS_OFF",
        "ELAPSED_TIME",
        "AIR_TIME",
        "WHEELS_ON",
        "TAXI_IN",
        "ARRIVAL_TIME",
        "ARRIVAL_DELAY",
        "DIVERTED",
        "CANCELLED",
        "CANCELLATION_REASON",
        "AIR_SYSTEM_DELAY",
        "SECURITY_DELAY",
        "AIRLINE_DELAY",
        "LATE_AIRCRAFT_DELAY",
        "WEATHER_DELAY",
    ],
    "supplier_profitability_features": [
        # selling_price is quarantined if predicting purchase cost
    ],
}

# Post-booking operational features for hotel bookings
POST_BOOKING_HOTEL_OPERATIONAL_FEATURES: List[str] = [
    "assigned_room_type",
    "room_type_changed",
    "booking_changes",
]

# Flight Operations Sampling Metadata
# In Phase 1 cleaning, a deterministic chronological head sample of 1,000 records
# (from 2015-01-01) was generated into data/processed/flights/cleaned_flights.parquet
# to provide an instant, lightweight test and prototyping fixture without incurring OOM
# on the full 5,819,079 row raw dataset (565 MB raw CSV, ~1.2 GB RAM).
FLIGHT_OPERATIONS_SAMPLE_SIZE: int = 1000
FLIGHT_OPERATIONS_FULL_RAW_ROWS: int = 5819079

# Configurable Categorical & Numerical Bins
BIN_CONFIGS: Dict[str, Any] = {
    "hotel_lead_time": {
        "bins": [-1, 7, 30, 90, 180, 365, 10000],
        "labels": ["0-7d", "8-30d", "31-90d", "91-180d", "181-365d", "365d+"],
    },
    "flight_days_left": {
        "bins": [0, 3, 7, 14, 30, 100],
        "labels": ["1-3d", "4-7d", "8-14d", "15-30d", "31d+"],
    },
    "flight_duration": {
        "bins": [0.0, 2.5, 6.0, 12.0, 100.0],
        "labels": ["Short_Haul", "Medium_Haul", "Long_Haul", "Ultra_Long_Haul"],
    },
    "search_lead_time": {
        "bins": [-1, 7, 15, 30, 60, 90, 10000],
        "labels": ["0-7d", "8-15d", "16-30d", "31-60d", "61-90d", "90d+"],
    },
    "market_demand_index": {
        "bins": [-1.0, 40.0, 70.0, 90.0, 200.0],
        "labels": ["Low", "Medium", "High", "Extreme_Peak"],
    },
    "inventory_availability_pct": {
        "bins": [-1.0, 0.0, 10.0, 25.0, 50.0, 1000.0],
        "labels": ["Sold_Out", "Critical", "Low", "Moderate", "High"],
    },
    "supplier_margin_pct": {
        "bins": [-1000.0, 0.0, 10.0, 25.0, 1000.0],
        "labels": ["Negative_Deficit", "Low_Margin", "Healthy_Margin", "High_Margin"],
    },
}

# Peak Season Definition (Tourism & Holiday surges)
PEAK_MONTHS: List[int] = [6, 7, 8, 12]  # June, July, August (Summer), December (Holidays)
