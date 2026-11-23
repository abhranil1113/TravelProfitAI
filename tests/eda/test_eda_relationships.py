"""
Tests for Cross-Dataset Relationships Module
Verifies join cardinality validation and demand-supply gap calculations.
"""

import pytest
import pandas as pd
from eda.relationship_analysis import (
    validate_join_cardinality,
    analyze_demand_vs_supply,
    analyze_seasonality_vs_demand,
)


def test_validate_join_cardinality_unique():
    """Verify safe join cardinality when right key is unique."""
    left = pd.DataFrame({"dest_id": ["D1", "D2", "D3"]})
    right = pd.DataFrame({"dest_id": ["D1", "D2", "D3"], "name": ["Paris", "Tokyo", "London"]})
    val = validate_join_cardinality(left, right, "dest_id", "dest_id")
    assert val["cartesian_explosion_risk"] is False
    assert val["right_max_multiplicity"] == 1


def test_validate_join_cardinality_explosion_risk():
    """Verify detection of Cartesian risk when right key has duplicates."""
    left = pd.DataFrame({"dest_id": ["D1", "D2"]})
    right = pd.DataFrame({"dest_id": ["D1", "D1", "D1", "D2"], "offer": [1, 2, 3, 4]})
    val = validate_join_cardinality(left, right, "dest_id", "dest_id")
    assert val["cartesian_explosion_risk"] is True
    assert val["right_max_multiplicity"] == 3


def test_analyze_demand_vs_supply():
    """Verify calculation of demand-to-supply ratio by destination."""
    searches = pd.DataFrame({
        "search_id": ["s1", "s2", "s3"],
        "destination_id": ["D1", "D1", "D2"],
        "clicked": [1, 1, 0],
        "booking_completed": [1, 0, 0],
        "search_price": [5000, 6000, 4000],
    })
    inventory = pd.DataFrame({
        "inventory_id": ["inv1", "inv2"],
        "destination_id": ["D1", "D2"],
        "travel_date": ["2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-01"],
        "total_capacity": [50, 100],
        "booked_quantity": [10, 20],
        "available_quantity": [40, 80],
    })
    supplier = pd.DataFrame({
        "offer_id": ["o1", "o2"],
        "destination_id": ["D1", "D2"],
        "purchase_cost": [3000, 4000],
        "selling_price": [3500, 4500],
        "margin_percentage": [14.28, 11.11],
    })
    res = analyze_demand_vs_supply(searches, inventory, supplier)
    assert len(res) == 2
    assert "demand_to_supply_ratio" in res.columns
    assert "procurement_priority" in res.columns
    
    d1_row = res[res["destination_id"] == "D1"].iloc[0]
    assert d1_row["search_volume"] == 2
    assert d1_row["available_units"] == 40
    # ratio = 2 / (40 + 1) = 0.05
    assert d1_row["demand_to_supply_ratio"] == 0.05
