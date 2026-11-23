"""
TBO InventoryIQ - Cross-Dataset Relationship & Currency Safety Engine (Phase 2)
Manages safe joins, checks join cardinalities, prevents Cartesian explosions,
enforces multi-currency safety, and aligns demand vs supply signals.
"""

from typing import Dict, Any, Optional, Tuple
import logging
import pandas as pd
import numpy as np

from eda.config import CURRENCY_MAP, CurrencyMismatchError
from eda.snapshot_analysis import get_latest_inventory_snapshots

logger = logging.getLogger(__name__)


def enforce_currency_safety(
    dataset1_name: str,
    dataset2_name: str,
    operation: str = "combine",
    exchange_rate: Optional[float] = None,
) -> None:
    """
    Validates financial operation compatibility between two datasets.
    Raises CurrencyMismatchError if unaligned currencies (e.g. EUR vs INR) are combined
    without an explicit, documented exchange rate.
    """
    curr1 = CURRENCY_MAP.get(dataset1_name, "UNKNOWN")
    curr2 = CURRENCY_MAP.get(dataset2_name, "UNKNOWN")

    if curr1 in ["OPERATIONAL", "METADATA", "INDEX"] or curr2 in ["OPERATIONAL", "METADATA", "INDEX"]:
        return

    if curr1 != curr2 and exchange_rate is None:
        raise CurrencyMismatchError(
            f"Illegal cross-currency operation '{operation}' between {dataset1_name} ({curr1}) "
            f"and {dataset2_name} ({curr2}) without an explicit exchange rate conversion."
        )


def validate_join_cardinality(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_on: str,
    right_on: str,
    how: str = "inner",
) -> Dict[str, Any]:
    """
    Analyzes join keys to detect and prevent Cartesian product explosion before merging.
    """
    left_len = len(left_df)
    right_len = len(right_df)

    left_keys = left_df[left_on].dropna()
    right_keys = right_df[right_on].dropna()

    right_key_counts = right_keys.value_counts()
    max_right_multiplicity = int(right_key_counts.max()) if not right_key_counts.empty else 0
    duplicate_right_keys = int((right_key_counts > 1).sum())

    is_explosion_risk = max_right_multiplicity > 1

    return {
        "left_rows": left_len,
        "right_rows": right_len,
        "left_key": left_on,
        "right_key": right_on,
        "right_max_multiplicity": max_right_multiplicity,
        "duplicate_right_keys_count": duplicate_right_keys,
        "cartesian_explosion_risk": is_explosion_risk,
        "recommendation": (
            f"DANGER: Key '{right_on}' has duplicate occurrences (up to {max_right_multiplicity}x). "
            f"Deduplicate right_df (e.g., latest snapshot) before joining to avoid row explosion."
            if is_explosion_risk
            else f"Safe: Key '{right_on}' is unique in right_df (1:1 or N:1 join)."
        ),
    }


def analyze_demand_vs_supply(
    searches_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    supplier_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Synthesizes customer search demand, available inventory capacity, and supplier offer volumes
    by destination. Strictly deduplicates inventory snapshots first.
    """
    # 1. Deduplicate inventory snapshots to point-in-time latest
    dedup_inventory = get_latest_inventory_snapshots(inventory_df)

    # 2. Demand aggregation by destination
    demand = searches_df.groupby("destination_id").agg(
        search_volume=("search_id", "count"),
        clicks=("clicked", "sum"),
        bookings=("booking_completed", "sum"),
        avg_searched_price_inr=("search_price", "mean"),
    ).reset_index()

    # 3. Supply availability aggregation by destination
    supply = dedup_inventory.groupby("destination_id").agg(
        inventory_items=("inventory_id", "count"),
        total_capacity=("total_capacity", "sum"),
        booked_units=("booked_quantity", "sum"),
        available_units=("available_quantity", "sum"),
    ).reset_index()

    # 4. Supplier offers aggregation by destination
    supplier_summary = supplier_df.groupby("destination_id").agg(
        supplier_offers_count=("offer_id", "count"),
        avg_purchase_cost_inr=("purchase_cost", "mean"),
        avg_supplier_selling_inr=("selling_price", "mean"),
        avg_margin_pct=("margin_percentage" if "margin_percentage" in supplier_df.columns else "purchase_cost", "mean"),
    ).reset_index()

    # 5. Merge all three domains
    merged = demand.merge(supply, on="destination_id", how="outer").fillna(0)
    merged = merged.merge(supplier_summary, on="destination_id", how="outer").fillna(0)

    # Compute key ratios
    # Demand-to-Available Ratio (searches / (available_units + 1))
    merged["demand_to_supply_ratio"] = merged.apply(
        lambda r: round(r["search_volume"] / (r["available_units"] + 1), 2), axis=1
    )
    # Market Opportunity Category
    def classify_market(row):
        if row["demand_to_supply_ratio"] > 1.5 and row["available_units"] < 50:
            return "High Demand - Supply Constrained (Procure More)"
        elif row["demand_to_supply_ratio"] < 0.5 and row["available_units"] > 100:
            return "Low Demand - Over-Supplied (Hold/Discount)"
        else:
            return "Balanced Market"

    merged["procurement_priority"] = merged.apply(classify_market, axis=1)

    return merged.sort_values(by="search_volume", ascending=False).reset_index(drop=True)


def analyze_seasonality_vs_demand(
    signals_df: pd.DataFrame,
    searches_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Correlates monthly seasonal demand indices with actual customer search volumes.
    """
    # Group signals by month
    signals_monthly = signals_df.groupby("month").agg(
        avg_demand_index=("demand_index", "mean"),
        avg_temperature=("temperature", "mean"),
        avg_rainfall_mm=("rainfall_mm", "mean"),
        holiday_events=("holiday_indicator", "sum"),
    ).reset_index()

    # Group searches by month from search_date
    searches_copy = searches_df.copy()
    searches_copy["search_month"] = pd.to_datetime(searches_copy["search_date"], errors="coerce").dt.month
    searches_monthly = searches_copy.groupby("search_month").agg(
        search_count=("search_id", "count"),
        booking_count=("booking_completed", "sum"),
        avg_search_price=("search_price", "mean"),
    ).reset_index().rename(columns={"search_month": "month"})

    # Merge
    merged = signals_monthly.merge(searches_monthly, on="month", how="left").fillna(0)
    merged["demand_index_vs_searches_corr"] = float(merged["avg_demand_index"].corr(merged["search_count"]))

    return merged
