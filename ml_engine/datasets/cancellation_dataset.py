"""
ml_engine/datasets/cancellation_dataset.py

Dataset wrapper for hotel booking cancellation modeling.
Manages the 47-feature feature matrix and is_cancelled ground-truth label.
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from ml_engine.exceptions import SchemaMismatchError, FeatureValidationError
from ml_engine.preprocessing.preprocess_hotel import HotelFeaturePreprocessor


class CancellationDataset:
    """
    Schema-aware dataset container for hotel cancellation prediction.
    Enforces the approved 47-feature matrix specification and handles class labeling.
    """

    FEATURE_NAMES: List[str] = HotelFeaturePreprocessor.FEATURE_NAMES
    TARGET_NAME: str = "is_cancelled"

    def __init__(self, data: pd.DataFrame, target_col: Optional[str] = None):
        self.target_name = target_col or self.TARGET_NAME
        self.has_target = self.target_name in data.columns

        # Verify missing features
        missing = [f for f in self.FEATURE_NAMES if f not in data.columns]
        if missing:
            raise SchemaMismatchError(
                f"CancellationDataset missing {len(missing)} required features: {missing[:5]}"
            )

        self._features = data[self.FEATURE_NAMES].copy()
        self._target = data[self.target_name].copy() if self.has_target else None

    def __len__(self) -> int:
        return len(self._features)

    def get_features(self) -> pd.DataFrame:
        """Returns the aligned 47-feature DataFrame."""
        return self._features

    def get_target(self) -> Optional[pd.Series]:
        """Returns the target series if present."""
        return self._target

    def to_numpy(self) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Converts features and optional targets to NumPy arrays."""
        X = self._features.to_numpy()
        y = self._target.to_numpy() if self._target is not None else None
        return X, y

    def get_class_distribution(self) -> Dict[str, Any]:
        """Calculates class balance metrics for cancellation labels."""
        if self._target is None:
            return {"has_target": False}
        total = len(self._target)
        cancelled = int((self._target == 1).sum())
        non_cancelled = total - cancelled
        return {
            "has_target": True,
            "total_samples": total,
            "cancelled_count": cancelled,
            "non_cancelled_count": non_cancelled,
            "cancellation_rate": cancelled / max(1, total),
        }
