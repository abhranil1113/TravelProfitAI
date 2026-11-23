"""
Tests for Data Leakage Safety Module
Verifies isolation of post-event fields from candidate predictive models.
"""

import pytest
from eda.config import LEAKAGE_BOUNDARIES, CANDIDATE_MODELS


def test_leakage_boundaries_defined():
    """Verify all critical domains have defined leakage boundaries."""
    assert "hotel_bookings" in LEAKAGE_BOUNDARIES
    assert "flight_prices" in LEAKAGE_BOUNDARIES
    assert "flights" in LEAKAGE_BOUNDARIES
    assert "customer_search_events" in LEAKAGE_BOUNDARIES


def test_hotel_leakage_isolation():
    """Verify reservation_status is quarantined as post-event leakage."""
    hotel_boundary = LEAKAGE_BOUNDARIES["hotel_bookings"]
    leakage = hotel_boundary["post_event_leakage_features"]
    allowed = hotel_boundary["allowed_pre_booking_features"]

    assert "reservation_status" in leakage
    assert "reservation_status_date" in leakage
    assert "reservation_status" not in allowed
    assert "lead_time" in allowed
    assert "market_segment" in allowed


def test_search_leakage_isolation():
    """Verify search outcomes are quarantined from search volume models."""
    search_boundary = LEAKAGE_BOUNDARIES["customer_search_events"]
    leakage = search_boundary["post_event_leakage_features"]
    allowed = search_boundary["allowed_search_features"]

    assert "booking_completed" in leakage
    assert "booking_completed" not in allowed
    assert "search_lead_days" in allowed


def test_candidate_models_structure():
    """Verify candidate models metadata contains 5 distinct models."""
    assert len(CANDIDATE_MODELS) == 5
    model_ids = [m["id"] for m in CANDIDATE_MODELS]
    assert "model_1_hotel_cancellation" in model_ids
    assert "model_2_flight_price" in model_ids
    assert "model_3_search_demand" in model_ids
    assert "model_4_inventory_depletion" in model_ids
    assert "model_5_supplier_competitiveness" in model_ids
