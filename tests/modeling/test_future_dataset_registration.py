"""
Tests for registering a future dataset and future task dynamically.
Verifies that new datasets and tasks can be integrated via registry
without modifying any core pipeline code.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from modeling.config import TaskType, ValidationStrategy
from modeling.registry.dataset_registry import DatasetMetadata, DatasetRegistry
from modeling.registry.task_registry import TaskConfig, TaskRegistry
from modeling.data_loader import load_modeling_dataset
from modeling.target_builder import prepare_task_dataset
from modeling.feature_validation import validate_modeling_features
from modeling.pipeline import run_task_pipeline


def test_dynamic_future_dataset_and_task_registration(tmp_path):
    # 1. Create a synthetic future dataset: 'supplier_lead_time_features'
    data_file = tmp_path / "supplier_lead_time_features.parquet"
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        "supplier_id": [f"SUP_{i % 5}" for i in range(n)],
        "quote_amount": np.random.uniform(100, 1000, n),
        "fill_rate": np.random.uniform(0.7, 1.0, n),
        "historical_reliability": np.random.uniform(0.5, 0.99, n),
        "actual_lead_days": np.random.uniform(1, 14, n),
    })
    df.to_parquet(data_file, index=False)

    # 2. Register future dataset dynamically
    dataset_registry = DatasetRegistry()
    ds_meta = DatasetMetadata(
        name="supplier_lead_time_features",
        file_path=data_file,
        file_format="parquet",
        entity_id_columns=["supplier_id"],
        description="Hypothetical future supplier fulfillment lead time dataset",
    )
    dataset_registry.register(ds_meta, overwrite=True)

    assert "supplier_lead_time_features" in dataset_registry.list_datasets()

    # 3. Register future task dynamically
    task_registry = TaskRegistry()
    task_cfg = TaskConfig(
        task_name="supplier_lead_time_prediction",
        dataset_name="supplier_lead_time_features",
        task_type=TaskType.REGRESSION,
        target_column="actual_lead_days",
        feature_columns=["quote_amount", "fill_rate", "historical_reliability"],
        categorical_columns=[],
        numerical_columns=["quote_amount", "fill_rate", "historical_reliability"],
        validation_strategy=ValidationStrategy.KFOLD,
        n_splits=3,
        primary_metric="mae",
        candidate_models=["dummy", "linear_regression"],
    )
    task_registry.register(task_cfg, overwrite=True)

    assert "supplier_lead_time_prediction" in task_registry.list_tasks()

    # 4. Verify data loader works seamlessly
    loaded_df = load_modeling_dataset("supplier_lead_time_features", dataset_registry)
    assert len(loaded_df) == n

    # 5. Verify target builder and validation
    X, y, _ = prepare_task_dataset(task_cfg, df_raw=loaded_df)
    assert X.shape == (n, 3)
    assert len(y) == n

    validation_result = validate_modeling_features(X)
    assert validation_result["is_valid"] is True

    # 6. Run pipeline on the new task using run_task_pipeline
    summary = run_task_pipeline(
        task_name="supplier_lead_time_prediction",
        n_iter_tuning=2,
    )

    assert summary["task_name"] == "supplier_lead_time_prediction"
    assert summary["champion_model"] is not None

    # Cleanup registry
    dataset_registry.unregister("supplier_lead_time_features")
    task_registry.unregister("supplier_lead_time_prediction")
