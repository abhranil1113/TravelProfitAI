"""
Tests for Core KPI Calculations Engine
Verifies safe division, hotel cancellation rates, search funnel, supplier margins, and inventory utilization.
"""

import pytest
import pandas as pd
import numpy as np
from eda.kpi_calculations import (
    safe_divide,
    compute_search_kpis,
    compute_inventory_kpis,
    compute_supplier_kpis,
    compute_hotel_kpis,
    compute_flight_operations_kpis,
    compute_flight_price_kpis,
)


def test_safe_divide():
    """Verify safe division with zero denominator, nan, and normal numbers."""
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(10, 0) == 0.0
    assert safe_divide(10, 0, default=99.0) == 99.0
    assert safe_divide(np.nan, 5) == 0.0
    assert safe_divide(10, np.nan) == 0.0


def test_compute_search_kpis():
    """Verify search conversion funnel KPIs."""
    searches_df = pd.DataFrame({
        "search_id": ["s1", "s2", "s3", "s4"],
        "destination_id": ["D1", "D1", "D2", "D2"],
        "clicked": [1, 1, 0, 0],
        "booking_completed": [1, 0, 0, 0],
        "search_price": [5000, 6000, 7000, 8000],
        "search_lead_days": [10, 20, 30, 40],
    })
    kpis = compute_search_kpis(searches_df)
    assert kpis["total_searches"] == 4
    assert kpis["total_clicks"] == 2
    assert kpis["total_bookings"] == 1
    assert kpis["search_to_click_pct"] == 50.0
    assert kpis["click_to_book_pct"] == 50.0
    assert kpis["search_to_book_pct"] == 25.0
    assert kpis["avg_search_price_inr"] == 6500.0


def test_compute_hotel_kpis():
    """Verify hotel KPIs (cancellation, ADR, RevPAR proxy)."""
    hotel_df = pd.DataFrame({
        "hotel": ["City Hotel", "Resort Hotel", "City Hotel", "Resort Hotel"],
        "is_canceled": [1, 0, 0, 0],
        "adr": [100.0, 150.0, 80.0, 120.0],
        "lead_time": [50, 20, 10, 5],
        "stays_in_weekend_nights": [1, 0, 1, 2],
        "stays_in_week_nights": [2, 3, 1, 2],
        "total_stay_nights": [3, 3, 2, 4],
        "is_repeated_guest": [0, 1, 0, 0],
        "market_segment": ["Online TA", "Direct", "Online TA", "Corporate"],
        "deposit_type": ["No Deposit", "No Deposit", "Non Refund", "No Deposit"],
    })
    kpis = compute_hotel_kpis(hotel_df)
    assert kpis["currency"] == "EUR"
    assert kpis["total_bookings"] == 4
    assert kpis["canceled_bookings"] == 1
    assert kpis["cancellation_rate_pct"] == 25.0
    assert kpis["avg_adr_eur"] == 112.5
    # RevPAR proxy = 112.5 * (1 - 0.25) = 84.38
    assert kpis["revpar_proxy_eur"] == 84.38
    assert kpis["repeat_guest_pct"] == 25.0


def test_compute_flight_price_kpis():
    """Verify flight price KPIs."""
    prices_df = pd.DataFrame({
        "class": ["Economy", "Economy", "Business", "Business"],
        "price": [5000, 7000, 25000, 35000],
        "stops": ["zero", "one", "zero", "one"],
        "days_left": [30, 20, 30, 20],
    })
    kpis = compute_flight_price_kpis(prices_df)
    assert kpis["currency"] == "INR"
    assert kpis["total_price_quotes"] == 4
    assert kpis["avg_price_inr"] == 18000.0
    assert kpis["business_to_economy_price_ratio"] == 5.0


def test_compute_supplier_kpis():
    """Verify supplier procurement and margin KPIs."""
    supplier_df = pd.DataFrame({
        "offer_id": ["o1", "o2"],
        "supplier_id": ["s1", "s2"],
        "purchase_cost": [1000.0, 2000.0],
        "selling_price": [1200.0, 1900.0],
        "unit_margin": [200.0, -100.0],
        "margin_percentage": [16.67, -5.26],
        "refundable": [1, 0],
    })
    kpis = compute_supplier_kpis(supplier_df)
    assert kpis["currency"] == "INR"
    assert kpis["total_offers"] == 2
    assert kpis["negative_margin_offers"] == 1
    assert kpis["negative_margin_pct"] == 50.0
    assert kpis["refundable_offers_pct"] == 50.0


def test_compute_inventory_kpis():
    """Verify inventory utilization KPIs with deduplication."""
    inv_df = pd.DataFrame({
        "inventory_id": ["inv1", "inv1", "inv2"],
        "travel_date": ["2026-06-01", "2026-06-01", "2026-06-01"],
        "snapshot_date": ["2026-05-01", "2026-05-15", "2026-05-15"],
        "inventory_type": ["hotel", "hotel", "flight"],
        "total_capacity": [100, 100, 50],
        "booked_quantity": [20, 60, 25],
        "available_quantity": [80, 40, 25],
        "sold_out": [0, 0, 0],
    })
    kpis = compute_inventory_kpis(inv_df, deduplicate_snapshots=True)
    # Deduplicated should have 2 unique items: inv1 (snapshot 2026-05-15: cap 100, booked 60) and inv2 (cap 50, booked 25)
    assert kpis["distinct_inventory_items"] == 2
    assert kpis["total_capacity"] == 150.0
    assert kpis["total_booked_units"] == 85.0
    assert kpis["total_available_units"] == 65.0
    assert kpis["overall_utilization_rate_pct"] == round((85.0 / 150.0) * 100, 2)
