"""
TBO InventoryIQ - Inventory Utilization & Depletion Feature Engineering (Phase 3)
Builds occupancy, utilization, snapshot-aware depletion velocity, and stockout risk features.
Preserves strict segregation between ROOM_NIGHT and SEAT units.
"""

import pandas as pd
import numpy as np

from feature_engineering.base_transformer import (
    BaseFeatureTransformer,
    safe_divide,
    safe_log1p,
    safe_date_diff_days,
    bin_series,
)
from feature_engineering.config import BIN_CONFIGS


class InventoryFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms multi-snapshot inventory availability records into utilization and depletion features.
    """
    def __init__(self):
        super().__init__(name="inventory_features")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # 1. Identifiers & Entity Attributes
        out["snapshot_id"] = df["snapshot_id"].astype(str)
        out["inventory_id"] = df["inventory_id"].astype(str)
        out["inventory_type"] = df["inventory_type"].astype(str)
        out["supplier_id"] = df["supplier_id"].astype(str)
        out["origin_id"] = df["origin_id"].astype(str)
        out["destination_id"] = df["destination_id"].astype(str)
        out["unit_type"] = df["unit_type"].astype(str)  # ROOM_NIGHT vs SEAT

        # 2. Temporal Reference
        out["travel_date"] = df["travel_date"].astype(str)
        out["snapshot_date"] = df["snapshot_date"].astype(str)
        days_to_travel = safe_date_diff_days(df["travel_date"], df["snapshot_date"]).fillna(0)
        out["days_to_travel"] = days_to_travel.clip(lower=0).astype(int)

        # 3. Capacity, Occupancy, & Utilization Rates
        cap = df["total_capacity"].clip(lower=1).astype(float)
        booked = df["booked_quantity"].clip(lower=0).astype(float)
        avail = df["available_quantity"].clip(lower=0).astype(float)

        out["total_capacity"] = cap.astype(int)
        out["booked_quantity"] = booked.astype(int)
        out["available_quantity"] = avail.astype(int)

        # Occupancy Rate (fraction of capacity booked)
        out["occupancy_rate"] = safe_divide(booked, cap, default=0.0).clip(0.0, 1.0).round(4)
        # Utilization Rate (synonymous with occupancy_rate under current business definition)
        out["inventory_utilization_rate"] = out["occupancy_rate"]
        # Availability Rate (fraction of capacity available)
        out["availability_rate"] = safe_divide(avail, cap, default=0.0).clip(0.0, 1.0).round(4)

        # 4. Availability Categories & Stockout Indicators
        out["availability_percentage"] = (out["availability_rate"] * 100).round(2)
        out["inventory_sold_out_indicator"] = (
            df["sold_out"].astype(bool) | (out["available_quantity"] == 0)
        )
        out["availability_bucket"] = bin_series(
            out["availability_percentage"],
            bins=BIN_CONFIGS["inventory_availability_pct"]["bins"],
            labels=BIN_CONFIGS["inventory_availability_pct"]["labels"],
        )

        # 5. Snapshot Sequential Tracking (Strictly Past-Only, No Lookahead)
        # Sort chronologically by item, travel_date, and snapshot_date
        work_df = df.copy()
        work_df["snapshot_dt"] = pd.to_datetime(work_df["snapshot_date"], errors="coerce")
        work_df = work_df.sort_values(by=["inventory_id", "travel_date", "snapshot_dt"])

        work_df["prev_booked"] = work_df.groupby(["inventory_id", "travel_date"])["booked_quantity"].shift(1)
        work_df["prev_avail"] = work_df.groupby(["inventory_id", "travel_date"])["available_quantity"].shift(1)
        work_df["prev_snapshot_dt"] = work_df.groupby(["inventory_id", "travel_date"])["snapshot_dt"].shift(1)

        delta_days = (work_df["snapshot_dt"] - work_df["prev_snapshot_dt"]).dt.total_seconds() / (24 * 3600)
        delta_booked = work_df["booked_quantity"] - work_df["prev_booked"]
        delta_avail = work_df["available_quantity"] - work_df["prev_avail"]

        # Align back to original index
        out["days_since_prev_snapshot"] = delta_days.reindex(df.index).fillna(0.0).clip(lower=0.0).round(1)
        out["change_in_booked_quantity"] = delta_booked.reindex(df.index).fillna(0.0).round(1)
        out["change_in_available_quantity"] = delta_avail.reindex(df.index).fillna(0.0).round(1)

        # Booking velocity (units booked per day between snapshots)
        out["booking_velocity_units_per_day"] = np.where(
            out["days_since_prev_snapshot"] > 0,
            safe_divide(out["change_in_booked_quantity"], out["days_since_prev_snapshot"]),
            0.0,
        ).round(2)

        # Depletion velocity (units depleted per day between snapshots)
        out["inventory_depletion_velocity"] = np.where(
            (out["days_since_prev_snapshot"] > 0) & (out["change_in_available_quantity"] < 0),
            safe_divide(-out["change_in_available_quantity"], out["days_since_prev_snapshot"]),
            0.0,
        ).round(2)

        # 6. Inventory Risk Indicators
        out["high_occupancy_indicator"] = out["occupancy_rate"] >= 0.80
        out["low_availability_indicator"] = out["availability_rate"] <= 0.20
        out["rapid_depletion_indicator"] = out["inventory_depletion_velocity"] >= 5.0

        return out
