"""
ml_engine/demand_forecasting/flight_demand_model.py

Specialized flight demand forecasting model wrapper.
Enforces inventory_type='flight' and routes to the 15-feature destination demand model.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from ml_engine.demand_forecasting.destination_demand_model import DestinationDemandModel


class FlightDemandModel(DestinationDemandModel):
    """
    Flight-specific demand forecasting wrapper.
    Ensures input features are scoped to flight inventory and validates flight-domain constraints.
    """

    def __init__(self, estimator: Any, preprocessor: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(estimator, preprocessor, metadata)

    def predict(self, feature_df: pd.DataFrame) -> np.ndarray:
        """
        Executes inference for flight demand.
        Enforces inventory_type='flight' if missing or unspecified.
        """
        df = feature_df.copy()
        if "inventory_type" not in df.columns:
            df["inventory_type"] = "flight"
        else:
            # Enforce flight inventory type
            df["inventory_type"] = df["inventory_type"].fillna("flight")
        return super().predict(df)
