"""
TBO InventoryIQ - Modeling Configuration & Constants (Phase 4)
Defines project-wide filesystem paths, random seeds, task types,
supported model families, and default parameters.
"""

from pathlib import Path
from typing import Dict, List, Any
from enum import Enum


# Project Root Directory Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FEATURES_DATA_DIR = DATA_DIR / "features"
MODELS_DIR = DATA_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports" / "model_evaluation"

# Ensure runtime directories exist
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Global Reproducibility Seed
RANDOM_SEED: int = 42


class TaskType(str, Enum):
    """Supported prediction task categories in the extensible ML framework."""
    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION = "regression"
    TIME_SERIES_REGRESSION = "time_series_regression"


class ValidationStrategy(str, Enum):
    """Supported cross-validation splitting strategies."""
    STRATIFIED_KFOLD = "stratified_kfold"
    KFOLD = "kfold"
    TIME_SERIES_SPLIT = "time_series_split"
    GROUP_KFOLD = "group_kfold"
    CHRONOLOGICAL_SPLIT = "chronological_split"


# Supported Model Identifiers
SUPPORTED_MODELS: Dict[TaskType, List[str]] = {
    TaskType.BINARY_CLASSIFICATION: [
        "dummy",
        "logistic_regression",
        "random_forest",
        "xgboost",
        "lightgbm",
    ],
    TaskType.MULTICLASS_CLASSIFICATION: [
        "dummy",
        "logistic_regression",
        "random_forest",
        "xgboost",
        "lightgbm",
    ],
    TaskType.REGRESSION: [
        "dummy",
        "linear_regression",
        "random_forest",
        "xgboost",
        "lightgbm",
    ],
    TaskType.TIME_SERIES_REGRESSION: [
        "naive",
        "seasonal_naive",
        "linear_regression",
        "random_forest",
        "xgboost",
        "lightgbm",
    ],
}

# Default Primary Optimization Metrics by Task Type
DEFAULT_PRIMARY_METRICS: Dict[TaskType, str] = {
    TaskType.BINARY_CLASSIFICATION: "f1_score",
    TaskType.MULTICLASS_CLASSIFICATION: "macro_f1",
    TaskType.REGRESSION: "mae",
    TaskType.TIME_SERIES_REGRESSION: "mae",
}

# Metric Direction (True if higher is better, False if lower is better)
METRIC_DIRECTION_IS_HIGHER_BETTER: Dict[str, bool] = {
    "f1_score": True,
    "roc_auc": True,
    "pr_auc": True,
    "precision": True,
    "recall": True,
    "accuracy": True,
    "log_loss": False,
    "r2": True,
    "mae": False,
    "rmse": False,
    "mape": False,
    "wape": False,
    "smape": False,
    "stockout_recall": True,
    "stockout_precision": True,
    "stockout_f1": True,
    "forecast_bias": False,
}

# Standard Default Hyperparameter Grids for Tuning
DEFAULT_PARAM_GRIDS: Dict[str, Dict[str, List[Any]]] = {
    "random_forest": {
        "n_estimators": [50, 100, 150],
        "max_depth": [5, 10, 15, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2"],
    },
    "xgboost": {
        "n_estimators": [50, 100, 150],
        "max_depth": [3, 5, 8],
        "learning_rate": [0.01, 0.05, 0.1, 0.2],
        "subsample": [0.7, 0.8, 1.0],
        "colsample_bytree": [0.7, 0.8, 1.0],
        "min_child_weight": [1, 3, 5],
        "reg_alpha": [0.0, 0.1, 1.0],
        "reg_lambda": [1.0, 5.0, 10.0],
    },
    "lightgbm": {
        "n_estimators": [50, 100, 150],
        "num_leaves": [15, 31, 63],
        "max_depth": [3, 6, 10, -1],
        "learning_rate": [0.01, 0.05, 0.1, 0.2],
        "feature_fraction": [0.7, 0.8, 1.0],
        "bagging_fraction": [0.7, 0.8, 1.0],
        "lambda_l1": [0.0, 0.1, 1.0],
        "lambda_l2": [0.0, 1.0, 5.0],
        "min_child_samples": [10, 20, 30],
    },
}
