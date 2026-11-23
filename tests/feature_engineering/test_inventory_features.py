"""
Tests for Inventory Utilization & Depletion Feature Engineering Module
"""

import pytest
import pandas as pd
from feature_engineering.inventory_features import InventoryFeatureTransformer


def test_inventory_feature_transformer():
    test_inv = pd.DataFrame({
        "snapshot_id": ["SN1", "SN2"],
        "inventory_id": ["INV_01", "INV_01"],
        "inventory_type": ["hotel", "hotel"],
        "supplier_id": ["SUP_1", "SUP_1"],
        "origin_id": ["DEL", "DEL"],
        "destination_id": ["GOA", "GOA"],
        "travel_date": ["2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-05"],  # 4 days difference
        "total_capacity": [100, 100],
        "booked_quantity": [20, 40],                     # +20 booked in 4 days -> 5 units/day
        "available_quantity": [80, 60],                  # -20 available in 4 days -> 5 units/day depletion
        "sold_out": [False, False],
        "unit_type": ["ROOM_NIGHT", "ROOM_NIGHT"],
    })

    transformer = InventoryFeatureTransformer()
    feats = transformer.transform(test_inv)

    assert len(feats) == 2
    assert "occupancy_rate" in feats.columns
    assert "inventory_utilization_rate" in feats.columns
    assert "booking_velocity_units_per_day" in feats.columns
    assert "inventory_depletion_velocity" in feats.columns

    # Row 0: 20 / 100 = 0.20 occupancy
    assert feats.loc[0, "occupancy_rate"] == 0.20
    assert feats.loc[0, "availability_rate"] == 0.80

    # Row 1: Snapshot sequence velocity
    assert feats.loc[1, "days_since_prev_snapshot"] == 4.0
    assert feats.loc[1, "booking_velocity_units_per_day"] == 5.0
    assert feats.loc[1, "inventory_depletion_velocity"] == 5.0
    assert feats.loc[1, "rapid_depletion_indicator"] == True
