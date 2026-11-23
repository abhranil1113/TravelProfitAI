"""
Tests for Feature Dataset Builder Module
"""

import pytest
from feature_engineering.dataset_builder import build_all_feature_datasets


def test_build_all_feature_datasets():
    # Run with small sample for flights to execute quickly
    datasets, summaries = build_all_feature_datasets(flight_sample_rows=100)
    assert len(datasets) == 8
    assert "hotel_cancellation_features" in datasets
    assert "flight_price_features" in datasets
    assert "customer_demand_features" in datasets
    assert "inventory_features" in datasets
    assert "supplier_profitability_features" in datasets
    assert "flight_operations_features" in datasets
    assert "market_demand_features" in datasets
    assert "destination_demand_supply_features" in datasets

    # Verify rows > 0
    assert len(datasets["hotel_cancellation_features"]) == 119208
    assert len(datasets["flight_price_features"]) == 300153
    assert len(datasets["customer_demand_features"]) == 5000
    assert len(datasets["inventory_features"]) == 5000
    assert len(datasets["supplier_profitability_features"]) == 5000
    assert len(datasets["market_demand_features"]) == 5000
