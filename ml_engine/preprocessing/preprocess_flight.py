"""
ml_engine/preprocessing/preprocess_flight.py

Domain feature preprocessing for flight price prediction.
Derives route, bucket, and log-transformed features required by the 17-feature model.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd


class FlightFeaturePreprocessor:
    """Constructs the canonical 17 features required by the flight price LightGBM model."""

    EXPECTED_FEATURES = [
        "days_left", "days_left_bucket", "days_left_log", "is_immediate_departure",
        "duration_hours", "duration_minutes", "duration_bucket", "class",
        "is_business_class", "stops_count", "is_direct_flight", "airline",
        "source_city", "destination_city", "route", "departure_time", "arrival_time"
    ]

    @staticmethod
    def build_features(raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derives all required features from booking/flight attributes.
        """
        days_left = float(raw_record.get("days_left", 30))
        duration_hrs = float(raw_record.get("duration_hours", 2.5))
        duration_mins = float(raw_record.get("duration_minutes", duration_hrs * 60.0))
        cabin_class = str(raw_record.get("class", raw_record.get("cabin_class", "Economy"))).capitalize()
        stops = int(raw_record.get("stops_count", 0))

        source = str(raw_record.get("source_city", raw_record.get("origin_city", "Delhi"))).strip()
        dest = str(raw_record.get("destination_city", raw_record.get("destination_id", "Mumbai"))).strip()
        route = f"{source}-{dest}"

        # Days left bucketing
        if days_left <= 2:
            bucket = "0-2 days"
        elif days_left <= 7:
            bucket = "3-7 days"
        elif days_left <= 15:
            bucket = "8-15 days"
        elif days_left <= 30:
            bucket = "16-30 days"
        else:
            bucket = "31+ days"

        # Duration bucketing
        if duration_hrs <= 3:
            dur_bucket = "Short (<3h)"
        elif duration_hrs <= 6:
            dur_bucket = "Medium (3-6h)"
        else:
            dur_bucket = "Long (>6h)"

        return {
            "days_left": days_left,
            "days_left_bucket": bucket,
            "days_left_log": float(np.log1p(max(0.0, days_left))),
            "is_immediate_departure": int(days_left <= 2),
            "duration_hours": duration_hrs,
            "duration_minutes": duration_mins,
            "duration_bucket": dur_bucket,
            "class": cabin_class,
            "is_business_class": int(cabin_class.lower() in ("business", "first")),
            "stops_count": stops,
            "is_direct_flight": int(stops == 0),
            "airline": str(raw_record.get("airline", "Air India")),
            "source_city": source,
            "destination_city": dest,
            "route": route,
            "departure_time": str(raw_record.get("departure_time", "Morning")),
            "arrival_time": str(raw_record.get("arrival_time", "Afternoon")),
        }
