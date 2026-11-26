"""
optimization/predictions/flight_price.py

Flight price ceiling inference service using approved LightGBM model.
Predicts consumer market price ceiling without confusing it with wholesale cost.
Validates authentic routes and rejects unsupported markets without fake fallbacks.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from optimization.predictions.model_registry import ModelRegistry
from optimization.config import OptimizationConfig
from optimization.exceptions import ModelInferenceError

logger = logging.getLogger(__name__)


class FlightPriceService:
    """Predicts fair retail market price ceiling for supported flight routes."""

    TASK_NAME = "flight_price"

    # Supported cities in the trained flight price model domain
    SUPPORTED_CITIES = {"Bangalore", "Chennai", "Delhi", "Hyderabad", "Kolkata", "Mumbai"}

    # Canonical airport and destination code resolvers
    CODE_TO_CITY = {
        "DEL": "Delhi",
        "BOM": "Mumbai",
        "BLR": "Bangalore",
        "CCU": "Kolkata",
        "HYD": "Hyderabad",
        "MAA": "Chennai",
        "DEST001": "Delhi",
        "DEST002": "Mumbai",
        "DEST003": "Bangalore",
        "DEST004": "Kolkata",
        "DEST005": "Hyderabad",
        "DEST006": "Chennai",
        "ORG001": "Delhi",
        "ORG002": "Mumbai",
        "ORG003": "Bangalore",
        "ORG004": "Kolkata",
        "ORG005": "Hyderabad",
        "ORG006": "Chennai",
    }

    def __init__(self, registry: ModelRegistry, config: OptimizationConfig):
        self.registry = registry
        self.config = config
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [])

    def resolve_city(self, code_or_name: Any) -> Optional[str]:
        """Resolves city name from airport code, destination id, or literal city string."""
        if not code_or_name:
            return None
        s = str(code_or_name).strip().upper()
        if s in self.CODE_TO_CITY:
            return self.CODE_TO_CITY[s]
        # Check title case
        title_s = str(code_or_name).strip().title()
        if title_s in self.SUPPORTED_CITIES:
            return title_s
        return None

    def predict_market_ceiling_price(self, offer_record: Dict[str, Any]) -> Optional[float]:
        """
        Predicts consumer market price benchmark for supported route.
        Returns None if route or advance purchase horizon is outside the model domain.
        """
        travel_date_ts = pd.to_datetime(offer_record["travel_date"])
        opt_ts = pd.to_datetime(self.config.optimization_timestamp)
        days_left = (travel_date_ts - opt_ts).days

        # Validate trained days-left boundary [1, 49]
        if days_left < 1 or days_left > 49:
            logger.info("Flight offer travel date %s is outside model days_left window (days_left=%d).", offer_record["travel_date"], days_left)
            return None

        source_city = self.resolve_city(offer_record.get("origin_id"))
        dest_city = self.resolve_city(offer_record.get("destination_id"))

        if not source_city or not dest_city or source_city == dest_city:
            # Route cannot be authenticated against supported domain
            logger.info("Unsupported route endpoints (%s -> %s). Flight price ceiling prediction unavailable.", offer_record.get("origin_id"), offer_record.get("destination_id"))
            return None

        # Route format matching trained model schema (hyphenated: Delhi-Mumbai)
        route = f"{source_city}-{dest_city}"

        # Resolve duration and stops from offer if available
        duration_hrs = float(offer_record.get("duration_hours", 2.5))
        stops = int(offer_record.get("stops_count", 0))
        cabin_class = str(offer_record.get("cabin_class", "Economy")).title()
        if cabin_class not in ["Economy", "Business"]:
            cabin_class = "Economy"

        airline = str(offer_record.get("airline", "Air_India"))
        if airline not in ["AirAsia", "Air_India", "GO_FIRST", "Indigo", "SpiceJet", "Vistara"]:
            airline = "Air_India"

        feature_dict = {
            "days_left": int(days_left),
            "days_left_bucket": "1-3d" if days_left <= 3 else ("4-7d" if days_left <= 7 else ("8-14d" if days_left <= 14 else ("15-30d" if days_left <= 30 else "31d+"))),
            "days_left_log": float(np.log1p(days_left)),
            "is_immediate_departure": bool(days_left <= 2),
            "duration_hours": duration_hrs,
            "duration_minutes": duration_hrs * 60.0,
            "duration_bucket": "Short_Haul" if duration_hrs < 3.0 else ("Medium_Haul" if duration_hrs <= 6.0 else "Long_Haul"),
            "class": cabin_class,
            "is_business_class": bool(cabin_class == "Business"),
            "stops_count": stops,
            "is_direct_flight": bool(stops == 0),
            "airline": airline,
            "source_city": source_city,
            "destination_city": dest_city,
            "route": route,
            "departure_time": str(offer_record.get("departure_time", "Morning")).title(),
            "arrival_time": str(offer_record.get("arrival_time", "Afternoon")).title(),
        }

        row_df = pd.DataFrame([feature_dict])[self.expected_features]
        try:
            X_trans = self.preprocessor.transform(row_df) if self.preprocessor is not None else row_df
            raw_pred = self.estimator.predict(X_trans)
            pred_price = float(raw_pred[0]) if hasattr(raw_pred, "__len__") else float(raw_pred)
            return max(1000.0, pred_price)
        except Exception as exc:
            logger.error("Flight price model inference failed for route %s: %s", route, exc)
            return None

