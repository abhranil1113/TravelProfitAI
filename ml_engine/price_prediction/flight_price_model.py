"""
ml_engine/price_prediction/flight_price_model.py

17-feature flight price prediction model wrapper.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


class FlightPriceModel:
    """Estimator wrapper for flight price regression model."""

    EXPECTED_FEATURES = [
        "days_left", "days_left_bucket", "days_left_log", "is_immediate_departure",
        "duration_hours", "duration_minutes", "duration_bucket", "class",
        "is_business_class", "stops_count", "is_direct_flight", "airline",
        "source_city", "destination_city", "route", "departure_time", "arrival_time"
    ]

    def __init__(self, estimator: Any, preprocessor: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None):
        self.estimator = estimator
        self.preprocessor = preprocessor
        self.metadata = metadata or {}
        self.feature_names = self.metadata.get("feature_names", self.EXPECTED_FEATURES)

    def predict(self, feature_df: pd.DataFrame) -> np.ndarray:
        aligned = feature_df[self.feature_names].copy()
        X_trans = self.preprocessor.transform(aligned) if self.preprocessor is not None else aligned
        raw_pred = self.estimator.predict(X_trans)
        return np.clip(np.nan_to_num(raw_pred, nan=0.0), a_min=0.0, a_max=None)
