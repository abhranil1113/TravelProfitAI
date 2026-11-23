"""
TBO InventoryIQ - Dataset Split Manifest Manager (Phase 3)
Constructs reproducible, leakage-free chronological and grouped dataset splits
for future model training without executing any training in Phase 3.
"""

from typing import Dict, Any, List
import json
from pathlib import Path
import pandas as pd

from feature_engineering.config import REPORTS_DIR


def generate_chronological_splits(
    feature_datasets: Dict[str, pd.DataFrame]
) -> Dict[str, Any]:
    """
    Computes deterministic chronological split manifests for time-dependent datasets.
    """
    manifest = {
        "project": "TBO InventoryIQ",
        "phase": "Phase 3 - Feature Engineering & Split Manifest",
        "split_strategy": "Strict Chronological / Time-Series (Zero Future Leakage)",
        "datasets": {},
    }

    # 1. Hotel Cancellation Split (Arrival Date Cohorts & Transaction Booking Date)
    if "hotel_cancellation_features" in feature_datasets:
        hdf = feature_datasets["hotel_cancellation_features"]
        train_mask = hdf["arrival_date"] <= "2016-12-31"
        val_mask = (hdf["arrival_date"] >= "2017-01-01") & (hdf["arrival_date"] <= "2017-04-30")
        test_mask = hdf["arrival_date"] >= "2017-05-01"

        hotel_split_dict = {
            "split_key": "arrival_date",
            "split_type": "Arrival Date Seasonal Cohort Split",
            "total_records": len(hdf),
            "train": {
                "records": int(train_mask.sum()),
                "pct": round(float(train_mask.mean()) * 100, 2),
                "date_range": ["2015-07-01", "2016-12-31"],
                "target_cancellation_rate_pct": round(float(hdf.loc[train_mask, "is_canceled"].mean()) * 100, 2),
            },
            "validation": {
                "records": int(val_mask.sum()),
                "pct": round(float(val_mask.mean()) * 100, 2),
                "date_range": ["2017-01-01", "2017-04-30"],
                "target_cancellation_rate_pct": round(float(hdf.loc[val_mask, "is_canceled"].mean()) * 100, 2),
            },
            "test": {
                "records": int(test_mask.sum()),
                "pct": round(float(test_mask.mean()) * 100, 2),
                "date_range": ["2017-05-01", "2017-08-31"],
                "target_cancellation_rate_pct": round(float(hdf.loc[test_mask, "is_canceled"].mean()) * 100, 2),
            },
        }

        # Add booking_date split if synthesized booking_date column is present
        if "booking_date" in hdf.columns:
            b_train_mask = hdf["booking_date"] <= "2016-11-06"
            b_val_mask = (hdf["booking_date"] >= "2016-11-07") & (hdf["booking_date"] <= "2017-02-03")
            b_test_mask = hdf["booking_date"] >= "2017-02-04"
            hotel_split_dict["booking_date_chronological_split"] = {
                "split_key": "booking_date",
                "split_type": "Transaction Point-in-Time Booking Stream Split",
                "train": {
                    "records": int(b_train_mask.sum()),
                    "pct": round(float(b_train_mask.mean()) * 100, 2),
                    "booking_date_range": [str(hdf.loc[b_train_mask, "booking_date"].min()), "2016-11-06"],
                    "target_cancellation_rate_pct": round(float(hdf.loc[b_train_mask, "is_canceled"].mean()) * 100, 2) if b_train_mask.any() else 0.0,
                },
                "validation": {
                    "records": int(b_val_mask.sum()),
                    "pct": round(float(b_val_mask.mean()) * 100, 2),
                    "booking_date_range": ["2016-11-07", "2017-02-03"],
                    "target_cancellation_rate_pct": round(float(hdf.loc[b_val_mask, "is_canceled"].mean()) * 100, 2) if b_val_mask.any() else 0.0,
                },
                "test": {
                    "records": int(b_test_mask.sum()),
                    "pct": round(float(b_test_mask.mean()) * 100, 2),
                    "booking_date_range": ["2017-02-04", str(hdf.loc[b_test_mask, "booking_date"].max())],
                    "target_cancellation_rate_pct": round(float(hdf.loc[b_test_mask, "is_canceled"].mean()) * 100, 2) if b_test_mask.any() else 0.0,
                },
            }

        manifest["datasets"]["hotel_cancellation_features"] = hotel_split_dict

    # 2. Flight Price Split (Scenario-Based Horizon Split)
    if "flight_price_features" in feature_datasets:
        fpdf = feature_datasets["flight_price_features"]
        train_mask = fpdf["days_left"] >= 15
        val_mask = (fpdf["days_left"] >= 8) & (fpdf["days_left"] < 15)
        test_mask = fpdf["days_left"] < 8

        manifest["datasets"]["flight_price_features"] = {
            "split_type": "Scenario-Based Horizon Split (Advance Booking vs. Immediate Departure)",
            "split_key": "days_left",
            "calendar_timestamps_present": False,
            "rationale": "Kaggle source dataset lacks calendar collection timestamps. Split evaluates model generalization across booking horizons: advance booking (>=15 days) to near-departure (1-7 days).",
            "total_records": len(fpdf),
            "train": {
                "records": int(train_mask.sum()),
                "pct": round(float(train_mask.mean()) * 100, 2),
                "days_left_range": [15, 49],
                "avg_price_inr": round(float(fpdf.loc[train_mask, "price"].mean()), 2),
            },
            "validation": {
                "records": int(val_mask.sum()),
                "pct": round(float(val_mask.mean()) * 100, 2),
                "days_left_range": [8, 14],
                "avg_price_inr": round(float(fpdf.loc[val_mask, "price"].mean()), 2),
            },
            "test": {
                "records": int(test_mask.sum()),
                "pct": round(float(test_mask.mean()) * 100, 2),
                "days_left_range": [1, 7],
                "avg_price_inr": round(float(fpdf.loc[test_mask, "price"].mean()), 2),
            },
        }

    # 3. Customer Search Demand Split (Chronological on search_year/month)
    if "customer_demand_features" in feature_datasets:
        sdf = feature_datasets["customer_demand_features"]
        n = len(sdf)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)

        manifest["datasets"]["customer_demand_features"] = {
            "split_key": "chronological_index",
            "total_records": n,
            "train": {"records": train_end, "pct": 70.0},
            "validation": {"records": val_end - train_end, "pct": 15.0},
            "test": {"records": n - val_end, "pct": 15.0},
        }

    # 4. Inventory Availability Split (Chronological on snapshot_date)
    if "inventory_features" in feature_datasets:
        idf = feature_datasets["inventory_features"]
        n = len(idf)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)

        manifest["datasets"]["inventory_features"] = {
            "split_key": "chronological_snapshot_date",
            "total_records": n,
            "train": {"records": train_end, "pct": 70.0},
            "validation": {"records": val_end - train_end, "pct": 15.0},
            "test": {"records": n - val_end, "pct": 15.0},
        }

    # 5. Supplier Profitability Split
    if "supplier_profitability_features" in feature_datasets:
        spdf = feature_datasets["supplier_profitability_features"]
        n = len(spdf)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)

        manifest["datasets"]["supplier_profitability_features"] = {
            "split_key": "chronological_travel_date",
            "total_records": n,
            "train": {"records": train_end, "pct": 70.0},
            "validation": {"records": val_end - train_end, "pct": 15.0},
            "test": {"records": n - val_end, "pct": 15.0},
        }

    manifest_path = REPORTS_DIR / "dataset_split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest
