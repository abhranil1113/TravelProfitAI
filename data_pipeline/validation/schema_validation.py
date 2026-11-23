"""
TBO InventoryIQ - Schema Validation Module
Provides Pandera-based schema models and validation routines for all 9 datasets.
"""

from typing import Dict, Any, Tuple, List
import pandas as pd
try:
    import pandera.pandas as pa
    from pandera.pandas import Column, Check, DataFrameSchema
except (ImportError, AttributeError):
    import pandera as pa
    from pandera import Column, Check, DataFrameSchema
import logging

logger = logging.getLogger(__name__)

# 1. Market Seasonal Signals Schema
MARKET_SEASONAL_SIGNALS_SCHEMA = DataFrameSchema(
    columns={
        "signal_id": Column(str, Check.str_matches(r"^SIG\d+"), nullable=False, unique=True),
        "destination_id": Column(str, nullable=False),
        "travel_date": Column(str, nullable=False),
        "month": Column(int, Check.in_range(1, 12), nullable=False),
        "season_type": Column(str, Check.isin(["PEAK", "NORMAL", "OFF_PEAK"]), nullable=False),
        "holiday_indicator": Column(bool, nullable=False),
        "festival_indicator": Column(bool, nullable=False),
        "event_indicator": Column(bool, nullable=False),
        "temperature": Column(float, nullable=False),
        "rainfall_mm": Column(float, Check.greater_than_or_equal_to(0.0), nullable=False),
        "demand_index": Column(float, Check.in_range(0.0, 1.0), nullable=False),
    },
    strict=False,
    coerce=False,
)

# 2. Inventory Availability Schema
INVENTORY_AVAILABILITY_SCHEMA = DataFrameSchema(
    columns={
        "snapshot_id": Column(str, Check.str_matches(r"^SNAP\d+"), nullable=False, unique=True),
        "inventory_id": Column(str, nullable=False),
        "inventory_type": Column(str, Check.isin(["HOTEL", "FLIGHT"]), nullable=False),
        "supplier_id": Column(str, nullable=False),
        "origin_id": Column(str, nullable=True),
        "destination_id": Column(str, nullable=False),
        "travel_date": Column(str, nullable=False),
        "snapshot_date": Column(str, nullable=False),
        "total_capacity": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "booked_quantity": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "available_quantity": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "sold_out": Column(bool, nullable=False),
        "unit_type": Column(str, Check.isin(["ROOM_NIGHT", "SEAT"]), nullable=False),
    },
    strict=False,
    coerce=False,
)

# 3. Supplier Offers Schema
SUPPLIER_OFFERS_SCHEMA = DataFrameSchema(
    columns={
        "offer_id": Column(str, Check.str_matches(r"^OFF\d+"), nullable=False, unique=True),
        "supplier_id": Column(str, nullable=False),
        "inventory_type": Column(str, Check.isin(["HOTEL", "FLIGHT"]), nullable=False),
        "inventory_id": Column(str, nullable=False),
        "origin_id": Column(str, nullable=True),
        "destination_id": Column(str, nullable=False),
        "travel_date": Column(str, nullable=False),
        "purchase_cost": Column(float, Check.greater_than_or_equal_to(0.0), nullable=False),
        "selling_price": Column(float, Check.greater_than_or_equal_to(0.0), nullable=False),
        "available_quantity": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "minimum_purchase_qty": Column(int, Check.greater_than_or_equal_to(1), nullable=False),
        "refundable": Column(bool, nullable=False),
        "offer_valid_until": Column(str, nullable=False),
    },
    strict=False,
    coerce=False,
)

# 4. Customer Search Events Schema
CUSTOMER_SEARCH_EVENTS_SCHEMA = DataFrameSchema(
    columns={
        "search_id": Column(str, Check.str_matches(r"^SRCH\d+"), nullable=False, unique=True),
        "user_id": Column(str, nullable=False),
        "search_date": Column(str, nullable=False),
        "travel_date": Column(str, nullable=False),
        "destination_id": Column(str, nullable=False),
        "origin_id": Column(str, nullable=True),
        "inventory_type": Column(str, Check.isin(["HOTEL", "FLIGHT"]), nullable=False),
        "travellers_count": Column(int, Check.greater_than_or_equal_to(1), nullable=False),
        "rooms_count": Column(float, nullable=True),
        "search_price": Column(float, Check.greater_than_or_equal_to(0.0), nullable=False),
        "clicked": Column(bool, nullable=False),
        "booking_completed": Column(bool, nullable=False),
    },
    strict=False,
    coerce=False,
)

# 5. Airlines Schema
AIRLINES_SCHEMA = DataFrameSchema(
    columns={
        "IATA_CODE": Column(str, nullable=False, unique=True),
        "AIRLINE": Column(str, nullable=False),
    },
    strict=False,
)

# 6. Airports Schema
AIRPORTS_SCHEMA = DataFrameSchema(
    columns={
        "IATA_CODE": Column(str, nullable=False, unique=True),
        "AIRPORT": Column(str, nullable=False),
        "CITY": Column(str, nullable=False),
        "STATE": Column(str, nullable=True),
        "COUNTRY": Column(str, nullable=False),
        "LATITUDE": Column(float, nullable=True),
        "LONGITUDE": Column(float, nullable=True),
    },
    strict=False,
)

# 7. Flight Prices Schema
FLIGHT_PRICES_SCHEMA = DataFrameSchema(
    columns={
        "airline": Column(str, nullable=False),
        "flight": Column(str, nullable=False),
        "source_city": Column(str, nullable=False),
        "departure_time": Column(str, nullable=False),
        "stops": Column(str, nullable=False),
        "arrival_time": Column(str, nullable=False),
        "destination_city": Column(str, nullable=False),
        "class": Column(str, Check.isin(["Economy", "Business"]), nullable=False),
        "duration": Column(float, Check.greater_than(0.0), nullable=False),
        "days_left": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "price": Column(float, Check.greater_than(0.0), nullable=False),
    },
    strict=False,
)

# 8. Hotel Bookings Schema
HOTEL_BOOKINGS_SCHEMA = DataFrameSchema(
    columns={
        "hotel": Column(str, nullable=False),
        "is_canceled": Column(int, Check.isin([0, 1]), nullable=False),
        "lead_time": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "arrival_date_year": Column(int, nullable=False),
        "arrival_date_month": Column(str, nullable=False),
        "arrival_date_week_number": Column(int, nullable=False),
        "arrival_date_day_of_month": Column(int, Check.in_range(1, 31), nullable=False),
        "stays_in_weekend_nights": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "stays_in_week_nights": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "adults": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "children": Column(float, nullable=True),
        "babies": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "meal": Column(str, nullable=False),
        "country": Column(str, nullable=True),
        "market_segment": Column(str, nullable=False),
        "distribution_channel": Column(str, nullable=False),
        "is_repeated_guest": Column(int, Check.isin([0, 1]), nullable=False),
        "previous_cancellations": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "previous_bookings_not_canceled": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "reserved_room_type": Column(str, nullable=False),
        "assigned_room_type": Column(str, nullable=False),
        "booking_changes": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "deposit_type": Column(str, nullable=False),
        "agent": Column(float, nullable=True),
        "company": Column(float, nullable=True),
        "days_in_waiting_list": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "customer_type": Column(str, nullable=False),
        "adr": Column(float, nullable=False),
        "required_car_parking_spaces": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "total_of_special_requests": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "reservation_status": Column(str, nullable=False),
        "reservation_status_date": Column(str, nullable=False),
    },
    strict=False,
)

# 9. Flights Schema
FLIGHTS_SCHEMA = DataFrameSchema(
    columns={
        "YEAR": Column(int, nullable=False),
        "MONTH": Column(int, Check.in_range(1, 12), nullable=False),
        "DAY": Column(int, Check.in_range(1, 31), nullable=False),
        "DAY_OF_WEEK": Column(int, Check.in_range(1, 7), nullable=False),
        "AIRLINE": Column(str, nullable=False),
        "FLIGHT_NUMBER": Column(str, nullable=False),
        "TAIL_NUMBER": Column(str, nullable=True),
        "ORIGIN_AIRPORT": Column(str, nullable=False),
        "DESTINATION_AIRPORT": Column(str, nullable=False),
        "SCHEDULED_DEPARTURE": Column(float, nullable=False),
        "DISTANCE": Column(float, Check.greater_than(0.0), nullable=False),
        "DIVERTED": Column(int, Check.isin([0, 1]), nullable=False),
        "CANCELLED": Column(int, Check.isin([0, 1]), nullable=False),
    },
    strict=False,
)

SCHEMAS: Dict[str, DataFrameSchema] = {
    "market_seasonal_signals": MARKET_SEASONAL_SIGNALS_SCHEMA,
    "inventory_availability": INVENTORY_AVAILABILITY_SCHEMA,
    "supplier_offers": SUPPLIER_OFFERS_SCHEMA,
    "customer_search_events": CUSTOMER_SEARCH_EVENTS_SCHEMA,
    "airlines": AIRLINES_SCHEMA,
    "airports": AIRPORTS_SCHEMA,
    "flight_prices": FLIGHT_PRICES_SCHEMA,
    "hotel_bookings": HOTEL_BOOKINGS_SCHEMA,
    "flights": FLIGHTS_SCHEMA,
}


def validate_schema(
    dataset_name: str,
    df: pd.DataFrame,
    lazy: bool = True,
) -> Tuple[bool, List[str]]:
    """
    Validate a dataframe against its schema specification.
    Returns (is_valid, list_of_error_messages).
    """
    if dataset_name not in SCHEMAS:
        return True, [f"No schema defined for '{dataset_name}'"]

    schema = SCHEMAS[dataset_name]
    try:
        schema.validate(df, lazy=lazy)
        return True, []
    except pa.errors.SchemaErrors as err:
        error_msgs = [f"SchemaError: {e}" for e in err.failure_cases["check"].tolist()[:20]]
        return False, error_msgs
    except Exception as e:
        return False, [str(e)]
