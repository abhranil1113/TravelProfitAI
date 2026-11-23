"""
TBO InventoryIQ - EDA Configuration & Settings (Phase 2)
Defines filesystem paths, currency safety mappings, target leakage boundaries,
and visualization parameters for exploratory data analysis.
"""

from pathlib import Path
from typing import Dict, List, Any

# Root Project Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SYNTHETIC_DATA_DIR = DATA_DIR / "synthetic"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORTS_DIR = BASE_DIR / "reports" / "eda"
FIGURES_DIR = REPORTS_DIR / "figures"
TABLES_DIR = REPORTS_DIR / "tables"

# Ensure output directories exist
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

# Processed Dataset Paths (Parquet preferred for performance, CSV fallback)
DATASET_PATHS: Dict[str, Dict[str, Path]] = {
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

# Currency Safety Mappings
# Strict rule: Unaligned financial calculations between EUR and INR are forbidden without explicit conversion.
CURRENCY_MAP: Dict[str, str] = {
    "hotel_bookings": "EUR",
    "flight_prices": "INR",
    "supplier_offers": "INR",
    "customer_search_events": "INR",
    "flights": "OPERATIONAL",
    "airlines": "METADATA",
    "airports": "METADATA",
    "inventory_availability": "OPERATIONAL",
    "market_seasonal_signals": "INDEX",
}

class CurrencyMismatchError(Exception):
    """Raised when an illegal cross-currency calculation is attempted without conversion."""
    pass


# Data Leakage & Target Boundaries
# Features that exist only after the outcome or post-event and must NOT be used as predictive inputs.
LEAKAGE_BOUNDARIES: Dict[str, Dict[str, Any]] = {
    "hotel_bookings": {
        "target": "is_canceled",
        "post_event_leakage_features": [
            "reservation_status",
            "reservation_status_date",
        ],
        "allowed_pre_booking_features": [
            "hotel",
            "lead_time",
            "arrival_date_year",
            "arrival_date_month",
            "arrival_date_week_number",
            "stays_in_weekend_nights",
            "stays_in_week_nights",
            "adults",
            "children",
            "babies",
            "meal",
            "country",
            "market_segment",
            "distribution_channel",
            "is_repeated_guest",
            "previous_cancellations",
            "previous_bookings_not_canceled",
            "reserved_room_type",
            "deposit_type",
            "agent",
            "company",
            "days_in_waiting_list",
            "customer_type",
            "adr",
            "required_car_parking_spaces",
            "total_of_special_requests",
        ],
    },
    "flight_prices": {
        "target": "price",
        "post_event_leakage_features": [],
        "allowed_pre_booking_features": [
            "airline",
            "flight",
            "source_city",
            "departure_time",
            "stops",
            "stops_count",
            "arrival_time",
            "destination_city",
            "class",
            "duration",
            "days_left",
            "route",
        ],
    },
    "flights": {
        "target": "ARRIVAL_DELAY",
        "post_event_leakage_features": [
            "DEPARTURE_TIME",
            "DEPARTURE_DELAY",
            "TAXI_OUT",
            "WHEELS_OFF",
            "ELAPSED_TIME",
            "AIR_TIME",
            "WHEELS_ON",
            "TAXI_IN",
            "ARRIVAL_TIME",
            "DIVERTED",
            "CANCELLED",
            "CANCELLATION_REASON",
            "AIR_SYSTEM_DELAY",
            "SECURITY_DELAY",
            "AIRLINE_DELAY",
            "LATE_AIRCRAFT_DELAY",
            "WEATHER_DELAY",
        ],
        "allowed_pre_departure_features": [
            "YEAR",
            "MONTH",
            "DAY",
            "DAY_OF_WEEK",
            "AIRLINE",
            "FLIGHT_NUMBER",
            "ORIGIN_AIRPORT",
            "DESTINATION_AIRPORT",
            "SCHEDULED_DEPARTURE",
            "SCHEDULED_ARRIVAL",
            "SCHEDULED_TIME",
            "DISTANCE",
            "ROUTE",
        ],
    },
    "customer_search_events": {
        "targets": ["clicked", "booking_completed"],
        "post_event_leakage_features": [
            "clicked",             # Leakage for search volume / search lead modeling
            "booking_completed",   # Leakage for search click modeling
        ],
        "allowed_search_features": [
            "user_id",
            "search_date",
            "travel_date",
            "destination_id",
            "origin_id",
            "inventory_type",
            "travellers_count",
            "rooms_count",
            "search_price",
            "search_lead_days",
        ],
    },
    "inventory_availability": {
        "snapshot_key": "snapshot_date",
        "cardinality_constraint": "Multiple snapshots exist per inventory_id; aggregate across latest snapshot only.",
    },
}

# Future Machine Learning Candidate Models to Assess in Phase 2
CANDIDATE_MODELS: List[Dict[str, str]] = [
    {
        "id": "model_1_hotel_cancellation",
        "name": "Hotel Booking Cancellation Prediction",
        "target": "is_canceled",
        "type": "Binary Classification",
        "primary_dataset": "hotel_bookings",
    },
    {
        "id": "model_2_flight_price",
        "name": "Dynamic Flight Price Regression",
        "target": "price",
        "type": "Regression",
        "primary_dataset": "flight_prices",
    },
    {
        "id": "model_3_search_demand",
        "name": "Destination Search & Demand Forecasting",
        "target": "search_volume / booking_completed",
        "type": "Time Series / Classification",
        "primary_dataset": "customer_search_events & market_seasonal_signals",
    },
    {
        "id": "model_4_inventory_depletion",
        "name": "Inventory Depletion & Stockout Velocity",
        "target": "available_quantity / sold_out",
        "type": "Survival Analysis / Classification",
        "primary_dataset": "inventory_availability",
    },
    {
        "id": "model_5_supplier_competitiveness",
        "name": "Supplier Price Competitiveness & Profit Margin Model",
        "target": "margin_percentage / supplier_win_rate",
        "type": "Regression / Ranking",
        "primary_dataset": "supplier_offers",
    },
]

# Visualization Aesthetics Configuration
PLOT_STYLE: Dict[str, Any] = {
    "style": "whitegrid",
    "palette": "deep",
    "dpi": 300,
    "figure_sizes": {
        "standard": (10, 6),
        "wide": (14, 7),
        "tall": (8, 10),
        "square": (8, 8),
        "dashboard": (16, 10),
    },
    "font_scale": 1.1,
}
