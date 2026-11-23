"""
TBO InventoryIQ - Configuration Module
Centralized configurations, file paths, schema definitions, and validation rules.
"""

from pathlib import Path
from typing import Dict, List, Any

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SYNTHETIC_DATA_DIR = DATA_DIR / "synthetic"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = BASE_DIR / "reports" / "data_quality"

# Dataset File Paths
DATASET_PATHS: Dict[str, Path] = {
    "market_seasonal_signals": SYNTHETIC_DATA_DIR / "market_seasonal_signals.csv",
    "inventory_availability": SYNTHETIC_DATA_DIR / "inventory_availability.csv",
    "supplier_offers": SYNTHETIC_DATA_DIR / "supplier_offers.csv",
    "customer_search_events": SYNTHETIC_DATA_DIR / "customer_search_events.csv",
    "airlines": RAW_DATA_DIR / "flights" / "airlines.csv",
    "airports": RAW_DATA_DIR / "flights" / "airports.csv",
    "flights": RAW_DATA_DIR / "flights" / "flights.csv",
    "flight_prices": RAW_DATA_DIR / "flight_prices" / "Flight Price Prediction.csv",
    "hotel_bookings": RAW_DATA_DIR / "hotel_bookings" / "hotel_bookings.csv",
}

# Output Processed Paths
PROCESSED_PATHS: Dict[str, Dict[str, Path]] = {
    "market_seasonal_signals": {
        "csv": PROCESSED_DATA_DIR / "market_signals" / "cleaned_market_seasonal_signals.csv",
        "parquet": PROCESSED_DATA_DIR / "market_signals" / "cleaned_market_seasonal_signals.parquet",
    },
    "inventory_availability": {
        "csv": PROCESSED_DATA_DIR / "inventory" / "cleaned_inventory_availability.csv",
        "parquet": PROCESSED_DATA_DIR / "inventory" / "cleaned_inventory_availability.parquet",
    },
    "supplier_offers": {
        "csv": PROCESSED_DATA_DIR / "supplier_offers" / "cleaned_supplier_offers.csv",
        "parquet": PROCESSED_DATA_DIR / "supplier_offers" / "cleaned_supplier_offers.parquet",
    },
    "customer_search_events": {
        "csv": PROCESSED_DATA_DIR / "searches" / "cleaned_customer_search_events.csv",
        "parquet": PROCESSED_DATA_DIR / "searches" / "cleaned_customer_search_events.parquet",
    },
    "airlines": {
        "csv": PROCESSED_DATA_DIR / "flights" / "cleaned_airlines.csv",
        "parquet": PROCESSED_DATA_DIR / "flights" / "cleaned_airlines.parquet",
    },
    "airports": {
        "csv": PROCESSED_DATA_DIR / "flights" / "cleaned_airports.csv",
        "parquet": PROCESSED_DATA_DIR / "flights" / "cleaned_airports.parquet",
    },
    "flights": {
        "csv": PROCESSED_DATA_DIR / "flights" / "cleaned_flights.csv",
        "parquet": PROCESSED_DATA_DIR / "flights" / "cleaned_flights.parquet",
    },
    "flight_prices": {
        "csv": PROCESSED_DATA_DIR / "flight_prices" / "cleaned_flight_prices.csv",
        "parquet": PROCESSED_DATA_DIR / "flight_prices" / "cleaned_flight_prices.parquet",
    },
    "hotel_bookings": {
        "csv": PROCESSED_DATA_DIR / "hotel_bookings" / "cleaned_hotel_bookings.csv",
        "parquet": PROCESSED_DATA_DIR / "hotel_bookings" / "cleaned_hotel_bookings.parquet",
    },
}

