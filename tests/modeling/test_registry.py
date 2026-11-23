"""
Tests for Extensible Registry System (DatasetRegistry & TaskRegistry)
"""

import pytest
from pathlib import Path
from modeling.config import TaskType, ValidationStrategy
from modeling.registry.dataset_registry import DatasetMetadata, DatasetRegistry
from modeling.registry.task_registry import TaskConfig, TaskRegistry


def test_dataset_registry_defaults():
    registry = DatasetRegistry()
    registry.reset()
    datasets = registry.list_datasets()
    assert "hotel_cancellation_features" in datasets
    assert "flight_price_features" in datasets
    assert "customer_demand_features" in datasets
    assert "inventory_features" in datasets

    meta = registry.get("hotel_cancellation_features")
    assert meta.name == "hotel_cancellation_features"
    assert meta.file_format == "parquet"


def test_dataset_registry_duplicate_rejection(tmp_path):
    dummy_file = tmp_path / "dummy.parquet"
    dummy_file.touch()

    registry = DatasetRegistry()
    meta = DatasetMetadata(name="test_dummy", file_path=dummy_file)
    registry.register(meta, overwrite=True)

    # Attempting to register again without overwrite=True must raise ValueError
    with pytest.raises(ValueError, match="already registered"):
        registry.register(meta, overwrite=False)

    registry.unregister("test_dummy")


def test_dataset_registry_missing_file():
    registry = DatasetRegistry()
    meta = DatasetMetadata(name="missing_ds", file_path=Path("non_existent_file.parquet"))
    with pytest.raises(FileNotFoundError):
        registry.register(meta)


def test_task_registry_defaults():
    registry = TaskRegistry()
    registry.reset()
    tasks = registry.list_tasks()
    assert "hotel_cancellation" in tasks
    assert "flight_price" in tasks
    assert "demand_forecasting" in tasks
    assert "inventory_forecasting" in tasks

    cfg = registry.get("hotel_cancellation")
    assert cfg.task_type == TaskType.BINARY_CLASSIFICATION
    assert cfg.target_column == "is_canceled"


def test_task_registry_target_in_predictors_rejection():
    # Target column must not be inside feature_columns
    with pytest.raises(ValueError, match="cannot be included in feature_columns"):
        TaskConfig(
            task_name="invalid_task",
            dataset_name="hotel_cancellation_features",
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="is_canceled",
            feature_columns=["lead_time_days", "is_canceled"],
        )


def test_task_registry_incompatible_model_rejection():
    # LinearRegression is not a classification model
    with pytest.raises(ValueError, match="is not supported for task type"):
        TaskConfig(
            task_name="incompatible_task",
            dataset_name="hotel_cancellation_features",
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="is_canceled",
            candidate_models=["linear_regression"],
        )


def test_task_registry_invalid_metric_rejection():
    with pytest.raises(ValueError, match="Unknown primary_metric"):
        TaskConfig(
            task_name="invalid_metric_task",
            dataset_name="hotel_cancellation_features",
            task_type=TaskType.BINARY_CLASSIFICATION,
            target_column="is_canceled",
            primary_metric="fake_metric_not_exist",
        )
