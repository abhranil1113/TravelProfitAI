"""
Tests for Cross-Dataset Aggregation & Indicator Module
Validates unit segregation (ROOM_NIGHT vs SEAT) and heuristic pressure indices.
"""

import pytest
import pandas as pd
from feature_engineering.aggregation import (
    deduplicate_latest_inventory_snapshots,
    build_destination_demand_supply_indicators,
)


def test_deduplicate_latest_inventory_snapshots():
    inv_df = pd.DataFrame({
        "inventory_id": ["I1", "I1", "I2"],
        "travel_date": ["2026-06-01", "2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-15", "2026-05-10"],
        "available_quantity": [80, 50, 30],
    })
    dedup = deduplicate_latest_inventory_snapshots(inv_df)
    assert len(dedup) == 2
    i1 = dedup[dedup["inventory_id"] == "I1"].iloc[0]
    assert i1["snapshot_date"] == "2026-05-15"
    assert i1["available_quantity"] == 50


def test_build_destination_demand_supply_indicators():
    searches = pd.DataFrame({
        "search_id": ["s1", "s2"],
        "destination_id": ["GOA", "GOA"],
        "travellers_count": [2, 2],
        "search_price": [5000.0, 6000.0],
    })
    inventory = pd.DataFrame({
        "inventory_id": ["inv1"],
        "destination_id": ["GOA"],
        "travel_date": ["2026-06-01"],
        "snapshot_date": ["2026-05-01"],
        "total_capacity": [50],
        "booked_quantity": [10],
        "available_quantity": [40],
    })
    supplier = pd.DataFrame({
        "offer_id": ["o1"],
        "destination_id": ["GOA"],
        "purchase_cost": [3000.0],
        "selling_price": [3600.0],
        "margin_percentage": [16.67],
    })

    res = build_destination_demand_supply_indicators(searches, inventory, supplier)
    assert len(res) == 1
    row = res.iloc[0]
    assert row["destination_id"] == "GOA"
    assert row["search_volume"] == 2
    assert row["available_units"] == 40
    # ratio = 2 / (40 + 1) = 0.05
    assert row["demand_to_supply_ratio"] == 0.05
    assert "procurement_candidate_score" in res.columns


def test_build_destination_demand_supply_indicators_unit_segregation():
    # Tests that hotel room-nights and flight seats are kept strictly segregated
    searches = pd.DataFrame({
        "search_id": ["s_h1", "s_h2", "s_f1"],
        "destination_id": ["GOA", "GOA", "GOA"],
        "inventory_type": ["HOTEL", "HOTEL", "FLIGHT"],
        "travellers_count": [2, 1, 1],
        "search_price": [4500.0, 5200.0, 6000.0],
    })
    inventory = pd.DataFrame({
        "inventory_id": ["inv_h1", "inv_f1"],
        "destination_id": ["GOA", "GOA"],
        "inventory_type": ["HOTEL", "FLIGHT"],
        "unit_type": ["ROOM_NIGHT", "SEAT"],
        "travel_date": ["2026-07-01", "2026-07-01"],
        "snapshot_date": ["2026-06-15", "2026-06-15"],
        "total_capacity": [50, 180],
        "booked_quantity": [20, 100],
        "available_quantity": [30, 80],
    })
    supplier = pd.DataFrame({
        "offer_id": ["off_h1", "off_f1"],
        "destination_id": ["GOA", "GOA"],
        "inventory_type": ["HOTEL", "FLIGHT"],
        "purchase_cost": [3500.0, 4800.0],
        "selling_price": [4200.0, 5500.0],
        "margin_percentage": [16.67, 12.73],
    })

    res = build_destination_demand_supply_indicators(searches, inventory, supplier)

    # Must produce exactly 2 rows for GOA (1 for HOTEL, 1 for FLIGHT)
    assert len(res) == 2
    hotel_row = res[res["inventory_type"] == "HOTEL"].iloc[0]
    flight_row = res[res["inventory_type"] == "FLIGHT"].iloc[0]

    # Verify HOTEL units: search_vol=2, avail=30 room nights -> ratio = 2 / 31 = 0.06
    assert hotel_row["unit_type"] == "ROOM_NIGHT"
    assert hotel_row["search_volume"] == 2
    assert hotel_row["available_units"] == 30
    assert hotel_row["demand_to_supply_ratio"] == 0.06

    # Verify FLIGHT units: search_vol=1, avail=80 seats -> ratio = 1 / 81 = 0.01
    assert flight_row["unit_type"] == "SEAT"
    assert flight_row["search_volume"] == 1
    assert flight_row["available_units"] == 80
    assert flight_row["demand_to_supply_ratio"] == 0.01

    assert "procurement_candidate_score" in res.columns
    assert "inventory_pressure_category" in res.columns