# Report Paths
REPORT_PATHS: Dict[str, Path] = {
    "profile": REPORTS_DIR / "dataset_profile.json",
    "missing_values": REPORTS_DIR / "missing_values.csv",
    "duplicates": REPORTS_DIR / "duplicates.csv",
    "datatype_issues": REPORTS_DIR / "datatype_issues.csv",
    "id_consistency": REPORTS_DIR / "id_consistency.csv",
    "business_rules": REPORTS_DIR / "business_rule_violations.csv",
    "outliers": REPORTS_DIR / "outliers.csv",
    "cleaning_summary": REPORTS_DIR / "cleaning_summary.json",
    "final_markdown": REPORTS_DIR / "final_validation_report.md",
}

# Primary Key Definitions
PRIMARY_KEYS: Dict[str, Any] = {
    "market_seasonal_signals": "signal_id",
    "inventory_availability": "snapshot_id",
    "supplier_offers": "offer_id",
    "customer_search_events": "search_id",
    "airlines": "IATA_CODE",
    "airports": "IATA_CODE",
    "flights": ["YEAR", "MONTH", "DAY", "AIRLINE", "FLIGHT_NUMBER", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT", "SCHEDULED_DEPARTURE"],
    "flight_prices": "price_record_id",
    "hotel_bookings": None,  # Transactional dataset without explicit single-column surrogate key
}

# Allowable Categories
VALID_INVENTORY_TYPES = ["HOTEL", "FLIGHT"]
VALID_SEASON_TYPES = ["PEAK", "NORMAL", "OFF_PEAK"]
VALID_UNIT_TYPES = ["ROOM_NIGHT", "SEAT"]

# Columns that legitimately permit nulls and their operational justifications
LEGITIMATE_NULL_FIELDS: Dict[str, Dict[str, str]] = {
    "inventory_availability": {
        "origin_id": "Hotels are stationary destination-only inventory and do not possess an origin location.",
    },
    "supplier_offers": {
        "origin_id": "Hotel supply offers apply to destination properties and do not have an origin.",
    },
    "customer_search_events": {
        "rooms_count": "Flight searches do not require or specify hotel room counts.",
        "origin_id": "Destination-only searches where customer searches without departure specified (if applicable).",
    },
    "hotel_bookings": {
        "agent": "Bookings placed directly by guests without travel agency intermediary.",
        "company": "Non-corporate individual leisure bookings without company sponsor.",
        "country": "Guest country of origin omitted or not captured during reservation.",
        "children": "Default zero children if not entered.",
    },
    "airports": {
        "LATITUDE": "Geographical coordinates unrecorded for select remote landing strips.",
        "LONGITUDE": "Geographical coordinates unrecorded for select remote landing strips.",
    },
    "flights": {
        "TAIL_NUMBER": "Unassigned tail number for cancelled flights.",
        "DEPARTURE_TIME": "Flight cancelled before pushback.",
        "DEPARTURE_DELAY": "Flight cancelled before departure.",
        "TAXI_OUT": "Flight cancelled before taxiing.",
        "WHEELS_OFF": "Flight cancelled prior to takeoff.",
        "ELAPSED_TIME": "Flight cancelled or diverted before completion.",
        "AIR_TIME": "Flight cancelled or diverted.",
        "WHEELS_ON": "Flight cancelled or diverted.",
        "TAXI_IN": "Flight cancelled or diverted.",
        "ARRIVAL_TIME": "Flight cancelled or diverted.",
        "ARRIVAL_DELAY": "Flight cancelled or diverted.",
        "CANCELLATION_REASON": "Not cancelled (flight operated normally).",
        "AIR_SYSTEM_DELAY": "Flight arrived on time or with delay < 15 minutes.",
        "SECURITY_DELAY": "Flight arrived on time or with delay < 15 minutes.",
        "AIRLINE_DELAY": "Flight arrived on time or with delay < 15 minutes.",
        "LATE_AIRCRAFT_DELAY": "Flight arrived on time or with delay < 15 minutes.",
        "WEATHER_DELAY": "Flight arrived on time or with delay < 15 minutes.",
    },
}
