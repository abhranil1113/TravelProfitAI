"""
TBO InventoryIQ - Unified Model Factory (Phase 4)
Instantiates baseline and advanced ML estimators (Random Forest, XGBoost, LightGBM)
with strict task compatibility verification and deterministic random states.
"""

from typing import Dict, Any, Optional
import logging
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
import xgboost as xgb
import lightgbm as lgb

from modeling.config import TaskType, RANDOM_SEED, SUPPORTED_MODELS
from modeling.baselines import create_baseline_model

logger = logging.getLogger(__name__)


def create_model(
    model_name: str,
    task_type: TaskType,
    random_state: int = RANDOM_SEED,
    **kwargs,
) -> BaseEstimator:
    """
    Factory creating a task-compatible candidate estimator.
    Validates model compatibility against the declared TaskType.
    """
    name_clean = model_name.lower().strip()
    supported = SUPPORTED_MODELS.get(task_type, [])

    if name_clean not in supported:
        raise ValueError(
            f"Model '{model_name}' is not supported for task type '{task_type.value}'. "
            f"Compatible estimators: {supported}"
        )

    # 1. Baseline Estimators
    if name_clean in ["dummy", "logistic_regression", "linear_regression", "naive", "seasonal_naive"]:
        return create_baseline_model(name_clean, task_type, random_state=random_state, **kwargs)

    # 2. Random Forest
    if name_clean == "random_forest":
        rf_params = {
            "n_estimators": kwargs.get("n_estimators", 100),
            "max_depth": kwargs.get("max_depth", 10),
            "min_samples_split": kwargs.get("min_samples_split", 2),
            "min_samples_leaf": kwargs.get("min_samples_leaf", 1),
            "random_state": random_state,
            "n_jobs": kwargs.get("n_jobs", -1),
        }
        for k, v in kwargs.items():
            if k not in rf_params:
                rf_params[k] = v

        if task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]:
            return RandomForestClassifier(**rf_params)
        else:
            return RandomForestRegressor(**rf_params)

    # 3. XGBoost
    elif name_clean == "xgboost":
        xgb_params = {
            "n_estimators": kwargs.get("n_estimators", 100),
            "max_depth": kwargs.get("max_depth", 5),
            "learning_rate": kwargs.get("learning_rate", 0.1),
            "subsample": kwargs.get("subsample", 0.8),
            "colsample_bytree": kwargs.get("colsample_bytree", 0.8),
            "random_state": random_state,
            "verbosity": 0,
            "n_jobs": kwargs.get("n_jobs", -1),
        }
        if task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]:
            xgb_params["eval_metric"] = "logloss"
            for k, v in kwargs.items():
                xgb_params[k] = v
            return xgb.XGBClassifier(**xgb_params)
        else:
            for k, v in kwargs.items():
                xgb_params[k] = v
            return xgb.XGBRegressor(**xgb_params)

    # 4. LightGBM
    elif name_clean == "lightgbm":
        lgb_params = {
            "n_estimators": kwargs.get("n_estimators", 100),
            "num_leaves": kwargs.get("num_leaves", 31),
            "max_depth": kwargs.get("max_depth", 6),
            "learning_rate": kwargs.get("learning_rate", 0.1),
            "random_state": random_state,
            "verbosity": -1,
            "n_jobs": kwargs.get("n_jobs", -1),
        }
        for k, v in kwargs.items():
            lgb_params[k] = v

        if task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]:
            return lgb.LGBMClassifier(**lgb_params)
        else:
            return lgb.LGBMRegressor(**lgb_params)

    raise ValueError(f"Unhandled estimator name: '{model_name}'.")
