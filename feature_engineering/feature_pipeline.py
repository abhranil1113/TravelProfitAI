"""
TBO InventoryIQ - Master Feature Engineering Pipeline Runner (Phase 3)
Executes end-to-end dataset transformation, quality validation, leakage auditing,
chronological splitting, and report generation.
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import logging
from typing import Dict, Any

from feature_engineering.config import REPORTS_DIR
from feature_engineering.dataset_builder import build_all_feature_datasets
from feature_engineering.feature_validation import validate_feature_dataset
from feature_engineering.leakage_detection import run_full_leakage_audit
from feature_engineering.split_manager import generate_chronological_splits
from feature_engineering.feature_metadata import export_feature_metadata_and_dictionary
from feature_engineering.report_generator import (
    generate_leakage_audit_report,
    generate_data_transformation_report,
    generate_feature_validation_report,
    generate_modeling_readiness_after_features_report,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_full_feature_pipeline(flight_sample_rows: int = None) -> Dict[str, Any]:
    """
    Executes the complete Phase 3 feature engineering pipeline.
    """
    logger.info("==================================================================")
    logger.info("Starting TBO InventoryIQ Phase 3: Feature Engineering Pipeline")
    logger.info("==================================================================")

    # 1. Build and serialize all feature datasets
    logger.info("Step 1: Transforming processed datasets into domain feature sets...")
    feature_datasets, summaries = build_all_feature_datasets(flight_sample_rows=flight_sample_rows)

    # 2. Validate all feature datasets
    logger.info("Step 2: Performing quality and mathematical consistency validation...")
    validation_results = []
    
    # Hotel validation
    v1 = validate_feature_dataset(
        feature_datasets["hotel_cancellation_features"],
        "hotel_cancellation_features",
        non_negative_columns=["lead_time_days", "total_stay_nights", "adr"],
        rate_columns_0_to_1=["weekend_nights_ratio", "weekday_nights_ratio"],
    )
    validation_results.append(v1)

    # Flight price validation
    v2 = validate_feature_dataset(
        feature_datasets["flight_price_features"],
        "flight_price_features",
        non_negative_columns=["price", "days_left", "duration_hours"],
    )
    validation_results.append(v2)

    # Flight operations validation
    v3 = validate_feature_dataset(
        feature_datasets["flight_operations_features"],
        "flight_operations_features",
        non_negative_columns=["flight_distance_miles", "scheduled_elapsed_time_minutes"],
    )
    validation_results.append(v3)

    # Customer search validation
    v4 = validate_feature_dataset(
        feature_datasets["customer_demand_features"],
        "customer_demand_features",
        non_negative_columns=["search_lead_days", "search_price_inr", "travellers_count"],
    )
    validation_results.append(v4)

    # Inventory validation
    v5 = validate_feature_dataset(
        feature_datasets["inventory_features"],
        "inventory_features",
        non_negative_columns=["total_capacity", "booked_quantity", "available_quantity"],
        rate_columns_0_to_1=["occupancy_rate", "inventory_utilization_rate", "availability_rate"],
        rate_columns_0_to_100=["availability_percentage"],
    )
    validation_results.append(v5)

    # Supplier validation
    v6 = validate_feature_dataset(
        feature_datasets["supplier_profitability_features"],
        "supplier_profitability_features",
        non_negative_columns=["purchase_cost_inr", "selling_price_inr", "minimum_purchase_qty"],
    )
    validation_results.append(v6)

    # Market demand validation
    v7 = validate_feature_dataset(
        feature_datasets["market_demand_features"],
        "market_demand_features",
        non_negative_columns=["rainfall_mm", "demand_index"],
        rate_columns_0_to_100=["composite_seasonal_demand_score"],
    )
    validation_results.append(v7)

    # 3. Target Leakage Audit
    logger.info("Step 3: Conducting systematic target leakage audit...")
    ds_feature_map = {name: list(df.columns) for name, df in feature_datasets.items()}
    leakage_records = run_full_leakage_audit(ds_feature_map)

    # 4. Generate Chronological Split Manifests
    logger.info("Step 4: Constructing reproducible chronological split manifests...")
    manifest_path = REPORTS_DIR / "dataset_split_manifest.json"
    split_manifest = generate_chronological_splits(feature_datasets, output_path=manifest_path)

    # 5. Export Feature Dictionary & Metadata
    logger.info("Step 5: Exporting feature dictionary and metadata catalogs...")
    meta_paths = export_feature_metadata_and_dictionary(feature_datasets, summaries)

    # 6. Compile Reports
    logger.info("Step 6: Generating Phase 3 markdown reports...")
    generate_leakage_audit_report(leakage_records)
    generate_data_transformation_report(summaries, feature_datasets)
    generate_feature_validation_report(validation_results)
    generate_modeling_readiness_after_features_report()

    logger.info("==================================================================")
    logger.info("Phase 3 Feature Engineering Pipeline Complete - All Assets Ready")
    logger.info("==================================================================")

    return {
        "status": "COMPLETED",
        "feature_datasets_count": len(feature_datasets),
        "total_features_engineered": sum(len(df.columns) for df in feature_datasets.values()),
        "validations_passed": sum(1 for v in validation_results if "PASSED" in v["status"]),
        "leakage_audits_count": len(leakage_records),
        "split_manifest": split_manifest,
    }


if __name__ == "__main__":
    run_full_feature_pipeline()
