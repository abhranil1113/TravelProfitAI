"""
ml_engine/datasets/price_dataset.py

Dataset wrapper for flight price prediction modeling.
Manages the 17-feature feature matrix and fare_amount ground-truth target.
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from ml_engine.exceptions import SchemaMismatchError, FeatureValidationError
from ml_engine.preprocessing.preprocess_flight import FlightFeaturePreprocessor


class PriceDataset:
    """
    Schema-aware dataset container for flight pricing prediction.
    Enforces the approved 17-feature matrix specification and pricing target.
    """

    FEATURE_NAMES: List[str] = FlightFeaturePreprocessor.FEATURE_NAMES
    TARGET_NAME: str = "price"

    def __init__(self, data: pd.DataFrame, target_col: Optional[str] = None):
        self.target_name = target_col or self.TARGET_NAME
        self.has_target = self.target_name in data.columns

        # Verify missing features
        missing = [f for f in self.FEATURE_NAMES if f not in data.columns]
        if missing:
            raise SchemaMismatchError(
                f"PriceDataset missing {len(missing)} required features: {missing[:5]}"
            )

        self._features = data[self.FEATURE_NAMES].copy()
        self._target = data[self.target_name].copy() if self.has_target else None

    def __len__(self) -> int:
        return len(self._features)

    def get_features(self) -> pd.DataFrame:
        """Returns the aligned 17-feature DataFrame."""
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
        """Calculates summary statistics of pricing distribution."""
        if self._target is None:
            return {"has_target": False}
        return {
            "has_target": True,
            "total_samples": len(self._target),
            "mean_price": float(self._target.mean()),
            "median_price": float(self._target.median()),
            "std_price": float(self._target.std()),
            "min_price": float(self._target.min()),
            "max_price": float(self._target.max()),
        }
