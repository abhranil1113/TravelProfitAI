"""
ml_engine/datasets/flight_demand_dataset.py

Dataset wrapper for flight search demand panel modeling.
Manages the 15-feature feature matrix and search_volume ground-truth target.
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from ml_engine.exceptions import SchemaMismatchError, FeatureValidationError


class FlightDemandDataset:
    """
    Schema-aware dataset container for flight demand forecasting.
    Enforces the approved 15-feature matrix specification for flight inventory.
    """

    FEATURE_NAMES: List[str] = [
        "destination_id", "inventory_type", "search_volume", "total_travellers",
        "avg_search_price", "lag_1", "lag_7", "lag_14", "rolling_mean_7",
        "rolling_mean_14", "rolling_std_7", "day_of_week", "is_weekend", "month", "quarter"
    ]
    TARGET_NAME: str = "search_volume"

    def __init__(self, data: pd.DataFrame, target_col: Optional[str] = None):
        self.target_name = target_col or self.TARGET_NAME
        self.has_target = self.target_name in data.columns

        # Verify missing features
        missing = [f for f in self.FEATURE_NAMES if f not in data.columns]
        if missing:
            raise SchemaMismatchError(
                f"FlightDemandDataset missing {len(missing)} required features: {missing[:5]}"
            )

        self._features = data[self.FEATURE_NAMES].copy()
        # Enforce flight inventory
        self._features["inventory_type"] = "flight"
        self._target = data[self.target_name].copy() if self.has_target else None

    def __len__(self) -> int:
        return len(self._features)

    def get_features(self) -> pd.DataFrame:
        """Returns the aligned 15-feature DataFrame."""
        return self._features

    def get_target(self) -> Optional[pd.Series]:
        """Returns the target series if present."""
        return self._target

    def to_numpy(self) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Converts features and optional targets to NumPy arrays."""
        X = self._features.to_numpy()
        y = self._target.to_numpy() if self._target is not None else None
        return X, y

    def get_statistics(self) -> Dict[str, Any]:
        """Calculates summary statistics of search volume demand."""
        if self._target is None:
            return {"has_target": False}
        return {
            "has_target": True,
            "total_observations": len(self._target),
            "mean_demand": float(self._target.mean()),
            "median_demand": float(self._target.median()),
            "std_demand": float(self._target.std()),
            "min_demand": float(self._target.min()),
            "max_demand": float(self._target.max()),
        }
