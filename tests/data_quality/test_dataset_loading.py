"""
TBO InventoryIQ - Automated Tests: Dataset Loading & Raw Preservation
"""

import pytest
import os
import pandas as pd
from pathlib import Path

from data_pipeline.ingestion.dataset_loader import load_dataset, load_all_datasets
from data_pipeline.config import DATASET_PATHS


def test_load_known_dataset():
    """Verify loading airlines table returns expected 14 rows and 2 columns."""
    df = load_dataset("airlines")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 14
    assert "IATA_CODE" in df.columns
    assert "AIRLINE" in df.columns


def test_load_unknown_dataset():
    """Verify ValueError is raised for unregistered dataset."""
    with pytest.raises(ValueError, match="Unknown dataset name"):
        load_dataset("non_existent_dataset")


def test_load_file_not_found(tmp_path):
    """Verify FileNotFoundError is raised when custom path does not exist."""
    missing_file = tmp_path / "does_not_exist.csv"
    with pytest.raises(FileNotFoundError):
        load_dataset("airlines", custom_path=missing_file)


def test_load_flights_sample():
    """Verify flights dataset can be sampled without memory exhaustion or mixed-type warnings."""
    df = load_dataset("flights", nrows=100)
    assert len(df) == 100
    assert "AIRLINE" in df.columns
    assert "ORIGIN_AIRPORT" in df.columns
    assert "DESTINATION_AIRPORT" in df.columns
    assert isinstance(df["ORIGIN_AIRPORT"].iloc[0], str)


def test_load_flight_prices_index_handling():
    """Verify Unnamed: 0 is safely formatted as price_record_id."""
    df = load_dataset("flight_prices", nrows=50)
    assert "Unnamed: 0" not in df.columns
    assert "price_record_id" in df.columns
    assert df["price_record_id"].iloc[0].startswith("PRC_")


def test_load_synthetic_datasets_string_ids():
    """Verify synthetic datasets load ID fields as strings."""
    df = load_dataset("customer_search_events", nrows=50)
    assert isinstance(df["search_id"].iloc[0], str)
    assert isinstance(df["destination_id"].iloc[0], str)


def test_raw_files_preservation():
    """Verify all raw and synthetic source files exist and have non-zero size."""
    for name, path in DATASET_PATHS.items():
        assert path.exists(), f"Source file missing: {path}"
        assert path.stat().st_size > 0, f"Source file is empty: {path}"
