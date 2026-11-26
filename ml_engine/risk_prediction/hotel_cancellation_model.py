"""
ml_engine/risk_prediction/hotel_cancellation_model.py

47-feature hotel cancellation classification model wrapper.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


class HotelCancellationModel:
    """Estimator wrapper for hotel cancellation probability model."""

    def __init__(self, estimator: Any, preprocessor: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None):
        self.estimator = estimator
        self.preprocessor = preprocessor
        self.metadata = metadata or {}
        self.feature_names: List[str] = self.metadata.get("feature_names", [])

    def predict_proba(self, feature_df: pd.DataFrame) -> np.ndarray:
        aligned = feature_df[self.feature_names].copy()
        X_trans = self.preprocessor.transform(aligned) if self.preprocessor is not None else aligned
        if hasattr(self.estimator, "predict_proba"):
            return self.estimator.predict_proba(X_trans)
        raw_pred = self.estimator.predict(X_trans)
        return np.column_stack([1.0 - raw_pred, raw_pred])
