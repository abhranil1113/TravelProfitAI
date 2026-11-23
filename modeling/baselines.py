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


class NaiveForecaster(BaseEstimator, RegressorMixin):
    """
    Predicts the most recent past observation (persistence forecast).
    If a 'lag_1' column exists in X, it outputs that directly;
    otherwise predicts the final observed value of y from the training period.
    """
    def __init__(self, lag_col: str = "lag_1"):
        self.lag_col = lag_col
        self.last_value_: float = 0.0

    def fit(self, X, y=None):
        if y is not None and len(y) > 0:
            self.last_value_ = float(np.asarray(y)[-1])
        return self

    def predict(self, X):
        if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
            return X[self.lag_col].to_numpy()
        n = len(X)
        return np.full(n, self.last_value_)


class SeasonalNaiveForecaster(BaseEstimator, RegressorMixin):
    """
    Predicts the observation from the previous seasonal cycle (e.g., lag 7 for weekly seasonality).
    If a 'lag_7' column exists in X, outputs that directly;
    otherwise repeats the last S observations of y from training.
    """
    def __init__(self, seasonal_period: int = 7, lag_col: str = "lag_7"):
        self.seasonal_period = seasonal_period
        self.lag_col = lag_col
        self.seasonal_history_: np.ndarray = np.array([])

    def fit(self, X, y=None):
        if y is not None and len(y) > 0:
            arr = np.asarray(y)
            p = min(self.seasonal_period, len(arr))
            self.seasonal_history_ = arr[-p:]
        return self

    def predict(self, X):
        if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
            return X[self.lag_col].to_numpy()
        n = len(X)
        if len(self.seasonal_history_) == 0:
            return np.zeros(n)
        repeats = int(np.ceil(n / len(self.seasonal_history_)))
        tiled = np.tile(self.seasonal_history_, repeats)
        return tiled[:n]


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
