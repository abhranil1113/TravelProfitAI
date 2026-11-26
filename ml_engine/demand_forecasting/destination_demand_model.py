"""
ml_engine/demand_forecasting/destination_demand_model.py

15-feature destination search demand model wrapper.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


class DestinationDemandModel:
    """Wrapper managing inference for the 15-feature demand model."""

    EXPECTED_FEATURES = [
        "destination_id", "inventory_type", "search_volume", "total_travellers",
        "avg_search_price", "lag_1", "lag_7", "lag_14", "rolling_mean_7",
        "rolling_mean_14", "rolling_std_7", "day_of_week", "is_weekend", "month", "quarter"
    ]

    def __init__(self, estimator: Any, preprocessor: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None):
        self.estimator = estimator
        self.preprocessor = preprocessor
        self.metadata = metadata or {}
        self.feature_names = self.metadata.get("feature_names", self.EXPECTED_FEATURES)

    def predict(self, feature_df: pd.DataFrame) -> np.ndarray:
        """Executes transformation and prediction, returning non-negative bounded predictions."""
        aligned = feature_df[self.feature_names].copy()
        X_trans = self.preprocessor.transform(aligned) if self.preprocessor is not None else aligned
        raw_pred = self.estimator.predict(X_trans)
        return np.clip(np.nan_to_num(raw_pred, nan=0.0), a_min=0.0, a_max=None)
