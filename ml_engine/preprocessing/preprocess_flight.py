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
            if not allow_imputation:
                raise FeatureValidationError("Missing 'duration_hours' or 'duration_minutes' in flight record", missing_features=["duration_hours"])
            duration_hrs = 2.5
            duration_mins = 150.0

        cabin_class_raw = raw_record.get("class", raw_record.get("cabin_class"))
        if cabin_class_raw is None:
            if not allow_imputation:
                raise FeatureValidationError("Missing cabin class in flight record", missing_features=["class"])
            cabin_class = "Economy"
        else:
            cabin_class = "Business" if str(cabin_class_raw).strip().lower() in ("business", "first") else "Economy"

        stops_raw = raw_record.get("stops_count")
        if stops_raw is None:
            if not allow_imputation:
                raise FeatureValidationError("Missing stops_count in flight record", missing_features=["stops_count"])
            stops = 0
        else:
            stops = int(stops_raw)

        source_raw = raw_record.get("source_city") or raw_record.get("origin_city")
        source = str(source_raw).strip() if source_raw else ""
        dest_raw = raw_record.get("destination_city") or raw_record.get("destination_id")
        dest = str(dest_raw).strip() if dest_raw else ""

        route = f"{source}-{dest}" if (source and dest) else str(raw_record.get("route", ""))

        # Days left bucketing aligned to fitted training transformer categories ['1-3d', '4-7d', '8-14d', '15-30d', '31d+']
        if days_left <= 3:
            bucket = "1-3d"
        elif days_left <= 7:
            bucket = "4-7d"
        elif days_left <= 14:
            bucket = "8-14d"
        elif days_left <= 30:
            bucket = "15-30d"
        else:
            bucket = "31d+"

        # Duration bucketing aligned to fitted training categories ['Short_Haul', 'Medium_Haul', 'Long_Haul', 'Ultra_Long_Haul']
        if duration_hrs <= 3.0:
            dur_bucket = "Short_Haul"
        elif duration_hrs <= 6.0:
            dur_bucket = "Medium_Haul"
        elif duration_hrs <= 12.0:
            dur_bucket = "Long_Haul"
        else:
            dur_bucket = "Ultra_Long_Haul"

        # Airline normalization aligned to fitted training categories ['AirAsia', 'Air_India', 'GO_FIRST', 'Indigo', 'SpiceJet', 'Vistara']
        airline_map = {
            "air india": "Air_India",
            "air_india": "Air_India",
            "airasia": "AirAsia",
            "go first": "GO_FIRST",
            "go_first": "GO_FIRST",
            "indigo": "Indigo",
            "spicejet": "SpiceJet",
            "vistara": "Vistara",
        }
        airline_raw = str(raw_record.get("airline", "")).strip()
        airline_val = airline_map.get(airline_raw.lower(), airline_raw)

        # Time slot normalization aligned to categories ['Afternoon', 'Early_Morning', 'Evening', 'Late_Night', 'Morning', 'Night']
        time_map = {
            "early morning": "Early_Morning",
            "early_morning": "Early_Morning",
            "late night": "Late_Night",
            "late_night": "Late_Night",
            "morning": "Morning",
            "afternoon": "Afternoon",
            "evening": "Evening",
            "night": "Night",
        }
        dep_raw = str(raw_record.get("departure_time", "Morning")).strip()
        arr_raw = str(raw_record.get("arrival_time", "Afternoon")).strip()
        dep_val = time_map.get(dep_raw.lower(), dep_raw)
        arr_val = time_map.get(arr_raw.lower(), arr_raw)

        return {
            "days_left": days_left,
            "days_left_bucket": bucket,
            "days_left_log": float(np.log1p(max(0.0, days_left))),
            "is_immediate_departure": int(days_left <= 3),
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
            "departure_time": dep_val,
            "arrival_time": arr_val,
        }
