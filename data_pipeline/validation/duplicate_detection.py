"""
TBO InventoryIQ - Duplicate Detection Module
Identifies exact row duplicates, primary key collisions, and business-record duplicates.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
from data_pipeline.config import PRIMARY_KEYS


def detect_duplicates(
    dataset_name: str,
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Detects exact row duplicates and primary key duplicates for a dataset.
    Returns metrics and duplicate record breakdowns.
    """
    total_rows = len(df)
    exact_dup_mask = df.duplicated()
    exact_dup_count = int(exact_dup_mask.sum())

    pk = PRIMARY_KEYS.get(dataset_name)
    pk_dup_count = 0
    pk_cols_str = "None"

    if pk:
        if isinstance(pk, str):
            if pk in df.columns:
                pk_dup_count = int(df.duplicated(subset=[pk]).sum())
                pk_cols_str = pk
        elif isinstance(pk, list):
            available_pks = [c for c in pk if c in df.columns]
            if len(available_pks) == len(pk):
                pk_dup_count = int(df.duplicated(subset=available_pks).sum())
                pk_cols_str = "+".join(available_pks)

    # Business entity duplicates check
    business_dup_count = 0
    business_rule_desc = "None"

    if dataset_name == "inventory_availability":
        # Inventory item snapshot for same inventory, date and snapshot date
        cols = ["inventory_id", "travel_date", "snapshot_date"]
        if all(c in df.columns for c in cols):
            business_dup_count = int(df.duplicated(subset=cols).sum())
            business_rule_desc = "Duplicate snapshot for same inventory_id, travel_date, snapshot_date"
    elif dataset_name == "supplier_offers":
        # Same supplier offering same inventory for same travel date
        cols = ["supplier_id", "inventory_id", "travel_date"]
        if all(c in df.columns for c in cols):
            business_dup_count = int(df.duplicated(subset=cols).sum())
            business_rule_desc = "Duplicate offer for same supplier_id, inventory_id, travel_date"
    elif dataset_name == "customer_search_events":
        # Search by same user for same travel date & destination on same search date
        cols = ["user_id", "search_date", "travel_date", "destination_id", "inventory_type"]
        if all(c in df.columns for c in cols):
            business_dup_count = int(df.duplicated(subset=cols).sum())
            business_rule_desc = "Repeated user search event with identical search parameters"
    elif dataset_name == "hotel_bookings":
        # Exact full row duplicate in hotel bookings
        business_dup_count = exact_dup_count
        business_rule_desc = "Exact duplicate reservation rows"

    return {
        "dataset_name": dataset_name,
        "total_rows": total_rows,
        "exact_duplicates": exact_dup_count,
        "exact_dup_percentage": round((exact_dup_count / total_rows * 100), 4) if total_rows > 0 else 0.0,
        "primary_key": pk_cols_str,
        "pk_duplicates": pk_dup_count,
        "business_entity_rule": business_rule_desc,
        "business_duplicates": business_dup_count,
    }


def detect_all_duplicates(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Detect duplicates across all datasets and produce summary DataFrame.
    """
    records = []
    for name, df in datasets.items():
        res = detect_duplicates(name, df)
        records.append(res)
    return pd.DataFrame(records)
