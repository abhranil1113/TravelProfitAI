"""
Tests for Feature Metadata & Dictionary Catalog Module
"""

import pytest
import pandas as pd
from feature_engineering.feature_metadata import (
    generate_feature_dictionary_records,
    export_feature_metadata_and_dictionary,
)


def test_generate_feature_dictionary_records():
    datasets = {
        "hotel_cancellation_features": pd.DataFrame({
            "is_canceled": [0, 1],
            "lead_time_days": [10, 20],
            "adr": [100.0, 150.0],
        }),
        "flight_price_features": pd.DataFrame({
            "price": [5000.0, 7000.0],
            "days_left": [10, 20],
        }),
    }
    records = generate_feature_dictionary_records(datasets)
    assert len(records) == 5
    feature_names = [r["feature_name"] for r in records]
    assert "is_canceled" in feature_names
    assert "lead_time_days" in feature_names
    assert "price" in feature_names


def test_export_feature_metadata_and_dictionary(tmp_path, monkeypatch):
    import feature_engineering.feature_metadata as fm
    monkeypatch.setattr(fm, "REPORTS_DIR", tmp_path)

    datasets = {
        "hotel_cancellation_features": pd.DataFrame({"is_canceled": [0]}),
    }
    summaries = [{"dataset_name": "hotel_cancellation_features", "row_count": 1}]

    paths = export_feature_metadata_and_dictionary(datasets, summaries)
    assert paths["dictionary_csv"].exists()
    assert paths["metadata_json"].exists()
    assert paths["summary_json"].exists()
