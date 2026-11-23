"""
Tests for Target Builder and Time-Series Panel Aggregation.
Verifies prepare_task_dataset, build_demand_forecasting_panel, and build_inventory_forecasting_stream.
"""

import pytest
import pandas as pd
import numpy as np
from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.target_builder import (
    prepare_task_dataset,
    build_demand_forecasting_panel,
    build_inventory_forecasting_stream,
)


def test_standard_prepare_task_dataset():
    df = pd.DataFrame({
        "lead_time": [10, 20, 30, 40],
        "is_canceled": [0, 1, 0, 1],
    })
    cfg = TaskConfig(
        task_name="test_clf",
        dataset_name="test_ds",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="is_canceled",
        feature_columns=["lead_time"],
        numerical_columns=["lead_time"],
    )
    X, y, _ = prepare_task_dataset(cfg, df_raw=df)
    assert list(X.columns) == ["lead_time"]
    assert list(y) == [0, 1, 0, 1]


def test_build_demand_forecasting_panel():
    dates = pd.date_range("2026-01-01", periods=15, freq="D")
    records = []
    for d in dates:
        for dest in [1, 2]:
            records.append({
                "search_id": f"s_{d}_{dest}",
                "search_date": d,
                "destination_id": dest,
                "inventory_type": "FLIGHT",
                "travellers_count": 2,
                "search_price_inr": 4500.0,
            })
    df_searches = pd.DataFrame(records)

    panel_df = build_demand_forecasting_panel(df_searches, horizon_days=3)
    assert "future_search_volume_3d" in panel_df.columns
    assert "lag_1" in panel_df.columns
    assert "rolling_mean_7" in panel_df.columns
    assert len(panel_df) > 0


def test_build_inventory_forecasting_stream():
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    records = []
    for d in dates:
        records.append({
            "snapshot_id": f"snap_{d}",
            "snapshot_date": d,
            "inventory_id": 101,
            "travel_date": "2026-02-01",
            "inventory_type": "HOTEL",
            "available_quantity": 25,
            "booked_quantity": 5,
            "capacity": 30,
            "stockout_flag": 0,
        })
    df_inv = pd.DataFrame(records)

    stream_df = build_inventory_forecasting_stream(df_inv, horizon_snapshots=1)
    assert "future_available_quantity" in stream_df.columns
    assert "actual_stockout" in stream_df.columns
    assert len(stream_df) > 0
