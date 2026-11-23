"""
TBO InventoryIQ - Safe Modeling Data Loader (Phase 4)
Loads registered datasets with Parquet optimization and CSV fallback,
guaranteeing source immutability.
"""

from typing import Optional
from pathlib import Path
import pandas as pd
import logging

from modeling.registry.dataset_registry import DatasetRegistry

logger = logging.getLogger(__name__)


def load_modeling_dataset(
    dataset_name: str,
    prefer_parquet: bool = True,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """
    Loads a registered dataset into a pandas DataFrame.
    Guarantees returning an independent copy to protect source immutability.
    """
    registry = DatasetRegistry()
    meta = registry.get(dataset_name)

    path = meta.file_path
    if prefer_parquet and path.suffix == ".parquet" and path.exists():
        try:
            df = pd.read_parquet(path)
            if nrows is not None and len(df) > nrows:
                df = df.iloc[:nrows].copy()
            logger.debug(f"Loaded '{dataset_name}' from Parquet ({len(df)} rows).")
            return df.copy()
        except Exception as e:
            logger.warning(f"Error loading Parquet for '{dataset_name}' ({e}). Falling back to CSV.")

    # CSV path lookup (either meta is CSV or sibling CSV exists)
    csv_path = path.with_suffix(".csv") if path.suffix == ".parquet" else path
    if csv_path.exists():
        df = pd.read_csv(csv_path, nrows=nrows)
        logger.debug(f"Loaded '{dataset_name}' from CSV ({len(df)} rows).")
        return df.copy()

    raise FileNotFoundError(f"Neither Parquet ({path}) nor CSV ({csv_path}) found for '{dataset_name}'.")
