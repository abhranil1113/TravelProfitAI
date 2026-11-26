"""
optimization/data/point_in_time.py

Point-in-time snapshot resolution and historical cutoff service.
Prevents temporal leakage, duplicate snapshot aggregation, and expired offer selection.
"""

from typing import Tuple, Dict, Any
import pandas as pd
from optimization.exceptions import PointInTimeViolationError, ExpiredOfferError


class PointInTimeResolver:
    """Enforces strict temporal integrity at optimization timestamp T_opt."""

    def __init__(self, optimization_timestamp: str):
        self.raw_timestamp = str(optimization_timestamp)
        self.optimization_timestamp = str(optimization_timestamp).split("T")[0]

    def filter_active_supplier_offers(self, offers_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Filters out expired offers where offer_valid_until < optimization_timestamp.
        
        Returns:
            Tuple of (active_offers_df, audit_metadata)
        """
        df = offers_df.copy()
        df["offer_valid_until_date"] = pd.to_datetime(df["offer_valid_until"]).dt.strftime("%Y-%m-%d")
        
        total_offers = len(df)
        active_mask = df["offer_valid_until_date"] >= self.optimization_timestamp
        active_df = df[active_mask].drop(columns=["offer_valid_until_date"]).reset_index(drop=True)
        expired_count = total_offers - len(active_df)

        audit_meta = {
            "total_offers_ingested": total_offers,
            "active_offers_retained": len(active_df),
            "expired_offers_dropped": expired_count,
            "optimization_timestamp": self.optimization_timestamp,
        }
        return active_df, audit_meta

    def resolve_inventory_snapshots(self, inventory_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Resolves point-in-time physical capacity by selecting the latest snapshot
        where snapshot_date <= optimization_timestamp for each (inventory_id, travel_date).
        
        Never sums repeated snapshots as independent inventory.
        
        Returns:
            Tuple of (resolved_inventory_df, audit_metadata)
        """
        df = inventory_df.copy()
        df["snapshot_date_str"] = pd.to_datetime(df["snapshot_date"]).dt.strftime("%Y-%m-%d")
        
        # Keep only snapshots observed on or before T_opt
        valid_snapshots = df[df["snapshot_date_str"] <= self.optimization_timestamp].copy()
        
        if valid_snapshots.empty:
            audit_meta = {
                "total_snapshots": len(df),
                "resolved_items_count": 0,
                "warning": "No inventory snapshots observed prior to optimization timestamp.",
                "optimization_timestamp": self.optimization_timestamp,
            }
            return pd.DataFrame(), audit_meta

        # Sort by snapshot_date ascending, then pick the exact latest physical snapshot row per (inventory_id, travel_date).
        # Note: drop_duplicates(keep='last') preserves atomic physical rows, preventing groupby().last() column-blending.
        valid_snapshots.sort_values(by=["inventory_id", "travel_date", "snapshot_date_str"], ascending=True, inplace=True)
        latest_snapshots = valid_snapshots.drop_duplicates(
            subset=["inventory_id", "travel_date"],
            keep="last"
        ).reset_index(drop=True)

        audit_meta = {
            "total_raw_snapshots": len(df),
            "snapshots_prior_to_opt_date": len(valid_snapshots),
            "unique_resolved_inventory_items": len(latest_snapshots),
            "optimization_timestamp": self.optimization_timestamp,
        }
        return latest_snapshots, audit_meta

    def filter_prior_search_events(self, searches_df: pd.DataFrame) -> pd.DataFrame:
        """Filters customer search events to strictly include records before T_opt."""
        df = searches_df.copy()
        df["search_date_str"] = pd.to_datetime(df["search_date"]).dt.strftime("%Y-%m-%d")
        prior_searches = df[df["search_date_str"] < self.optimization_timestamp].copy()
        return prior_searches.drop(columns=["search_date_str"]).reset_index(drop=True)
