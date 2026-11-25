"""
TBO InventoryIQ - Task Registry (Phase 4)
Defines task configurations and centralized registration interface for
extensible supervised learning and forecasting tasks.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

from modeling.config import (
    TaskType,
    ValidationStrategy,
    SUPPORTED_MODELS,
    DEFAULT_PRIMARY_METRICS,
    METRIC_DIRECTION_IS_HIGHER_BETTER,
)
from modeling.registry.dataset_registry import DatasetRegistry

logger = logging.getLogger(__name__)


@dataclass
class TaskConfig:
    """Configuration defining an end-to-end ML prediction task."""
    task_name: str
    dataset_name: str
    task_type: TaskType
    target_column: str
    feature_columns: Optional[List[str]] = None
    excluded_columns: List[str] = field(default_factory=list)
    categorical_columns: Optional[List[str]] = None
    numerical_columns: Optional[List[str]] = None
    prediction_timestamp: Optional[str] = None
    group_columns: Optional[List[str]] = None
    validation_strategy: ValidationStrategy = ValidationStrategy.KFOLD
    n_splits: int = 5
    forecast_horizon: Optional[int] = None
    primary_metric: Optional[str] = None
    secondary_metrics: List[str] = field(default_factory=list)
    candidate_models: List[str] = field(default_factory=list)
    business_params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        # Convert string to enums if strings were passed
        if isinstance(self.task_type, str):
            self.task_type = TaskType(self.task_type)
        if isinstance(self.validation_strategy, str):
            self.validation_strategy = ValidationStrategy(self.validation_strategy)

        if self.primary_metric is None:
            self.primary_metric = DEFAULT_PRIMARY_METRICS.get(self.task_type, "mae")

        if not self.candidate_models:
            self.candidate_models = list(SUPPORTED_MODELS.get(self.task_type, []))

        self.validate()

    def validate(self) -> None:
        """Validates internal consistency and compatibility."""
        if not self.task_name or not self.dataset_name:
            raise ValueError("Both task_name and dataset_name are mandatory.")

        if not self.target_column:
            raise ValueError(f"Task '{self.task_name}' must specify a target_column.")

        # Check feature exclusions
        if self.feature_columns and self.target_column in self.feature_columns:
            raise ValueError(
                f"Target column '{self.target_column}' cannot be included in feature_columns for task '{self.task_name}'."
            )

        # Validate candidate models against task type
        supported = SUPPORTED_MODELS.get(self.task_type, [])
        for model in self.candidate_models:
            if model not in supported:
                raise ValueError(
                    f"Model '{model}' is not supported for task type '{self.task_type}'. "
                    f"Supported models: {supported}"
                )

        # Check primary metric exists in direction map
        if self.primary_metric not in METRIC_DIRECTION_IS_HIGHER_BETTER:
            raise ValueError(
                f"Unknown primary_metric '{self.primary_metric}'. "
                f"Supported metrics: {list(METRIC_DIRECTION_IS_HIGHER_BETTER.keys())}"
            )

        # Validate time series specifics
        if self.validation_strategy == ValidationStrategy.TIME_SERIES_SPLIT:
            if self.task_type not in [TaskType.TIME_SERIES_REGRESSION, TaskType.REGRESSION]:
                logger.warning(
                    f"TimeSeriesSplit specified for non-time-series task type '{self.task_type}'."
                )


class TaskRegistry:
    """
    Centralized registry for managing prediction tasks.
    Enforces architectural extensibility: new tasks can be registered and
    executed without touching shared modeling pipelines.
    """
    _instance: Optional["TaskRegistry"] = None

    def __new__(cls) -> "TaskRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry: Dict[str, TaskConfig] = {}
            cls._instance._initialize_default_tasks()
        return cls._instance

    def _initialize_default_tasks(self) -> None:
        """Pre-registers the 4 eligible Phase 4 modeling tasks."""
        # 1. Hotel Cancellation Prediction
        self._registry["hotel_cancellation"] = TaskConfig(
            task_name="hotel_cancellation",
            dataset_name="hotel_cancellation_features",
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="is_canceled",
            excluded_columns=[
                "reservation_status",
                "reservation_status_date",
                "assigned_room_type",
                "room_type_changed",
                "market_segment_historical_cancel_rate",
                "deposit_type_historical_cancel_rate",
                "booking_changes",
                "arrival_date",
                "booking_date",
                "currency",
            ],
            validation_strategy=ValidationStrategy.STRATIFIED_KFOLD,
            n_splits=5,
            primary_metric="f1_score",
            secondary_metrics=["roc_auc", "pr_auc", "precision", "recall", "log_loss", "accuracy"],
            candidate_models=["dummy", "logistic_regression", "random_forest", "xgboost", "lightgbm"],
            business_params={"threshold": 0.50, "cost_fn": 3.0, "cost_fp": 1.0},
            description="Predicts hotel booking cancellation risk at reservation time.",
        )

        # 2. Flight Price Prediction
        self._registry["flight_price"] = TaskConfig(
            task_name="flight_price",
            dataset_name="flight_price_features",
            task_type=TaskType.REGRESSION,
            target_column="price",
            excluded_columns=[
                "price_log",
                "price_record_id",
                "currency",
            ],
            validation_strategy=ValidationStrategy.KFOLD,
            n_splits=5,
            primary_metric="mae",
            secondary_metrics=["rmse", "r2", "mape"],
            candidate_models=["dummy", "linear_regression", "random_forest", "xgboost", "lightgbm"],
            business_params={"horizon_evaluation": True},
            description="Predicts flight quote prices across booking horizons.",
        )

        # 3. Customer Demand Forecasting
        self._registry["demand_forecasting"] = TaskConfig(
            task_name="demand_forecasting",
            dataset_name="customer_demand_features",
            task_type=TaskType.TIME_SERIES_REGRESSION,
            target_column="future_search_volume_7d",
            excluded_columns=[
                "clicked",
                "booking_completed",
                "has_funnel_anomaly",
                "currency",
            ],
            group_columns=["destination_id", "inventory_type"],
            validation_strategy=ValidationStrategy.TIME_SERIES_SPLIT,
            n_splits=5,
            forecast_horizon=7,
            primary_metric="mae",
            secondary_metrics=["rmse", "wape", "smape"],
            candidate_models=["naive", "seasonal_naive", "linear_regression", "random_forest", "xgboost", "lightgbm"],
            business_params={"horizon_days": 7, "seasonal_period": 7},
            description="Forecasts destination search demand volume 7 days ahead.",
        )

        # 4. Inventory Availability & Stockout Forecasting
        self._registry["inventory_forecasting"] = TaskConfig(
            task_name="inventory_forecasting",
            dataset_name="inventory_features",
            task_type=TaskType.TIME_SERIES_REGRESSION,
            target_column="future_available_quantity",
            excluded_columns=[
                "snapshot_id",
                "inventory_sold_out_indicator",
            ],
            group_columns=["inventory_id", "travel_date"],
            validation_strategy=ValidationStrategy.TIME_SERIES_SPLIT,
            n_splits=5,
            forecast_horizon=1,
            primary_metric="mae",
            secondary_metrics=["rmse", "wape", "stockout_recall"],
            candidate_models=["naive", "linear_regression", "random_forest", "xgboost", "lightgbm"],
            business_params={"stockout_threshold": 5.0},
            description="Forecasts future available inventory and detects impending stockouts.",
        )

    def register(self, config: TaskConfig, overwrite: bool = False) -> None:
        """Registers a new task configuration."""
        if config.task_name in self._registry and not overwrite:
            raise ValueError(
                f"Task '{config.task_name}' is already registered. Set overwrite=True to update."
            )
        # Ensure referenced dataset exists
        dataset_reg = DatasetRegistry()
        if not dataset_reg.exists(config.dataset_name):
            raise KeyError(
                f"Cannot register task '{config.task_name}': referenced dataset '{config.dataset_name}' is not registered."
            )

        self._registry[config.task_name] = config
        logger.info(f"Registered task: '{config.task_name}' (type: {config.task_type.value})")

    def get(self, name: str) -> TaskConfig:
        """Retrieves a registered task configuration."""
        if name not in self._registry:
            raise KeyError(
                f"Task '{name}' is not registered. Available: {list(self._registry.keys())}"
            )
        return self._registry[name]

    def exists(self, name: str) -> bool:
        """Checks if a task is registered."""
        return name in self._registry

    def unregister(self, name: str) -> bool:
        """Unregisters a task."""
        if name in self._registry:
            del self._registry[name]
            logger.info(f"Unregistered task: '{name}'")
            return True
        return False

    def list_tasks(self) -> List[str]:
        """Lists all registered task names."""
        return list(self._registry.keys())

    def reset(self) -> None:
        """Resets the task registry to defaults."""
        self._registry.clear()
        self._initialize_default_tasks()
