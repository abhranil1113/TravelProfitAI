"""
TBO InventoryIQ - Feature Dataset Builder (Phase 3)
Orchestrates domain transformers to construct and serialize all separate
feature datasets in both high-performance Parquet and standard CSV formats.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import pandas as pd

from feature_engineering.config import FEATURE_DIRS
from feature_engineering.data_loader import load_dataset
from feature_engineering.hotel_features import HotelFeatureTransformer
from feature_engineering.flight_features import (
    FlightPriceFeatureTransformer,
    FlightOperationsFeatureTransformer,
)
from feature_engineering.search_features import CustomerSearchFeatureTransformer
from feature_engineering.inventory_features import InventoryFeatureTransformer
from feature_engineering.supplier_features import SupplierFeatureTransformer
from feature_engineering.demand_features import MarketDemandFeatureTransformer
from feature_engineering.aggregation import build_destination_demand_supply_indicators

logger = logging.getLogger(__name__)


def build_and_save_dataset(
    df_transformed: pd.DataFrame,
    dir_key: str,
    base_filename: str,
) -> Dict[str, Any]:
    """
    Saves transformed DataFrame to both Parquet and CSV in target directory.
    """
    target_dir = FEATURE_DIRS[dir_key]
    parquet_path = target_dir / f"{base_filename}.parquet"
    csv_path = target_dir / f"{base_filename}.csv"

    # Write Parquet
    df_transformed.to_parquet(parquet_path, index=False)
    # Write CSV
    df_transformed.to_csv(csv_path, index=False)

    size_parquet_mb = round(parquet_path.stat().st_size / (1024 * 1024), 2)
    size_csv_mb = round(csv_path.stat().st_size / (1024 * 1024), 2)

    logger.info(
        f"Saved '{base_filename}' ({len(df_transformed):,} rows, {len(df_transformed.columns)} cols) "
        f"-> Parquet ({size_parquet_mb} MB), CSV ({size_csv_mb} MB)"
    )

    return {
        "dataset_name": base_filename,
        "row_count": len(df_transformed),
        "column_count": len(df_transformed.columns),
        "parquet_path": str(parquet_path),
        "csv_path": str(csv_path),
        "parquet_size_mb": size_parquet_mb,
        "csv_size_mb": size_csv_mb,
    }


def build_all_feature_datasets(
    flight_sample_rows: int = None,
    process_full_flights: bool = False,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """
    Generates all 7 domain feature datasets and cross-domain procurement indicators.
    
    NOTE ON FLIGHT OPERATIONS SCOPE:
    `cleaned_flights.parquet` is stored as a deterministic 1,000-row chronological development sample
    (starting from 2015-01-01) created during Phase 1 data cleaning to allow instantaneous testing
    and prevent memory exhaustion on resource-constrained environments. The raw source dataset
    `data/raw/flights/flights.csv` contains all 5,819,079 records (565 MB).
    """
    feature_datasets: Dict[str, pd.DataFrame] = {}
    generation_summaries = []

    # 1. Hotel Cancellation Features
    logger.info("Transforming hotel_bookings -> hotel_cancellation_features...")
    raw_hotel = load_dataset("hotel_bookings")
    hotel_transformer = HotelFeatureTransformer()
    hotel_feats = hotel_transformer.transform(raw_hotel)
    feature_datasets["hotel_cancellation_features"] = hotel_feats
    s1 = build_and_save_dataset(hotel_feats, "hotel", "hotel_cancellation_features")
    generation_summaries.append(s1)

    # 2. Flight Price Features
    logger.info("Transforming flight_prices -> flight_price_features...")
    raw_prices = load_dataset("flight_prices")
    price_transformer = FlightPriceFeatureTransformer()
    price_feats = price_transformer.transform(raw_prices)
    feature_datasets["flight_price_features"] = price_feats
    s2 = build_and_save_dataset(price_feats, "flight_prices", "flight_price_features")
    generation_summaries.append(s2)

    # 3. Flight Operations Features
    logger.info("Transforming flights -> flight_operations_features...")
    raw_flights = load_dataset("flights", nrows=flight_sample_rows)
    logger.info(
        f"Loaded flight operations dataset with {len(raw_flights):,} records "
        f"(Development sample mode; raw source contains 5,819,079 records)."
    )
    flight_ops_transformer = FlightOperationsFeatureTransformer()
    flight_ops_feats = flight_ops_transformer.transform(raw_flights)
    feature_datasets["flight_operations_features"] = flight_ops_feats
    s3 = build_and_save_dataset(flight_ops_feats, "flights", "flight_operations_features")
    generation_summaries.append(s3)

    # 4. Customer Search Demand Features
    logger.info("Transforming customer_search_events -> customer_demand_features...")
    raw_searches = load_dataset("customer_search_events")
    search_transformer = CustomerSearchFeatureTransformer()
    search_feats = search_transformer.transform(raw_searches)
    feature_datasets["customer_demand_features"] = search_feats
    s4 = build_and_save_dataset(search_feats, "customer_demand", "customer_demand_features")
    generation_summaries.append(s4)

    # 5. Inventory Utilization Features
    logger.info("Transforming inventory_availability -> inventory_features...")
    raw_inventory = load_dataset("inventory_availability")
    inventory_transformer = InventoryFeatureTransformer()
    inv_feats = inventory_transformer.transform(raw_inventory)
    feature_datasets["inventory_features"] = inv_feats
    s5 = build_and_save_dataset(inv_feats, "inventory", "inventory_features")
    generation_summaries.append(s5)

    # 6. Supplier Profitability Features
    logger.info("Transforming supplier_offers -> supplier_profitability_features...")
    raw_supplier = load_dataset("supplier_offers")
    supplier_transformer = SupplierFeatureTransformer()
    supplier_feats = supplier_transformer.transform(raw_supplier)
    feature_datasets["supplier_profitability_features"] = supplier_feats
    s6 = build_and_save_dataset(supplier_feats, "supplier", "supplier_profitability_features")
    generation_summaries.append(s6)

    # 7. Market Seasonality Features
    logger.info("Transforming market_seasonal_signals -> market_demand_features...")
    raw_signals = load_dataset("market_seasonal_signals")
    market_transformer = MarketDemandFeatureTransformer()
    market_feats = market_transformer.transform(raw_signals)
    feature_datasets["market_demand_features"] = market_feats
    s7 = build_and_save_dataset(market_feats, "market", "market_demand_features")
    generation_summaries.append(s7)

    # 8. Cross-Domain Destination Demand & Supply Indicators
    logger.info("Synthesizing searches + inventory + supplier -> destination_demand_supply_features...")
    demand_supply_feats = build_destination_demand_supply_indicators(
        raw_searches, raw_inventory, raw_supplier
    )
    feature_datasets["destination_demand_supply_features"] = demand_supply_feats
    s8 = build_and_save_dataset(demand_supply_feats, "market", "destination_demand_supply_features")
    generation_summaries.append(s8)

    return feature_datasets, generation_summaries
