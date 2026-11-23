"""
Tests for Flight Pricing & Operational Feature Engineering Modules
"""

import pytest
import pandas as pd
from feature_engineering.flight_features import (
    FlightPriceFeatureTransformer,
    FlightOperationsFeatureTransformer,
)


def test_flight_price_transformer():
    test_prices = pd.DataFrame({
        "airline": ["Vistara", "AirAsia"],
        "flight": ["UK-800", "I5-500"],
        "source_city": ["Delhi", "Mumbai"],
        "departure_time": ["Evening", "Morning"],
        "stops": ["zero", "one"],
        "arrival_time": ["Night", "Afternoon"],
        "destination_city": ["Mumbai", "Bangalore"],
        "class": ["Business", "Economy"],
        "duration": [2.25, 6.5],
        "days_left": [2, 35],
        "price": [28500.0, 4200.0],
        "stops_count": [0, 1],
        "route": ["Delhi-Mumbai", "Mumbai-Bangalore"],
    })

    transformer = FlightPriceFeatureTransformer()
    feats = transformer.transform(test_prices)

    assert len(feats) == 2
    assert "days_left_bucket" in feats.columns
    assert "duration_bucket" in feats.columns
    assert "is_business_class" in feats.columns
    assert "is_direct_flight" in feats.columns
    assert "is_immediate_departure" in feats.columns

    # Row 0: Business, 2 days left (immediate departure), direct flight
    assert feats.loc[0, "is_business_class"] == True
    assert feats.loc[0, "is_immediate_departure"] == True
    assert feats.loc[0, "is_direct_flight"] == True
    assert feats.loc[0, "days_left_bucket"] == "1-3d"
    assert feats.loc[0, "duration_bucket"] == "Short_Haul"


def test_flight_operations_transformer():
    test_ops = pd.DataFrame({
        "YEAR": [2015],
        "MONTH": [1],
        "DAY": [1],
        "DAY_OF_WEEK": [4],
        "AIRLINE": ["DL"],
        "FLIGHT_NUMBER": ["100"],
        "ORIGIN_AIRPORT": ["ATL"],
        "DESTINATION_AIRPORT": ["LAX"],
        "SCHEDULED_DEPARTURE": [1030],
        "SCHEDULED_ARRIVAL": [1315],
        "SCHEDULED_TIME": [285],
        "DISTANCE": [1946],
        "DEPARTURE_DELAY": [5.0],
        "ARRIVAL_DELAY": [8.0],
        "CANCELLED": [0],
        "DIVERTED": [0],
        "ROUTE": ["ATL-LAX"],
    })

    transformer = FlightOperationsFeatureTransformer()
    feats = transformer.transform(test_ops)

    assert len(feats) == 1
    assert feats.loc[0, "scheduled_departure_hour"] == 10
    assert feats.loc[0, "scheduled_departure_minute"] == 30
    assert feats.loc[0, "is_ontime_arrival"] == 1
