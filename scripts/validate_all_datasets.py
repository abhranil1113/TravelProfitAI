"""
TBO InventoryIQ - Master Validation & Cleaning CLI Script
Usage:
    python scripts/validate_all_datasets.py [--flight-sample ROWS]
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.cleaning.cleaning_pipeline import run_cleaning_pipeline
from data_pipeline.config import REPORT_PATHS, PROCESSED_PATHS


def main():
    parser = argparse.ArgumentParser(description="TBO InventoryIQ Data Validation & Cleaning Pipeline")
    parser.add_argument(
        "--flight-sample",
        type=int,
        default=None,
        help="Optional row limit for flights.csv to accelerate testing (default: None, processes all records)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("TBO InventoryIQ - Travel Inventory Optimization Platform")
    print("Master Data Cleaning & Quality Validation Pipeline")
    print("=" * 70)

    results = run_cleaning_pipeline(flight_sample_rows=args.flight_sample)
    summaries = results["cleaning_summaries"]

    print("\n" + "=" * 70)
    print("CLEANING AUDIT SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Dataset Name':<28} | {'Initial Rows':<12} | {'Final Rows':<12} | {'Removed':<8} | {'Retention %':<11}")
    print("-" * 80)

    for name, meta in summaries.items():
        init_r = meta["initial_rows"]
        final_r = meta["final_rows"]
        rem_r = meta["rows_removed"]
        ret_pct = round((final_r / init_r * 100), 2) if init_r > 0 else 0.0
        print(f"{name:<28} | {init_r:<12,d} | {final_r:<12,d} | {rem_r:<8,d} | {ret_pct:<10.2f}%")

    print("-" * 80)
    print("\nGenerated Quality Audit Reports:")
    for rep_name, rep_path in REPORT_PATHS.items():
        exists_sym = "[OK]" if rep_path.exists() else "[MISSING]"
        print(f"  {exists_sym} {rep_name:<20} -> {rep_path}")

    print("\nGenerated Processed Datasets:")
    for ds_name, p_dict in PROCESSED_PATHS.items():
        csv_ok = "[OK]" if p_dict["csv"].exists() else "[MISSING]"
        pq_ok = "[OK]" if p_dict["parquet"].exists() else "[MISSING]"
        print(f"  {csv_ok} {ds_name} (CSV)     -> {p_dict['csv']}")
        print(f"  {pq_ok} {ds_name} (Parquet) -> {p_dict['parquet']}")

    print("\nPipeline execution completed successfully.")


if __name__ == "__main__":
    main()
