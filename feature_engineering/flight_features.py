"""
TBO InventoryIQ - Flight Feature Engineering (Phase 3)
Builds feature sets for dynamic ticket pricing (flight_price_features) and
commercial carrier operational reliability (flight_operations_features).
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from feature_engineering.base_transformer import (
    BaseFeatureTransformer,
    safe_divide,
    safe_log1p,
    bin_series,
)
from feature_engineering.config import BIN_CONFIGS


class FlightPriceFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms flight price observation records into regression features for dynamic pricing.
    """
    def __init__(self):
        super().__init__(name="flight_price_features")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # 1. Target Variable (INR ₹)
        out["price"] = df["price"].astype(float)
        out["price_log"] = safe_log1p(out["price"]).round(4)

        # 2. Days Left & Advance Booking Surge Curve
        out["days_left"] = df["days_left"].clip(lower=1).astype(int)
        out["days_left_bucket"] = bin_series(
            out["days_left"],
            bins=BIN_CONFIGS["flight_days_left"]["bins"],
            labels=BIN_CONFIGS["flight_days_left"]["labels"],
        )
        out["days_left_log"] = safe_log1p(out["days_left"]).round(4)
        out["is_immediate_departure"] = out["days_left"] <= 3

        # 3. Flight Duration & Haul Category
        out["duration_hours"] = df["duration"].astype(float).round(2)
        out["duration_minutes"] = (out["duration_hours"] * 60).round(1)
        out["duration_bucket"] = bin_series(
            out["duration_hours"],
            bins=BIN_CONFIGS["flight_duration"]["bins"],
            labels=BIN_CONFIGS["flight_duration"]["labels"],
        )

        # 4. Cabin Class & Stops
        out["class"] = df["class"].astype(str)
        out["is_business_class"] = (df["class"].str.lower() == "business")
        out["stops_count"] = df["stops_count"].clip(lower=0).astype(int)
        out["is_direct_flight"] = out["stops_count"] == 0

        # 5. Route & Carrier Attributes
        out["airline"] = df["airline"].astype(str)
        out["source_city"] = df["source_city"].astype(str)
        out["destination_city"] = df["destination_city"].astype(str)
        out["route"] = df["route"].astype(str)
        out["departure_time"] = df["departure_time"].astype(str)
        out["arrival_time"] = df["arrival_time"].astype(str)

        # 6. Metadata & Identifiers
        out["price_record_id"] = df["price_record_id"].astype(str) if "price_record_id" in df.columns else [f"P_{i}" for i in range(len(df))]
        out["currency"] = "INR"

        return out


class FlightOperationsFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms flight schedule and operational records into reliability & performance features.
    """
    def __init__(self):
        super().__init__(name="flight_operations_features")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # 1. Schedule Timing Features
        out["year"] = df["YEAR"].astype(int)
        out["month"] = df["MONTH"].astype(int)
        out["day"] = df["DAY"].astype(int)
        out["day_of_week"] = df["DAY_OF_WEEK"].astype(int)
        out["is_weekend_flight"] = df["DAY_OF_WEEK"].isin([6, 7])

        sched_dep = df["SCHEDULED_DEPARTURE"].fillna(0).astype(int)
        out["scheduled_departure_hour"] = sched_dep // 100
        out["scheduled_departure_minute"] = sched_dep % 100

        sched_arr = df["SCHEDULED_ARRIVAL"].fillna(0).astype(int)
        out["scheduled_arrival_hour"] = sched_arr // 100
        out["scheduled_arrival_minute"] = sched_arr % 100

        out["scheduled_elapsed_time_minutes"] = df["SCHEDULED_TIME"].fillna(0).astype(float)
        out["flight_distance_miles"] = df["DISTANCE"].fillna(0).astype(float)

        # 2. Route & Carrier
        out["airline"] = df["AIRLINE"].astype(str)
        out["flight_number"] = df["FLIGHT_NUMBER"].astype(str)
        out["origin_airport"] = df["ORIGIN_AIRPORT"].astype(str)
        out["destination_airport"] = df["DESTINATION_AIRPORT"].astype(str)
        out["route"] = df["ROUTE"].astype(str) if "ROUTE" in df.columns else (out["origin_airport"] + "-" + out["destination_airport"])

        # 3. Operational Indicators (Analytical Metrics)
        out["is_cancelled"] = df["CANCELLED"].fillna(0).astype(int)
        out["is_diverted"] = df["DIVERTED"].fillna(0).astype(int)
        arr_delay = pd.to_numeric(df["ARRIVAL_DELAY"], errors="coerce")
        out["arrival_delay_minutes"] = arr_delay.fillna(0.0).round(1)
        dep_delay = pd.to_numeric(df["DEPARTURE_DELAY"], errors="coerce")
        out["departure_delay_minutes"] = dep_delay.fillna(0.0).round(1)

        # On-Time arrival: arrived <= 15 min after scheduled, not cancelled or diverted
        out["is_ontime_arrival"] = (
            (arr_delay <= 15) & (out["is_cancelled"] == 0) & (out["is_diverted"] == 0)
        ).astype(int)

        out["unit"] = "MINUTES_AND_MILES"
        return out
