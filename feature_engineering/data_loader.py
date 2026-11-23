"""
TBO InventoryIQ - Safe Data Loader for Feature Engineering (Phase 3)
Loads validated processed datasets from data/processed/ with Parquet optimization
and CSV fallback, guaranteeing source immutability.
"""

import logging
from typing import Dict, Optional, Any
import pandas as pd

from feature_engineering.config import PROCESSED_DATASET_PATHS

logger = logging.getLogger(__name__)


def load_dataset(
    name: str,
    prefer_parquet: bool = True,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """
    Loads a single processed dataset by canonical name.
    """
    if name not in PROCESSED_DATASET_PATHS:
        raise ValueError(
            f"Unknown dataset '{name}'. Available: {list(PROCESSED_DATASET_PATHS.keys())}"
        )

    paths = PROCESSED_DATASET_PATHS[name]
    parquet_path = paths["parquet"]
    csv_path = paths["csv"]

    df = None
    if prefer_parquet and parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            if nrows is not None and len(df) > nrows:
                df = df.iloc[:nrows].copy()
            logger.debug(f"Loaded '{name}' from Parquet ({len(df)} rows).")
        except Exception as e:
            logger.warning(f"Error reading Parquet for '{name}' ({e}). Trying CSV: {csv_path}")
            df = None

    if df is None:
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Neither Parquet ({parquet_path}) nor CSV ({csv_path}) found for '{name}'."
            )
        df = pd.read_csv(csv_path, nrows=nrows)
        logger.debug(f"Loaded '{name}' from CSV ({len(df)} rows).")

    # Return independent copy to preserve source immutability
    return df.copy()


def load_all_datasets(
    prefer_parquet: bool = True,
    flight_nrows: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Loads all 9 processed datasets into a dictionary.
    """
    datasets: Dict[str, pd.DataFrame] = {}
    for name in PROCESSED_DATASET_PATHS.keys():
        nrows = flight_nrows if name == "flights" else None
        datasets[name] = load_dataset(name, prefer_parquet=prefer_parquet, nrows=nrows)

    return datasets
