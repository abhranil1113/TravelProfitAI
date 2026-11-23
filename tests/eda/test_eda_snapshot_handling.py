"""
Tests for Snapshot Analysis Module
Verifies multi-snapshot detection, latest snapshot deduplication, and trajectory tracking.
"""

import pytest
import pandas as pd
from eda.snapshot_analysis import (
    validate_snapshot_cardinality,
    get_latest_inventory_snapshots,
    safe_aggregate_capacity,
    analyze_inventory_depletion_trajectories,
)


def test_validate_snapshot_cardinality():
    """Verify detection of multi-snapshot records."""
    df = pd.DataFrame({
        "inventory_id": ["inv1", "inv1", "inv1", "inv2"],
        "travel_date": ["2026-06-01", "2026-06-01", "2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-10", "2026-05-20", "2026-05-20"],
    })
    card = validate_snapshot_cardinality(df)
    assert card["is_multi_snapshot_dataset"] is True
    assert card["max_snapshots_per_item"] == 3
    assert card["distinct_inventory_ids"] == 2


def test_get_latest_inventory_snapshots():
    """Verify that latest snapshot per (inventory_id, travel_date) is returned."""
    df = pd.DataFrame({
        "inventory_id": ["inv1", "inv1", "inv2"],
        "travel_date": ["2026-06-01", "2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-15", "2026-05-10"],
        "available_quantity": [90, 45, 10],
    })
    latest = get_latest_inventory_snapshots(df)
    assert len(latest) == 2
    inv1_row = latest[latest["inventory_id"] == "inv1"].iloc[0]
    assert inv1_row["snapshot_date"] == "2026-05-15"
    assert inv1_row["available_quantity"] == 45


def test_safe_aggregate_capacity():
    """Verify safe capacity aggregation prevents Cartesian overcounting."""
    df = pd.DataFrame({
        "inventory_id": ["inv1", "inv1"],
        "travel_date": ["2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-15"],
        "total_capacity": [100, 100],
        "booked_quantity": [20, 50],
        "available_quantity": [80, 50],
    })
    # When force_deduplicate=True, total_capacity should be 100, not 200
    res = safe_aggregate_capacity(df, force_deduplicate=True)
    assert res["total_capacity"] == 100.0
    assert res["total_booked_quantity"] == 50.0

    # When raise_on_multi_snapshot=True and force_deduplicate=False, should raise ValueError
    with pytest.raises(ValueError, match="Attempted to aggregate capacity over multiple temporal snapshots"):
        safe_aggregate_capacity(df, force_deduplicate=False, raise_on_multi_snapshot=True)


def test_analyze_inventory_depletion_trajectories():
    """Verify tracking of depletion velocity over sequential snapshots."""
    df = pd.DataFrame({
        "inventory_id": ["inv1", "inv1"],
        "travel_date": ["2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-05"],  # 4 days
        "available_quantity": [100, 60],  # 40 units depleted in 4 days -> 10 units/day
    })
    traj = analyze_inventory_depletion_trajectories(df)
    assert len(traj) == 1
    assert traj.iloc[0]["depletion_velocity_units_per_day"] == 10.0
