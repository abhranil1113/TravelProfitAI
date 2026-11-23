"""
TBO InventoryIQ - Safe Data Loader for EDA (Phase 2)
Provides high-performance, immutable loading of processed datasets with Parquet/CSV fallback.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Any
import pandas as pd
import numpy as np

from eda.config import DATASET_PATHS, CURRENCY_MAP

logger = logging.getLogger(__name__)


def load_dataset(
    name: str,
    prefer_parquet: bool = True,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """
    Loads a single processed dataset by canonical name.
    
    Args:
        name: Key from DATASET_PATHS (e.g. 'hotel_bookings', 'flight_prices', etc.)
        prefer_parquet: If True, reads from parquet format for speed; falls back to CSV.
        nrows: Optional row limit for fast testing or large file exploration.
        
    Returns:
        pd.DataFrame: Immutable copy of the loaded dataset.
    """
    if name not in DATASET_PATHS:
        raise ValueError(
            f"Unknown dataset '{name}'. Available options: {list(DATASET_PATHS.keys())}"
        )

    paths = DATASET_PATHS[name]
    parquet_path = paths["parquet"]
    csv_path = paths["csv"]

    df = None
    if prefer_parquet and parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            if nrows is not None and len(df) > nrows:
                df = df.iloc[:nrows].copy()
            logger.debug(f"Loaded '{name}' from Parquet: {len(df)} rows.")
        except Exception as e:
            logger.warning(
                f"Failed to read parquet for '{name}' ({e}). Falling back to CSV: {csv_path}"
            )
            df = None

    if df is None:
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Neither Parquet ({parquet_path}) nor CSV ({csv_path}) found for '{name}'."
            )
        df = pd.read_csv(csv_path, nrows=nrows)
        logger.debug(f"Loaded '{name}' from CSV: {len(df)} rows.")

    # Return a clean copy to guarantee caller immutability
    return df.copy()


def load_all_datasets(
    prefer_parquet: bool = True,
    flight_nrows: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Loads all 9 processed datasets into a dictionary.
    
    Args:
        prefer_parquet: If True, uses Parquet files where available.
        flight_nrows: Optional row limit specifically for the large flights dataset.
        
    Returns:
        Dict[str, pd.DataFrame]: Dictionary mapping dataset names to loaded DataFrames.
    """
    datasets: Dict[str, pd.DataFrame] = {}
    for name in DATASET_PATHS.keys():
        nrows = flight_nrows if name == "flights" else None
        datasets[name] = load_dataset(name, prefer_parquet=prefer_parquet, nrows=nrows)

    return datasets


def get_dataset_metadata(name: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extracts high-level schema and memory profile for a loaded dataset.
    """
    return {
        "dataset_name": name,
        "row_count": len(df),
        "column_count": len(df.columns),
        "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        "currency": CURRENCY_MAP.get(name, "N/A"),
        "columns": list(df.columns),
    }
