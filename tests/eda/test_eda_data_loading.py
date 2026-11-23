"""
Tests for EDA Data Loader Module
Verifies parquet/csv loading, immutability, and metadata extraction.
"""

import pytest
import pandas as pd
from eda.data_loader import load_dataset, load_all_datasets, get_dataset_metadata
from eda.config import DATASET_PATHS


def test_load_each_dataset():
    """Verify all 9 datasets load successfully."""
    for name in DATASET_PATHS.keys():
        df = load_dataset(name, prefer_parquet=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0


def test_load_dataset_csv_fallback(monkeypatch, tmp_path):
    """Verify fallback to CSV when parquet is unavailable."""
    # Temporarily point parquet to non-existent file
    original_paths = DATASET_PATHS["airlines"].copy()
    DATASET_PATHS["airlines"]["parquet"] = tmp_path / "non_existent.parquet"
    try:
        df = load_dataset("airlines", prefer_parquet=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    finally:
        DATASET_PATHS["airlines"] = original_paths


def test_load_dataset_invalid_name():
    """Verify error when invalid dataset name is requested."""
    with pytest.raises(ValueError, match="Unknown dataset"):
        load_dataset("invalid_dataset_xyz")


def test_dataset_immutability():
    """Verify modifying a loaded DataFrame copy does not affect repeated loads."""
    df1 = load_dataset("airlines")
    initial_val = df1.iloc[0, 0]
    df1.iloc[0, 0] = "MODIFIED"
    
    df2 = load_dataset("airlines")
    assert df2.iloc[0, 0] == initial_val
    assert df2.iloc[0, 0] != "MODIFIED"


def test_get_dataset_metadata():
    """Verify metadata extraction."""
    df = load_dataset("airlines")
    meta = get_dataset_metadata("airlines", df)
    assert meta["dataset_name"] == "airlines"
    assert meta["row_count"] == len(df)
    assert meta["column_count"] == len(df.columns)
    assert meta["memory_mb"] >= 0
    assert "IATA_CODE" in meta["columns"]
