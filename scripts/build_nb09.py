"""
Builds notebooks/09_feature_engineering.ipynb
"""

import json
from pathlib import Path


def make_cell(cell_type, text):
    lines = [line + "\n" for line in text.split("\n")]
    if lines and lines[-1] == "\n":
        lines[-1] = ""
    cell = {
        "cell_type": cell_type,
        "metadata": {},
        "source": lines,
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


cells = [
    make_cell(
        "markdown",
        """# 09. TBO InventoryIQ – Feature Engineering & Dataset Transformation
**Phase 3: Production Feature Engineering & Split Manifests**  
**Team:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)

This notebook inspects the engineered feature datasets across all travel verticals, verifies quality bounds, reviews the target leakage audit, and examines the chronological train/validation/test split manifests.""",
    ),
    make_cell(
        "code",
        """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
import json
from feature_engineering.config import FEATURES_DATA_DIR, REPORTS_DIR""",
    ),
    make_cell("markdown", "## 1. Inspect All 7 Engineered Feature Datasets"),
    make_cell(
        "code",
        """summary_path = REPORTS_DIR / "feature_generation_summary.json"
with open(summary_path, "r", encoding="utf-8") as f:
    summary_data = json.load(f)

summary_df = pd.DataFrame(summary_data["datasets"])
summary_df[["dataset_name", "row_count", "column_count", "parquet_size_mb", "csv_size_mb"]]""",
    ),
    make_cell("markdown", "## 2. Sample Hotel Cancellation Features (Leakage-Quarantined)"),
    make_cell(
        "code",
        """hotel_feats = pd.read_parquet(FEATURES_DATA_DIR / "hotel" / "hotel_cancellation_features.parquet")
print(f"Hotel Features Shape: {hotel_feats.shape}")
hotel_feats[["is_canceled", "lead_time_days", "lead_time_bucket", "total_stay_nights", "adr", "adr_per_guest", "market_segment_historical_cancel_rate"]].head()""",
    ),
    make_cell("markdown", "## 3. Sample Flight Dynamic Pricing Features"),
    make_cell(
        "code",
        """price_feats = pd.read_parquet(FEATURES_DATA_DIR / "flight_prices" / "flight_price_features.parquet")
print(f"Flight Price Features Shape: {price_feats.shape}")
price_feats[["price", "days_left", "days_left_bucket", "duration_hours", "duration_bucket", "class", "airline"]].head()""",
    ),
    make_cell("markdown", "## 4. Sample Inventory Utilization & Depletion Velocity Features"),
    make_cell(
        "code",
        """inv_feats = pd.read_parquet(FEATURES_DATA_DIR / "inventory" / "inventory_features.parquet")
print(f"Inventory Features Shape: {inv_feats.shape}")
inv_feats[["inventory_id", "travel_date", "snapshot_date", "total_capacity", "occupancy_rate", "availability_rate", "booking_velocity_units_per_day", "inventory_depletion_velocity"]].head()""",
    ),
    make_cell("markdown", "## 5. Sample Supplier Profitability Features"),
    make_cell(
        "code",
        """supplier_feats = pd.read_parquet(FEATURES_DATA_DIR / "supplier" / "supplier_profitability_features.parquet")
print(f"Supplier Features Shape: {supplier_feats.shape}")
supplier_feats[["offer_id", "supplier_id", "purchase_cost_inr", "selling_price_inr", "gross_margin_inr", "gross_margin_percentage", "markup_percentage", "is_negative_margin"]].head()""",
    ),
    make_cell("markdown", "## 6. Review Chronological Train/Validation/Test Split Manifests"),
    make_cell(
        "code",
        """manifest_path = REPORTS_DIR / "dataset_split_manifest.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

for ds_name, sinfo in manifest["datasets"].items():
    print(f"Dataset: {ds_name} (Total: {sinfo['total_records']:,} rows, Split Key: {sinfo['split_key']})")
    print(f"  Train: {sinfo['train']['records']:,} ({sinfo['train']['pct']}%)")
    print(f"  Validation: {sinfo['validation']['records']:,} ({sinfo['validation']['pct']}%)")
    print(f"  Test: {sinfo['test']['records']:,} ({sinfo['test']['pct']}%)")""",
    ),
    make_cell("markdown", "## 7. Review Feature Dictionary Catalog"),
    make_cell(
        "code",
        """dict_df = pd.read_csv(REPORTS_DIR / "feature_dictionary.csv")
print(f"Total Documented Features: {len(dict_df)}")
dict_df[["feature_name", "dataset_name", "data_type", "business_purpose", "leakage_status"]].head(15)""",
    ),
]

nb = {
    "cells": cells,
    "metadata": {
        "language_info": {"name": "python", "version": "3.10.0"},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(Path("notebooks/09_feature_engineering.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print("Generated notebooks/09_feature_engineering.ipynb successfully.")
