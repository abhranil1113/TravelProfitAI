"""
TBO InventoryIQ - Dataset Ingestion & Loader
Provides robust, optimized, and validated loaders for all raw and synthetic datasets.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Union
import pandas as pd
import logging

from data_pipeline.config import DATASET_PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Optimized dtypes for high-volume flight datasets
FLIGHTS_DTYPES = {
    "YEAR": "int16",
    "MONTH": "int8",
    "DAY": "int8",
    "DAY_OF_WEEK": "int8",
    "AIRLINE": "string",
    "FLIGHT_NUMBER": "string",
    "TAIL_NUMBER": "string",
    "ORIGIN_AIRPORT": "string",
    "DESTINATION_AIRPORT": "string",
    "SCHEDULED_DEPARTURE": "float32",
    "DEPARTURE_TIME": "float32",
    "DEPARTURE_DELAY": "float32",
    "TAXI_OUT": "float32",
    "WHEELS_OFF": "float32",
    "SCHEDULED_TIME": "float32",
    "ELAPSED_TIME": "float32",
    "AIR_TIME": "float32",
    "DISTANCE": "float32",
    "WHEELS_ON": "float32",
    "TAXI_IN": "float32",
    "SCHEDULED_ARRIVAL": "float32",
    "ARRIVAL_TIME": "float32",
    "ARRIVAL_DELAY": "float32",
    "DIVERTED": "int8",
    "CANCELLED": "int8",
    "CANCELLATION_REASON": "string",
    "AIR_SYSTEM_DELAY": "float32",
    "SECURITY_DELAY": "float32",
    "AIRLINE_DELAY": "float32",
    "LATE_AIRCRAFT_DELAY": "float32",
    "WEATHER_DELAY": "float32",
}


def load_dataset(
    dataset_name: str,
    nrows: Optional[int] = None,
    custom_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Load a dataset by registered name or custom path with optimized typing.
    """
    if custom_path:
        file_path = Path(custom_path)
    elif dataset_name in DATASET_PATHS:
        file_path = DATASET_PATHS[dataset_name]
    else:
        raise ValueError(
            f"Unknown dataset name '{dataset_name}'. Available: {list(DATASET_PATHS.keys())}"
        )

    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found at: {file_path}")

    logger.info(f"Loading '{dataset_name}' from {file_path} (nrows={nrows})...")

    if dataset_name == "flights":
        # Load with explicit string typing for airport codes to prevent mixed type warnings
        df = pd.read_csv(
            file_path,
            nrows=nrows,
            dtype={
                "ORIGIN_AIRPORT": str,
                "DESTINATION_AIRPORT": str,
                "FLIGHT_NUMBER": str,
                "AIRLINE": str,
                "TAIL_NUMBER": str,
                "CANCELLATION_REASON": str,
            },
            low_memory=False,
        )
    elif dataset_name == "flight_prices":
        df = pd.read_csv(file_path, nrows=nrows)
        if "Unnamed: 0" in df.columns:
            # Preserve original source index as price_record_id string
            df["price_record_id"] = "PRC_" + df["Unnamed: 0"].astype(str)
            df.drop(columns=["Unnamed: 0"], inplace=True)
    elif dataset_name in ["customer_search_events", "supplier_offers", "inventory_availability"]:
        # Ensure string representation of identifiers preserving potential leading zeros
        dtype_spec = {
            col: str
            for col in [
                "search_id",
                "user_id",
                "destination_id",
                "origin_id",
                "offer_id",
                "supplier_id",
                "inventory_id",
                "snapshot_id",
            ]
        }
        df = pd.read_csv(file_path, nrows=nrows, dtype=dtype_spec)
    else:
        df = pd.read_csv(file_path, nrows=nrows)

    logger.info(f"Loaded '{dataset_name}' successfully: {len(df):,} rows, {len(df.columns)} columns.")
    return df


def load_all_datasets(
    flight_sample_rows: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Load all 9 datasets into a dictionary.
    flight_sample_rows can be used during test runs to limit memory usage on 5.8M rows.
    """
    dfs: Dict[str, pd.DataFrame] = {}
    for name in DATASET_PATHS.keys():
        nrows = flight_sample_rows if name == "flights" else None
        dfs[name] = load_dataset(name, nrows=nrows)
    return dfs
