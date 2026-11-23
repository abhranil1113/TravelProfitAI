"""
TBO InventoryIQ - Hyperparameter Tuning Engine (Phase 4)
Provides randomized and grid search tuning interfaces strictly executed
on the training portion, preventing test set leakage.
"""

from typing import Dict, Any, Optional, Tuple
import logging
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator
import pandas as pd

from modeling.config import (
    TaskType,
    ValidationStrategy,
    RANDOM_SEED,
    DEFAULT_PARAM_GRIDS,
)
from modeling.registry.task_registry import TaskConfig
from modeling.preprocessing import build_preprocessor, partition_features
from modeling.splitters import get_cross_validation_splitter
from modeling.model_factory import create_model

logger = logging.getLogger(__name__)


def tune_model_hyperparameters(
    task_config: TaskConfig,
    model_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    param_grid: Optional[Dict[str, Any]] = None,
    n_iter: int = 5,
    cv_splits: int = 3,
) -> Tuple[BaseEstimator, Dict[str, Any], float]:
    """
    Executes RandomizedSearchCV strictly over X_train using an integrated Pipeline.
    
    Returns:
      (best_estimator, best_params, best_score)
    """
    grid = param_grid or DEFAULT_PARAM_GRIDS.get(model_name, {})
    if not grid:
        logger.info(f"No param grid configured for '{model_name}'. Returning default model.")
        base = create_model(model_name, task_config.task_type)
        return base, {}, 0.0

    # 1. Build Preprocessor
    num_cols, cat_cols = partition_features(X_train)
    scale_numeric = model_name in ["logistic_regression", "linear_regression"]
    preprocessor = build_preprocessor(num_cols, cat_cols, scale_numeric=scale_numeric)

    # 2. Build Pipeline
    estimator = create_model(model_name, task_config.task_type)
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("model", estimator),
    ])

    # Prefix parameter keys with 'model__' for the Pipeline
    pipelined_grid = {f"model__{k}": v for k, v in grid.items()}

    # 3. Determine Scoring Function
    is_classification = task_config.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]
    scoring = "f1" if is_classification else "neg_mean_absolute_error"

    # 4. Determine Splitter
    splitter = get_cross_validation_splitter(
        task_config.validation_strategy,
        n_splits=cv_splits,
        shuffle=(task_config.validation_strategy != ValidationStrategy.TIME_SERIES_SPLIT),
        random_state=RANDOM_SEED,
    )

    logger.info(
        f"Starting hyperparameter tuning for '{model_name}' on task '{task_config.task_name}' "
        f"({n_iter} iterations, {cv_splits} CV folds)..."
    )

    search = RandomizedSearchCV(
        estimator=pipeline,
        param_distributions=pipelined_grid,
        n_iter=n_iter,
        scoring=scoring,
        cv=splitter,
        random_state=RANDOM_SEED,
        n_jobs=-1,
        refit=True,
    )

    search.fit(X_train, y_train)

    # Clean parameter names by removing 'model__' prefix
    best_params = {k.replace("model__", ""): v for k, v in search.best_params_.items()}
    best_score = float(search.best_score_)

    logger.info(f"Tuning complete for '{model_name}': best_score={best_score:.4f}, params={best_params}")

    return search.best_estimator_, best_params, best_score
