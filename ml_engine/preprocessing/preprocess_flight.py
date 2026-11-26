"""
ml_engine/preprocessing/preprocess_flight.py

Domain feature preprocessing for flight price prediction.
Derives route, bucket, and log-transformed features required by the 17-feature model.
Enforces strict input validation: rejects missing route, airline, or departure parameters.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from ml_engine.exceptions import FeatureValidationError


class FlightFeaturePreprocessor:
    """Constructs the canonical 17 features required by the flight price LightGBM model."""

    EXPECTED_FEATURES = [
        "days_left", "days_left_bucket", "days_left_log", "is_immediate_departure",
        "duration_hours", "duration_minutes", "duration_bucket", "class",
        "is_business_class", "stops_count", "is_direct_flight", "airline",
        "source_city", "destination_city", "route", "departure_time", "arrival_time"
    ]

    REQUIRED_RAW_FIELDS = [
        "airline", "days_left"
    ]

    @staticmethod
    def validate_raw_record(raw_record: Dict[str, Any]) -> List[str]:
        """
        Validates presence of essential flight offer attributes.
        Returns list of missing field names.
        """
        missing = []
        for field in FlightFeaturePreprocessor.REQUIRED_RAW_FIELDS:
            if field not in raw_record or raw_record[field] is None:
                missing.append(field)

        # Check route endpoints
        source = raw_record.get("source_city") or raw_record.get("origin_city")
        dest = raw_record.get("destination_city") or raw_record.get("destination_id")
        if not source or not str(source).strip():
            missing.append("source_city")
        if not dest or not str(dest).strip():
            missing.append("destination_city")

        return missing

    @staticmethod
    def build_features(raw_record: Dict[str, Any], allow_imputation: bool = False) -> Dict[str, Any]:
        """
        Derives all required 17 features from booking/flight attributes.
        Raises FeatureValidationError if mandatory business attributes are missing.
        """
        missing = FlightFeaturePreprocessor.validate_raw_record(raw_record)
        if missing and not allow_imputation:
            raise FeatureValidationError(
                f"Missing required flight business fields: {missing}",
                missing_features=missing
            )

        days_left_raw = raw_record.get("days_left")
        if days_left_raw is None:
            if not allow_imputation:
                raise FeatureValidationError("Missing 'days_left' in flight record", missing_features=["days_left"])
            days_left = 30.0
        else:
            days_left = float(days_left_raw)

        if not np.isfinite(days_left) or days_left < 0:
            raise FeatureValidationError(f"Invalid days_left value: {days_left}")

        # Duration resolution
        dur_hrs_raw = raw_record.get("duration_hours")
        dur_mins_raw = raw_record.get("duration_minutes")
        if dur_hrs_raw is not None:
            duration_hrs = float(dur_hrs_raw)
            duration_mins = float(dur_mins_raw) if dur_mins_raw is not None else duration_hrs * 60.0
        elif dur_mins_raw is not None:
            duration_mins = float(dur_mins_raw)
            duration_hrs = duration_mins / 60.0
        else:
            duration_hrs = 2.5
            duration_mins = 150.0

        cabin_class_raw = raw_record.get("class", raw_record.get("cabin_class", "Economy"))
        cabin_class = str(cabin_class_raw).strip().capitalize() if cabin_class_raw else "Economy"
        stops = int(raw_record.get("stops_count", 0))

        source_raw = raw_record.get("source_city") or raw_record.get("origin_city")
        source = str(source_raw).strip() if source_raw else ""
        dest_raw = raw_record.get("destination_city") or raw_record.get("destination_id")
        dest = str(dest_raw).strip() if dest_raw else ""

        route = f"{source}-{dest}" if (source and dest) else str(raw_record.get("route", ""))

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

        airline_val = str(raw_record.get("airline", "")).strip()

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
            "airline": airline_val,
            "source_city": source,
            "destination_city": dest,
            "route": route,
            "departure_time": str(raw_record.get("departure_time", "Morning")),
            "arrival_time": str(raw_record.get("arrival_time", "Afternoon")),
        }
