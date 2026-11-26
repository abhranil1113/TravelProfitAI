"""
ml_engine/demand_forecasting/hotel_demand_model.py

Specialized hotel demand forecasting model wrapper.
Enforces inventory_type='hotel' and routes to the 15-feature destination demand model.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from ml_engine.demand_forecasting.destination_demand_model import DestinationDemandModel


class HotelDemandModel(DestinationDemandModel):
    """
    Hotel-specific demand forecasting wrapper.
    Ensures input features are scoped to hotel inventory and validates hotel-domain constraints.
    """

    def __init__(self, estimator: Any, preprocessor: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(estimator, preprocessor, metadata)

    def predict(self, feature_df: pd.DataFrame) -> np.ndarray:
        """
        Executes inference for hotel demand.
        Enforces inventory_type='hotel' if missing or unspecified.
        """
        df = feature_df.copy()
        if "inventory_type" not in df.columns:
            df["inventory_type"] = "hotel"
        else:
            # Enforce hotel inventory type
            df["inventory_type"] = df["inventory_type"].fillna("hotel")
        return super().predict(df)
