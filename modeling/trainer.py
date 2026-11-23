"""
TBO InventoryIQ - Single Model Trainer & Inference Container (Phase 4)
Handles pipeline fitting, feature transformation, inference timing,
and prediction generation.
"""

from typing import Dict, Any, Optional, List, Tuple
import time
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer

from modeling.config import TaskType


class ModelArtifact:
    """
    Inference-ready container bundling a fitted estimator, fitted preprocessor,
    feature names, and model metadata.
    """
    def __init__(
        self,
        estimator: BaseEstimator,
        preprocessor: Optional[ColumnTransformer],
        feature_names: List[str],
        task_type: TaskType,
        fit_time_seconds: float = 0.0,
        model_name: str = "",
    ):
        self.estimator = estimator
        self.preprocessor = preprocessor
        self.feature_names = feature_names
        self.task_type = task_type
        self.fit_time_seconds = fit_time_seconds
        self.model_name = model_name

    def transform_features(self, X: pd.DataFrame) -> np.ndarray:
        """Transforms input DataFrame using the fold-fitted preprocessor."""
        # Align features to expected columns
        X_aligned = X[self.feature_names].copy()
        if self.preprocessor is not None:
            return self.preprocessor.transform(X_aligned)
        return X_aligned.to_numpy()

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, float]:
        """
        Generates predictions and records inference duration.
        """
        start = time.perf_counter()
        X_trans = self.transform_features(X)
        preds = self.estimator.predict(X_trans)
        elapsed = time.perf_counter() - start
        return preds, elapsed

    def predict_proba(self, X: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Generates probability estimates for classification tasks if supported.
        """
        if hasattr(self.estimator, "predict_proba"):
            X_trans = self.transform_features(X)
            return self.estimator.predict_proba(X_trans)
        return None


def train_single_model(
    estimator: BaseEstimator,
    preprocessor: Optional[ColumnTransformer],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    task_type: TaskType,
    model_name: str = "",
) -> ModelArtifact:
    """
    Fits preprocessor strictly on X_train, transforms features,
    and trains the estimator without target or validation leakage.
    """
    start_time = time.perf_counter()

    feature_names = list(X_train.columns)
    if preprocessor is not None:
        X_trans = preprocessor.fit_transform(X_train, y_train)
    else:
        X_trans = X_train.to_numpy()

    # Fit estimator
    estimator.fit(X_trans, y_train)
    fit_duration = time.perf_counter() - start_time

    return ModelArtifact(
        estimator=estimator,
        preprocessor=preprocessor,
        feature_names=feature_names,
        task_type=task_type,
        fit_time_seconds=round(fit_duration, 4),
        model_name=model_name,
    )
