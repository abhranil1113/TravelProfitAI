"""
Tests for Currency Safety Module
Verifies strict isolation between EUR and INR and prevention of illegal cross-currency operations.
"""

import pytest
from eda.config import CurrencyMismatchError, CURRENCY_MAP
from eda.relationship_analysis import enforce_currency_safety


def test_currency_map_assignments():
    """Verify standard currency assignments per dataset."""
    assert CURRENCY_MAP["hotel_bookings"] == "EUR"
    assert CURRENCY_MAP["flight_prices"] == "INR"
    assert CURRENCY_MAP["supplier_offers"] == "INR"
    assert CURRENCY_MAP["customer_search_events"] == "INR"
    assert CURRENCY_MAP["flights"] == "OPERATIONAL"


def test_enforce_currency_safety_raises_on_eur_and_inr():
    """Verify that combining EUR and INR without exchange rate raises CurrencyMismatchError."""
    with pytest.raises(CurrencyMismatchError, match="Illegal cross-currency operation"):
        enforce_currency_safety("hotel_bookings", "flight_prices", operation="combine_margins")


def test_enforce_currency_safety_allows_with_explicit_rate():
    """Verify that explicit exchange rate allows cross-currency operation."""
    # Should not raise exception
    enforce_currency_safety(
        "hotel_bookings",
        "flight_prices",
        operation="convert_and_sum",
        exchange_rate=90.0,
    )


def test_enforce_currency_safety_allows_same_currency():
    """Verify that operations within same currency (INR vs INR) are allowed."""
    # Should not raise exception
    enforce_currency_safety("flight_prices", "supplier_offers", operation="compare_prices")
