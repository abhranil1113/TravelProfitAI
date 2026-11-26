"""
ml_engine/demand_forecasting/baseline.py

Baseline demand forecasters with array and DataFrame support.
Provides naive lag-1 and seasonal lag-7 benchmarks.
"""

from typing import Union, Optional
import numpy as np
import pandas as pd


class NaiveForecaster:
    """Predicts target using the most recent observation (lag-1)."""

    def __init__(self, lag_feature: str = "lag_1", fallback_value: float = 0.0):
        self.lag_feature = lag_feature
        self.fallback_value = fallback_value

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            if self.lag_feature in X.columns:
                return X[self.lag_feature].fillna(self.fallback_value).to_numpy()
            return np.full(len(X), self.fallback_value)
        elif isinstance(X, np.ndarray):
            if X.ndim == 2 and X.shape[1] >= 6:
                # lag_1 is index 5 in the 15-feature schema
                vals = X[:, 5]
                return np.nan_to_num(vals, nan=self.fallback_value)
            return np.full(len(X), self.fallback_value)
        return np.array([self.fallback_value])


class SeasonalNaiveForecaster:
    """Predicts target using the 7-day seasonal observation (lag-7)."""

    def __init__(self, lag_feature: str = "lag_7", fallback_value: float = 0.0):
        self.lag_feature = lag_feature
        self.fallback_value = fallback_value

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            if self.lag_feature in X.columns:
                return X[self.lag_feature].fillna(self.fallback_value).to_numpy()
            return np.full(len(X), self.fallback_value)
        elif isinstance(X, np.ndarray):
            if X.ndim == 2 and X.shape[1] >= 7:
                # lag_7 is index 6 in the 15-feature schema
                vals = X[:, 6]
                return np.nan_to_num(vals, nan=self.fallback_value)
            return np.full(len(X), self.fallback_value)
        return np.array([self.fallback_value])
