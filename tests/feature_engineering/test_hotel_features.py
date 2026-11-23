"""
Tests for Hotel Booking Feature Engineering Module
Validates booking_date calculation and pre-booking vs post-booking operational separation.
"""

import pytest
import pandas as pd
from feature_engineering.hotel_features import (
    HotelFeatureTransformer,
    PRE_BOOKING_FEATURE_COLUMNS,
    POST_BOOKING_OPERATIONAL_COLUMNS,
)


def test_hotel_feature_transformer():
    test_hotel = pd.DataFrame({
        "hotel": ["City Hotel", "Resort Hotel"],
        "is_canceled": [0, 1],
        "lead_time": [15, 120],
        "arrival_date": ["2016-07-15", "2016-08-20"],
        "stays_in_weekend_nights": [1, 2],
        "stays_in_week_nights": [3, 5],
        "adults": [2, 1],
        "children": [1, 0],
        "babies": [0, 0],
        "meal": ["BB", "HB"],
        "country": ["PRT", "ESP"],
        "market_segment": ["Online TA", "Direct"],
        "distribution_channel": ["TA/TO", "Direct"],
        "is_repeated_guest": [0, 1],
        "previous_cancellations": [0, 2],
        "previous_bookings_not_canceled": [0, 5],
        "reserved_room_type": ["A", "C"],
        "assigned_room_type": ["A", "D"],
        "booking_changes": [0, 1],
        "deposit_type": ["No Deposit", "Non Refund"],
        "customer_type": ["Transient", "Transient-Party"],
        "adr": [120.0, 95.0],
        "days_in_waiting_list": [0, 0],
        "required_car_parking_spaces": [1, 0],
        "total_of_special_requests": [2, 0],
        "agent": [9, 0],
        "company": [0, 0],
    })

    transformer = HotelFeatureTransformer()
    feats = transformer.transform(test_hotel)

    assert len(feats) == 2
    assert "lead_time_bucket" in feats.columns
    assert "total_stay_nights" in feats.columns
    assert "weekend_nights_ratio" in feats.columns
    assert "adr_per_guest" in feats.columns
    assert "room_type_changed" in feats.columns
    assert "booking_date" in feats.columns

    # Row 0 checks:
    # 2016-07-15 minus 15 days lead time = 2016-06-30
    assert feats.loc[0, "booking_date"] == "2016-06-30"
    assert feats.loc[0, "total_stay_nights"] == 4
    assert feats.loc[0, "weekend_nights_ratio"] == 0.25
    assert feats.loc[0, "total_guests"] == 3
    assert feats.loc[0, "adr_per_guest"] == 40.0
    assert feats.loc[0, "room_type_changed"] == False

    # Row 1 checks:
    # 2016-08-20 minus 120 days lead time = 2016-04-22
    assert feats.loc[1, "booking_date"] == "2016-04-22"
    assert feats.loc[1, "room_type_changed"] == True
    assert feats.loc[1, "has_cancellation_history"] == True


def test_hotel_pre_booking_feature_segregation():
    # Verify strict pre-booking feature boundary
    assert "reserved_room_type" in PRE_BOOKING_FEATURE_COLUMNS
    assert "assigned_room_type" not in PRE_BOOKING_FEATURE_COLUMNS
    assert "room_type_changed" not in PRE_BOOKING_FEATURE_COLUMNS
    assert "booking_changes" not in PRE_BOOKING_FEATURE_COLUMNS

    # Verify post-booking operational classification
    assert "assigned_room_type" in POST_BOOKING_OPERATIONAL_COLUMNS
    assert "room_type_changed" in POST_BOOKING_OPERATIONAL_COLUMNS
    assert "booking_changes" in POST_BOOKING_OPERATIONAL_COLUMNS
