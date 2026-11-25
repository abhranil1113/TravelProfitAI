"""
TBO InventoryIQ - Baseline Estimators (Phase 4)
Implements standard statistical and heuristic baselines for classification,
regression, and time-series forecasting.
"""

from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression

from modeling.config import TaskType, RANDOM_SEED


import logging

logger = logging.getLogger(__name__)


class NaiveForecaster(BaseEstimator, RegressorMixin):
    """
    Predicts the most recent past observation (persistence forecast).
    Supports both pandas DataFrame inputs and NumPy 2D array inputs.
    If lag_col (default 'lag_1') exists in X (or lag_col_idx is known),
    it outputs that feature directly; otherwise falls back to the final observed
    value of y from the training period with an explicit warning.
    """
    def __init__(self, lag_col: str = "lag_1", lag_col_idx: Optional[int] = None):
        self.lag_col = lag_col
        self.lag_col_idx = lag_col_idx
        self.last_value_: float = 0.0
        self.lag_col_idx_: Optional[int] = lag_col_idx

    def fit(self, X, y=None):
        if y is not None and len(y) > 0:
            self.last_value_ = float(np.asarray(y)[-1])
        if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
            self.lag_col_idx_ = int(X.columns.get_loc(self.lag_col))
        elif self.lag_col_idx is not None:
            self.lag_col_idx_ = int(self.lag_col_idx)
        return self

    def predict(self, X):
        preds = None
        # Path A: Input is a pandas DataFrame with lag_col
        if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
            preds = X[self.lag_col].to_numpy().astype(float)
        # Path B: Input is a NumPy array (or DataFrame) and lag_col_idx_ is known
        elif hasattr(self, "lag_col_idx_") and self.lag_col_idx_ is not None:
            if isinstance(X, np.ndarray) and 0 <= self.lag_col_idx_ < X.shape[1]:
                preds = X[:, self.lag_col_idx_].astype(float)
            elif isinstance(X, pd.DataFrame) and 0 <= self.lag_col_idx_ < X.shape[1]:
                preds = X.iloc[:, self.lag_col_idx_].to_numpy().astype(float)

        # Fallback: Constant persistence from last training observation
        if preds is None:
            n = len(X)
            logger.warning(
                f"NaiveForecaster: Column '{self.lag_col}' (idx={getattr(self, 'lag_col_idx_', None)}) "
                f"not resolvable in input of type {type(X)}. Falling back to last_value_={self.last_value_}."
            )
            preds = np.full(n, self.last_value_, dtype=float)

        # Safeguard: detect silent all-zero predictions on non-empty inputs
        if len(preds) > 0 and np.all(preds == 0.0):
            logger.warning(
                f"NaiveForecaster SAFEGUARD WARNING: All {len(preds)} predictions are exactly 0.0."
            )
        return preds


class SeasonalNaiveForecaster(BaseEstimator, RegressorMixin):
    """
    Predicts the observation from the previous seasonal cycle (e.g., lag 7 for weekly seasonality).
    Supports both pandas DataFrame inputs and NumPy 2D array inputs.
    If lag_col (default 'lag_7') exists in X (or lag_col_idx is known),
    it outputs that feature directly; otherwise repeats the last S observations of y from training.
    """
    def __init__(self, seasonal_period: int = 7, lag_col: str = "lag_7", lag_col_idx: Optional[int] = None):
        self.seasonal_period = seasonal_period
        self.lag_col = lag_col
        self.lag_col_idx = lag_col_idx
        self.seasonal_history_: np.ndarray = np.array([])
        self.lag_col_idx_: Optional[int] = lag_col_idx

    def fit(self, X, y=None):
        if y is not None and len(y) > 0:
            arr = np.asarray(y)
            p = min(self.seasonal_period, len(arr))
            self.seasonal_history_ = arr[-p:]
        if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
            self.lag_col_idx_ = int(X.columns.get_loc(self.lag_col))
        elif self.lag_col_idx is not None:
            self.lag_col_idx_ = int(self.lag_col_idx)
        return self

    def predict(self, X):
        preds = None
        # Path A: Input is a pandas DataFrame with lag_col
        if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
            preds = X[self.lag_col].to_numpy().astype(float)
        # Path B: Input is a NumPy array (or DataFrame) and lag_col_idx_ is known
        elif hasattr(self, "lag_col_idx_") and self.lag_col_idx_ is not None:
            if isinstance(X, np.ndarray) and 0 <= self.lag_col_idx_ < X.shape[1]:
                preds = X[:, self.lag_col_idx_].astype(float)
            elif isinstance(X, pd.DataFrame) and 0 <= self.lag_col_idx_ < X.shape[1]:
                preds = X.iloc[:, self.lag_col_idx_].to_numpy().astype(float)

        # Fallback: Tiled seasonal history from training period
        if preds is None:
            n = len(X)
            logger.warning(
                f"SeasonalNaiveForecaster: Column '{self.lag_col}' (idx={getattr(self, 'lag_col_idx_', None)}) "
                f"not resolvable in input of type {type(X)}. Falling back to tiled seasonal history."
            )
            if len(self.seasonal_history_) == 0:
                preds = np.zeros(n, dtype=float)
            else:
                repeats = int(np.ceil(n / len(self.seasonal_history_)))
                tiled = np.tile(self.seasonal_history_, repeats)
                preds = tiled[:n].astype(float)

        # Safeguard: detect silent all-zero predictions on non-empty inputs
        if len(preds) > 0 and np.all(preds == 0.0):
            logger.warning(
                f"SeasonalNaiveForecaster SAFEGUARD WARNING: All {len(preds)} predictions are exactly 0.0."
            )
        return preds


def create_baseline_model(
    model_name: str,
    task_type: TaskType,
    random_state: int = RANDOM_SEED,
    **kwargs,
) -> BaseEstimator:
    """
    Factory creating a task-compatible baseline estimator.
    """
    name_clean = model_name.lower().strip()

    if task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]:
        if name_clean == "dummy":
            strategy = kwargs.get("strategy", "stratified")
            return DummyClassifier(strategy=strategy, random_state=random_state)
        elif name_clean in ["logistic_regression", "logistic"]:
            max_iter = kwargs.get("max_iter", 1000)
            C = kwargs.get("C", 1.0)
            return LogisticRegression(max_iter=max_iter, C=C, random_state=random_state)
        raise ValueError(f"Unknown classification baseline '{model_name}'.")

    elif task_type in [TaskType.REGRESSION, TaskType.TIME_SERIES_REGRESSION]:
        if name_clean == "dummy":
            strategy = kwargs.get("strategy", "mean")
            return DummyRegressor(strategy=strategy)
        elif name_clean in ["linear_regression", "linear"]:
            return LinearRegression()
        elif name_clean == "naive":
            lag_col = kwargs.get("lag_col", "lag_1")
            return NaiveForecaster(lag_col=lag_col)
        elif name_clean in ["seasonal_naive", "snaive"]:
            period = kwargs.get("seasonal_period", 7)
            lag_col = kwargs.get("lag_col", f"lag_{period}")
            return SeasonalNaiveForecaster(seasonal_period=period, lag_col=lag_col)
        raise ValueError(f"Unknown regression baseline '{model_name}'.")

    raise ValueError(f"Unsupported task type for baselines: {task_type}")
