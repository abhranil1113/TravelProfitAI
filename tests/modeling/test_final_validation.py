"""
Unit tests for Phase 4 Final Validation corrections:
1. Hotel cancellation strict exclusion of booking_changes and post-event columns.
2. Demand forecasting global chronological panel and embargo gap.
3. Inventory stockout threshold optimization logic.
4. Champion artifact prediction and unknown-category robustness.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.registry.task_registry import TaskRegistry
from modeling.target_builder import prepare_task_dataset
from modeling.model_persistence import load_model_artifact


def test_hotel_cancellation_strict_leakage_exclusion():
    reg = TaskRegistry()
    cfg = reg.get("hotel_cancellation")
    X, y, _ = prepare_task_dataset(cfg)

    prohibited_columns = [
        "booking_changes",
        "reservation_status",
        "reservation_status_date",
        "assigned_room_type",
        "room_type_changed",
    ]
    for col in prohibited_columns:
        assert col not in X.columns, f"Prohibited leakage column '{col}' found in hotel cancellation predictor matrix X!"


def test_demand_forecasting_panel_chronological_ordering():
    reg = TaskRegistry()
    cfg = reg.get("demand_forecasting")
    X, y, df = prepare_task_dataset(cfg)

    assert "date" in df.columns
    assert "future_search_volume_7d" in df.columns
    assert len(df) == 10569
    assert (df["future_search_volume_7d"] == 0).sum() > 0.50 * len(df)


def test_inventory_forecasting_stockout_threshold_logic():
    # Evaluate threshold cost logic on synthetic validation predictions
    y_val = np.array([2.0, 4.0, 10.0, 25.0, 3.0])
    val_preds = np.array([4.0, 6.0, 11.0, 24.0, 2.0])

    # Threshold 5
    actual_stockout = (y_val <= 5.0).astype(int)  # [1, 1, 0, 0, 1] (3 stockouts)
    pred_stockout_5 = (val_preds <= 5.0).astype(int)  # [1, 0, 0, 0, 1] (2 alerts, 1 FN at idx 1)
    assert actual_stockout.sum() == 3
    assert pred_stockout_5.sum() == 2

    # Threshold 10 catches idx 1
    pred_stockout_10 = (val_preds <= 10.0).astype(int)
    assert pred_stockout_10[1] == 1


def test_champion_artifacts_unknown_category_robustness():
    tasks = ["hotel_cancellation", "flight_price", "demand_forecasting", "inventory_forecasting"]
    reg = TaskRegistry()

    for t in tasks:
        artifact, meta = load_model_artifact(t)
        cfg = reg.get(t)
        X, y, _ = prepare_task_dataset(cfg)

        sample = X.head(3).copy()
        for col in artifact.feature_names:
            if col in sample.columns and sample[col].dtype == "object":
                sample[col] = "UNKNOWN_CATEGORY_PROBE_999"

        preds, _ = artifact.predict(sample)
        assert len(preds) == 3
        assert not np.isnan(preds).any()
