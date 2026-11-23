"""
TBO InventoryIQ - End-to-End Cleaning & Validation Pipeline
Orchestrates raw dataset discovery, profiling, rule validation, targeted cleaning,
processed storage (CSV & Parquet), lineage recording, and final reporting.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from data_pipeline.config import (
    PROCESSED_PATHS,
    REPORT_PATHS,
    REPORTS_DIR,
    PROCESSED_DATA_DIR,
)
from data_pipeline.ingestion.dataset_loader import load_dataset, load_all_datasets
from data_pipeline.validation.validation_report import run_and_save_validation_reports
from data_pipeline.cleaning.clean_market_signals import clean_market_signals
from data_pipeline.cleaning.clean_inventory import clean_inventory_availability
from data_pipeline.cleaning.clean_supplier_offers import clean_supplier_offers
from data_pipeline.cleaning.clean_search_events import clean_search_events
from data_pipeline.cleaning.clean_flight_prices import clean_flight_prices
from data_pipeline.cleaning.clean_hotel_bookings import clean_hotel_bookings
from data_pipeline.cleaning.clean_flights import clean_airlines, clean_airports, clean_flights

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_cleaning_pipeline(
    flight_sample_rows: Optional[int] = None,
    deduplicate_hotel_rows: bool = False,
) -> Dict[str, Any]:
    """
    Executes the complete data cleaning and validation pipeline.
    
    1. Loads all 9 raw and synthetic datasets safely.
    2. Runs domain cleaning routines on each dataset with full lineage tracking.
    3. Writes cleaned datasets to data/processed/ in CSV & Parquet.
    4. Runs validation audits on both raw and processed datasets.
    5. Emits cleaning summary audit JSON and final validation report.
    """
    logger.info("=============================================================")
    logger.info("Starting TBO InventoryIQ Data Cleaning & Validation Pipeline")
    logger.info("=============================================================")

    # Step 1: Load raw & synthetic datasets
    logger.info("Phase 1: Loading raw and synthetic datasets...")
    raw_datasets = load_all_datasets(flight_sample_rows=flight_sample_rows)

    # Step 2: Clean each dataset with lineage
    logger.info("Phase 2: Executing domain cleaning modules with audit lineage...")
    cleaned_datasets: Dict[str, pd.DataFrame] = {}
    cleaning_summaries: Dict[str, Any] = {}

    # 1. Market Seasonal Signals
    logger.info("Cleaning market_seasonal_signals...")
    df_sig, meta_sig = clean_market_signals(raw_datasets["market_seasonal_signals"])
    cleaned_datasets["market_seasonal_signals"] = df_sig
    cleaning_summaries["market_seasonal_signals"] = meta_sig

    # 2. Inventory Availability
    logger.info("Cleaning inventory_availability...")
    df_inv, meta_inv = clean_inventory_availability(raw_datasets["inventory_availability"])
    cleaned_datasets["inventory_availability"] = df_inv
    cleaning_summaries["inventory_availability"] = meta_inv

    # 3. Supplier Offers
    logger.info("Cleaning supplier_offers...")
    df_off, meta_off = clean_supplier_offers(raw_datasets["supplier_offers"])
    cleaned_datasets["supplier_offers"] = df_off
    cleaning_summaries["supplier_offers"] = meta_off

    # 4. Customer Search Events
    logger.info("Cleaning customer_search_events...")
    df_se, meta_se = clean_search_events(raw_datasets["customer_search_events"])
    cleaned_datasets["customer_search_events"] = df_se
    cleaning_summaries["customer_search_events"] = meta_se

    # 5. Airlines
    logger.info("Cleaning airlines...")
    df_airl, meta_airl = clean_airlines(raw_datasets["airlines"])
    cleaned_datasets["airlines"] = df_airl
    cleaning_summaries["airlines"] = meta_airl

    # 6. Airports
    logger.info("Cleaning airports...")
    df_airp, meta_airp = clean_airports(raw_datasets["airports"])
    cleaned_datasets["airports"] = df_airp
    cleaning_summaries["airports"] = meta_airp

    # 7. Flights
    logger.info("Cleaning flights...")
    df_flt, meta_flt = clean_flights(raw_datasets["flights"])
    cleaned_datasets["flights"] = df_flt
    cleaning_summaries["flights"] = meta_flt

    # 8. Flight Prices (Preserves all 300,153 records with distinct durations/stops)
    logger.info("Cleaning flight_prices...")
    df_fp, meta_fp = clean_flight_prices(raw_datasets["flight_prices"])
    cleaned_datasets["flight_prices"] = df_fp
    cleaning_summaries["flight_prices"] = meta_fp

    # 9. Hotel Bookings (Filters data errors while flagging identical feature duplicates)
    logger.info("Cleaning hotel_bookings...")
    df_hb, meta_hb = clean_hotel_bookings(
        raw_datasets["hotel_bookings"],
        filter_data_errors=True,
        deduplicate_identical_rows=deduplicate_hotel_rows,
    )
    cleaned_datasets["hotel_bookings"] = df_hb
    cleaning_summaries["hotel_bookings"] = meta_hb

    # Step 3: Persist Cleaned Datasets to data/processed/
    logger.info("Phase 3: Writing cleaned datasets to data/processed/...")
    for name, df_clean in cleaned_datasets.items():
        if name in PROCESSED_PATHS:
            paths = PROCESSED_PATHS[name]
            csv_path = paths["csv"]
            parquet_path = paths["parquet"]

            csv_path.parent.mkdir(parents=True, exist_ok=True)
            parquet_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Saving '{name}' to {csv_path} and {parquet_path}...")
            df_clean.to_csv(csv_path, index=False)
            df_clean.to_parquet(parquet_path, index=False, engine="pyarrow")

    # Step 4: Write Cleaning Summary & Lineage JSON
    logger.info("Phase 4: Emitting cleaning summary and lineage audit report...")
    summary_path = REPORT_PATHS["cleaning_summary"]
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(cleaning_summaries, f, indent=2)

    # Step 5: Run comprehensive validation audits across raw & processed datasets
    logger.info("Phase 5: Generating comprehensive data quality audits and Markdown report...")
    run_and_save_validation_reports(
        raw_datasets=raw_datasets,
        processed_datasets=cleaned_datasets,
        cleaning_summaries=cleaning_summaries,
        output_dir=REPORTS_DIR,
    )

    logger.info("=============================================================")
    logger.info("Data Cleaning & Validation Pipeline Completed Successfully!")
    logger.info(f"Cleaned datasets written to: {PROCESSED_DATA_DIR}")
    logger.info(f"Quality reports written to:  {REPORTS_DIR}")
    logger.info("=============================================================")

    return {
        "cleaned_datasets": cleaned_datasets,
        "cleaning_summaries": cleaning_summaries,
    }


if __name__ == "__main__":
    run_cleaning_pipeline()
