"""
Tests for Customer Search Feature Engineering Module
"""

import pytest
import pandas as pd
from feature_engineering.search_features import CustomerSearchFeatureTransformer


def test_customer_search_transformer():
    test_searches = pd.DataFrame({
        "search_id": ["S1", "S2"],
        "user_id": ["U10", "U20"],
        "search_date": ["2026-05-01", "2026-06-01"],
        "travel_date": ["2026-05-10", "2026-08-01"],
        "destination_id": ["GOA", "DEL"],
        "origin_id": ["BOM", "BOM"],
        "inventory_type": ["hotel", "flight"],
        "travellers_count": [4, 1],
        "rooms_count": [2, 1],
        "search_price": [12000.0, 4500.0],
        "clicked": [True, False],
        "booking_completed": [True, False],
        "search_lead_days": [9, 61],
    })

    transformer = CustomerSearchFeatureTransformer()
    feats = transformer.transform(test_searches)

    assert len(feats) == 2
    assert "search_lead_bucket" in feats.columns
    assert "travellers_per_room" in feats.columns
    assert "search_price_per_traveller_inr" in feats.columns
    assert "has_funnel_anomaly" in feats.columns

    # S1: 4 travellers, 2 rooms -> 2.0 per room, 12000 / 4 = 3000 per traveller
    assert feats.loc[0, "travellers_per_room"] == 2.0
    assert feats.loc[0, "search_price_per_traveller_inr"] == 3000.0
    assert feats.loc[0, "is_group_search"] == True
    assert feats.loc[0, "has_funnel_anomaly"] == False


def test_funnel_anomaly_flag():
    # Anomaly case: booking_completed=True but clicked=False
    anomaly_df = pd.DataFrame({
        "search_id": ["S99"],
        "user_id": ["U99"],
        "search_date": ["2026-05-01"],
        "travel_date": ["2026-05-10"],
        "destination_id": ["GOA"],
        "origin_id": ["BOM"],
        "inventory_type": ["hotel"],
        "travellers_count": [2],
        "rooms_count": [1],
        "search_price": [5000.0],
        "clicked": [False],
        "booking_completed": [True],
        "search_lead_days": [9],
    })
    transformer = CustomerSearchFeatureTransformer()
    feats = transformer.transform(anomaly_df)
    assert feats.loc[0, "has_funnel_anomaly"] == True
