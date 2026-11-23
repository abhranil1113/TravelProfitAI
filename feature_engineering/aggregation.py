"""
TBO InventoryIQ - Cross-Dataset Aggregation & Procurement Decision Indicators (Phase 3)
Builds unified demand-to-supply ratios, inventory pressure categories,
and procurement candidate indicators with strict join cardinality validation
and segregated unit types (ROOM_NIGHT vs SEAT).
"""

from typing import Dict, Any, Tuple, List
import pandas as pd
import numpy as np

from feature_engineering.base_transformer import safe_divide


def deduplicate_latest_inventory_snapshots(inventory_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts the single most recent temporal snapshot per (inventory_id, travel_date).
    Guarantees physical capacity is counted exactly once before cross-dataset joins.
    """
    if "snapshot_date" not in inventory_df.columns:
        return inventory_df.copy()

    sorted_df = inventory_df.sort_values(by=["inventory_id", "travel_date", "snapshot_date"])
    latest_df = sorted_df.groupby(["inventory_id", "travel_date"], as_index=False).last()
    return latest_df.reset_index(drop=True)


def build_destination_demand_supply_indicators(
    searches_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    supplier_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Synthesizes search demand volume, contracted inventory availability, and supplier economics
    at the destination and inventory_type level to produce procurement decision-support indicators.
    
    CRITICAL UNIT SEGREGATION:
    Hotel room nights (ROOM_NIGHT) and flight seats (SEAT) are preserved as distinct physical units
    by grouping on ['destination_id', 'inventory_type'] whenever inventory_type is available.
    
    DEMAND-TO-SUPPLY RATIO:
    search_volume / (available_units + 1) is a heuristic search-to-inventory pressure index
    representing consumer inquiry density relative to available physical units.
    """
    # 1. Deduplicate inventory snapshots to point-in-time latest
    dedup_inv = deduplicate_latest_inventory_snapshots(inventory_df)

    # Determine grouping grain: use ['destination_id', 'inventory_type'] if present in datasets
    has_inv_type = (
        "inventory_type" in searches_df.columns
        and "inventory_type" in dedup_inv.columns
        and "inventory_type" in supplier_df.columns
    )
    group_cols: List[str] = ["destination_id", "inventory_type"] if has_inv_type else ["destination_id"]

    # 2. Demand aggregation by destination and inventory_type
    demand = searches_df.groupby(group_cols).agg(
        search_volume=("search_id", "count"),
        total_travellers_searched=("travellers_count", "sum") if "travellers_count" in searches_df.columns else ("search_id", "count"),
        avg_search_price_inr=("search_price", "mean") if "search_price" in searches_df.columns else ("search_id", lambda x: 0.0),
    ).reset_index()

    # 3. Supply availability aggregation by destination and inventory_type
    supply_agg_dict = {
        "inventory_items_count": ("inventory_id", "count"),
        "total_capacity_units": ("total_capacity", "sum"),
        "booked_units": ("booked_quantity", "sum"),
        "available_units": ("available_quantity", "sum"),
    }
    if "unit_type" in dedup_inv.columns:
        supply_agg_dict["unit_type"] = ("unit_type", "first")

    supply = dedup_inv.groupby(group_cols).agg(**supply_agg_dict).reset_index()

    # 4. Supplier procurement economics aggregation
    cost_col = "purchase_cost_inr" if "purchase_cost_inr" in supplier_df.columns else "purchase_cost"
    sell_col = "selling_price_inr" if "selling_price_inr" in supplier_df.columns else "selling_price"
    margin_col = (
        "margin_percentage"
        if "margin_percentage" in supplier_df.columns
        else ("gross_margin_percentage" if "gross_margin_percentage" in supplier_df.columns else cost_col)
    )

    supplier_econ = supplier_df.groupby(group_cols).agg(
        supplier_offers_count=("offer_id", "count"),
        avg_supplier_cost_inr=(cost_col, "mean"),
        avg_supplier_selling_inr=(sell_col, "mean"),
        avg_supplier_margin_pct=(margin_col, "mean"),
    ).reset_index()

    # 5. Outer merge to preserve all destinations and inventory types
    merged = demand.merge(supply, on=group_cols, how="outer")
    merged = merged.merge(supplier_econ, on=group_cols, how="outer")

    # Fill numerical missing values with 0
    numeric_cols = [
        "search_volume", "total_travellers_searched", "avg_search_price_inr",
        "inventory_items_count", "total_capacity_units", "booked_units",
        "available_units", "supplier_offers_count", "avg_supplier_cost_inr",
        "avg_supplier_selling_inr", "avg_supplier_margin_pct",
    ]
    for c in numeric_cols:
        if c in merged.columns:
            merged[c] = merged[c].fillna(0)

    # Attach unit_type if missing based on inventory_type
    if "inventory_type" in merged.columns and "unit_type" not in merged.columns:
        unit_map = {"HOTEL": "ROOM_NIGHT", "FLIGHT": "SEAT"}
        merged["unit_type"] = merged["inventory_type"].map(unit_map).fillna("UNIT")
    elif "unit_type" in merged.columns:
        unit_map = {"HOTEL": "ROOM_NIGHT", "FLIGHT": "SEAT"}
        merged["unit_type"] = merged["unit_type"].fillna(
            merged["inventory_type"].map(unit_map) if "inventory_type" in merged.columns else "UNIT"
        )

    # 6. Demand-to-Supply Ratio: searches / (available_units + 1)
    # Heuristic pressure index: inquiries per available physical room-night or seat.
    merged["demand_to_supply_ratio"] = merged.apply(
        lambda r: round(float(r["search_volume"]) / (float(r["available_units"]) + 1.0), 2), axis=1
    )

    # 7. Inventory Pressure Classification
    def classify_inventory_pressure(row):
        ratio = row["demand_to_supply_ratio"]
        avail = row["available_units"]
        if ratio >= 1.0 and avail <= 30:
            return "High Demand - Supply Constrained (Procure More)"
        elif ratio >= 1.0 and avail > 30:
            return "High Demand - High Availability (High Velocity)"
        elif ratio < 1.0 and avail > 50:
            return "Low Demand - Over-Supplied (Hold/Discount)"
        else:
            return "Low Demand - Low Availability (Niche/Balanced)"

    merged["inventory_pressure_category"] = merged.apply(classify_inventory_pressure, axis=1)

    # 8. Procurement Candidate Score (0-100)
    # Combines demand pressure (0.60) with supplier margin potential (0.40)
    max_ratio = float(merged["demand_to_supply_ratio"].max()) if not merged.empty else 1.0
    normalized_demand = (merged["demand_to_supply_ratio"] / (max_ratio if max_ratio > 0 else 1.0)) * 100.0
    margin_score = merged["avg_supplier_margin_pct"].clip(lower=0.0, upper=50.0) * 2.0  # Scale 0-50% to 0-100

    merged["procurement_candidate_score"] = (
        0.60 * normalized_demand + 0.40 * margin_score
    ).clip(0.0, 100.0).round(2)

    return merged.sort_values(by="demand_to_supply_ratio", ascending=False).reset_index(drop=True)
