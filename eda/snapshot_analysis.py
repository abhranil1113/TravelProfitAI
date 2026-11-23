"""
TBO InventoryIQ - Inventory Snapshot & Cardinality Engine (Phase 2)
Provides snapshot-aware filtering, trajectory tracking, and prevents
erroneous multi-snapshot capacity aggregations.
"""

from typing import Dict, Any, Optional
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def validate_snapshot_cardinality(inventory_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Examines snapshot counts per inventory item and travel date.
    Detects repeated point-in-time observations to avoid Cartesian inflation.
    """
    total_rows = len(inventory_df)
    if total_rows == 0:
        return {"total_rows": 0, "status": "empty"}

    group_keys = ["inventory_id", "travel_date"]
    counts_per_item = inventory_df.groupby(group_keys).size()

    max_snapshots = int(counts_per_item.max())
    min_snapshots = int(counts_per_item.min())
    avg_snapshots = float(counts_per_item.mean())
    multi_snapshot_items = int((counts_per_item > 1).sum())

    distinct_inventory_items = int(inventory_df["inventory_id"].nunique())
    distinct_item_dates = len(counts_per_item)

    is_multi_snapshot = max_snapshots > 1

    return {
        "total_rows": total_rows,
        "distinct_inventory_ids": distinct_inventory_items,
        "distinct_inventory_travel_dates": distinct_item_dates,
        "max_snapshots_per_item": max_snapshots,
        "min_snapshots_per_item": min_snapshots,
        "avg_snapshots_per_item": round(avg_snapshots, 2),
        "multi_snapshot_item_count": multi_snapshot_items,
        "is_multi_snapshot_dataset": is_multi_snapshot,
        "cardinality_guideline": (
            "WARNING: Dataset contains multiple temporal snapshots. "
            "Never sum capacity or available units across all rows directly. "
            "Filter to latest snapshot or group by snapshot_date."
            if is_multi_snapshot
            else "Dataset has single snapshot per inventory item."
        ),
    }


def get_latest_inventory_snapshots(inventory_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts the single most recent temporal snapshot for each (inventory_id, travel_date).
    Guarantees physical capacity is counted exactly once.
    """
    if "snapshot_date" not in inventory_df.columns:
        return inventory_df.copy()

    sorted_df = inventory_df.sort_values(by=["inventory_id", "travel_date", "snapshot_date"])
    latest_df = sorted_df.groupby(["inventory_id", "travel_date"], as_index=False).last()
    return latest_df.reset_index(drop=True)


def safe_aggregate_capacity(
    inventory_df: pd.DataFrame,
    force_deduplicate: bool = True,
    raise_on_multi_snapshot: bool = False,
) -> Dict[str, float]:
    """
    Safely computes capacity and availability metrics, enforcing snapshot deduplication.
    """
    cardinality_info = validate_snapshot_cardinality(inventory_df)

    if cardinality_info.get("is_multi_snapshot_dataset", False):
        if raise_on_multi_snapshot and not force_deduplicate:
            raise ValueError(
                "Attempted to aggregate capacity over multiple temporal snapshots. "
                "Set force_deduplicate=True to safely isolate the latest snapshot."
            )
        if not force_deduplicate:
            logger.warning(
                "Aggregating multi-snapshot inventory without deduplication. "
                "Capacity figures are likely overstated!"
            )
            target_df = inventory_df
        else:
            target_df = get_latest_inventory_snapshots(inventory_df)
    else:
        target_df = inventory_df

    total_cap = float(target_df["total_capacity"].sum())
    total_booked = float(target_df["booked_quantity"].sum())
    total_avail = float(target_df["available_quantity"].sum())

    return {
        "aggregated_rows": len(target_df),
        "total_capacity": total_cap,
        "total_booked_quantity": total_booked,
        "total_available_quantity": total_avail,
        "utilization_rate_pct": round((total_booked / total_cap * 100), 2) if total_cap > 0 else 0.0,
    }


def analyze_inventory_depletion_trajectories(inventory_df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyzes how inventory availability changes across snapshot observation dates.
    Tracks depletion velocity (units booked / day) between consecutive snapshots.
    """
    if "snapshot_date" not in inventory_df.columns:
        return pd.DataFrame()

    df = inventory_df.copy()
    df["snapshot_dt"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
    df = df.sort_values(by=["inventory_id", "travel_date", "snapshot_dt"])

    # Group by inventory item and compute lag changes
    df["prev_available"] = df.groupby(["inventory_id", "travel_date"])["available_quantity"].shift(1)
    df["prev_snapshot_dt"] = df.groupby(["inventory_id", "travel_date"])["snapshot_dt"].shift(1)

    df["available_delta"] = df["available_quantity"] - df["prev_available"]
    df["days_between_snapshots"] = (df["snapshot_dt"] - df["prev_snapshot_dt"]).dt.total_seconds() / (24 * 3600)

    # Depletion velocity (negative delta indicates sales/bookings)
    df["depletion_velocity_units_per_day"] = np.where(
        (df["days_between_snapshots"] > 0) & (df["available_delta"] < 0),
        -df["available_delta"] / df["days_between_snapshots"],
        0.0,
    )

    trajectory_summary = df.dropna(subset=["prev_available"]).copy()
    return trajectory_summary
