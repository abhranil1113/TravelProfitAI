"""
Tests for Temporal Consistency & Chronological Splitting Module
Validates arrival-date cohorts, booking-date stream splits, and scenario horizon splits.
"""

import pytest
import pandas as pd
from feature_engineering.split_manager import generate_chronological_splits


def test_chronological_splits_hotel_arrival_and_booking_date():
    hdf = pd.DataFrame({
        "arrival_date": ["2015-08-01", "2016-10-15", "2017-02-10", "2017-06-20"],
        "booking_date": ["2015-06-01", "2016-09-01", "2016-12-15", "2017-04-10"],
        "is_canceled": [0, 1, 0, 1],
    })
    feature_datasets = {"hotel_cancellation_features": hdf}
    manifest = generate_chronological_splits(feature_datasets)

    hotel_split = manifest["datasets"]["hotel_cancellation_features"]
    # Arrival date split
    assert hotel_split["train"]["records"] == 2  # 2015 and 2016
    assert hotel_split["validation"]["records"] == 1  # 2017-02-10
    assert hotel_split["test"]["records"] == 1  # 2017-06-20
    assert hotel_split["split_key"] == "arrival_date"

    # Booking date chronological stream split
    assert "booking_date_chronological_split" in hotel_split
    b_split = hotel_split["booking_date_chronological_split"]
    assert b_split["split_key"] == "booking_date"
    assert b_split["train"]["records"] == 2  # 2015-06-01, 2016-09-01 (<= 2016-11-06)
    assert b_split["validation"]["records"] == 1  # 2016-12-15 (between 2016-11-07 and 2017-02-03)
    assert b_split["test"]["records"] == 1  # 2017-04-10 (>= 2017-02-04)


def test_scenario_horizon_split_flight_price():
    fpdf = pd.DataFrame({
        "days_left": [30, 20, 10, 3],
        "price": [5000, 6000, 9000, 15000],
    })
    feature_datasets = {"flight_price_features": fpdf}
    manifest = generate_chronological_splits(feature_datasets)

    flight_split = manifest["datasets"]["flight_price_features"]
    assert flight_split["train"]["records"] == 2  # 30, 20 (>= 15)
    assert flight_split["validation"]["records"] == 1  # 10 (8-14)
    assert flight_split["test"]["records"] == 1  # 3 (1-7)
    assert "Scenario-Based Horizon Split" in flight_split["split_type"]
    assert flight_split["calendar_timestamps_present"] == False
