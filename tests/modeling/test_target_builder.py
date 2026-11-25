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
    assert "forecast_origin_snapshot_date" in stream_df.columns
    assert "future_snapshot_date" in stream_df.columns
    assert len(stream_df) > 0


def test_demand_panel_zero_future_lookahead_no_bfill():
    """Verifies that avg_search_price does NOT backfill from future observations."""
    records = [
        {"search_id": "s1", "search_date": "2026-01-01", "destination_id": 1, "inventory_type": "FLIGHT", "search_price_inr": np.nan},
        {"search_id": "s2", "search_date": "2026-01-02", "destination_id": 1, "inventory_type": "FLIGHT", "search_price_inr": np.nan},
        {"search_id": "s3", "search_date": "2026-01-03", "destination_id": 1, "inventory_type": "FLIGHT", "search_price_inr": 5000.0},
        {"search_id": "s4", "search_date": "2026-01-04", "destination_id": 1, "inventory_type": "FLIGHT", "search_price_inr": 6000.0},
    ]
    df = pd.DataFrame(records)
    panel = build_demand_forecasting_panel(df, horizon_days=1)
    # The first two dates should be 0.0 (past-only fill), NOT 5000.0 (bfill from future)
    first_price = panel.loc[panel["date"] == "2026-01-01", "avg_search_price"].iloc[0]
    assert first_price == 0.0, f"Expected 0.0 without future lookahead, got {first_price}"


def test_inventory_stream_deterministic_sorting():
    """Verifies deterministic sorting with snapshot_id secondary tie-breaker."""
    records = [
        {"snapshot_id": "b_2", "snapshot_date": "2026-01-01", "inventory_id": 1, "travel_date": "2026-02-01", "available_quantity": 10, "booked_quantity": 2},
        {"snapshot_id": "a_1", "snapshot_date": "2026-01-01", "inventory_id": 1, "travel_date": "2026-02-01", "available_quantity": 12, "booked_quantity": 1},
        {"snapshot_id": "c_3", "snapshot_date": "2026-01-02", "inventory_id": 1, "travel_date": "2026-02-01", "available_quantity": 8, "booked_quantity": 4},
    ]
    df = pd.DataFrame(records)
    stream = build_inventory_forecasting_stream(df, horizon_snapshots=1)
    # First snapshot should be a_1 because 'snapshot_id' is used as tie-breaker
    assert stream.iloc[0]["snapshot_id"] == "a_1"
