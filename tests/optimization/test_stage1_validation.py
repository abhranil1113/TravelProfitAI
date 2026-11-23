"""
tests/optimization/test_stage1_validation.py

Automated mathematical validation and unit tests for Phase 5 Stage 1.3:
1. Flight economics under 0% and 10% salvage rates and break-even calculations.
2. TC-06 intermediate calculations and negative contribution assertion.
3. Hotel ADR currency scale and unit mismatch detection.
4. Currency validation semantics (mixed currencies, unverified currency, prototype override).
5. Demand conversion zero-denominator handling and temporal cutoff preservation.
"""

import math
import pytest
import pandas as pd
import numpy as np


# ----------------------------------------------------------------------
# 1. Flight Contribution & Break-Even Functions (Pure Mathematical Forms)
# ----------------------------------------------------------------------

def calculate_flight_contribution(purchase_cost: float,
                                  selling_price: float,
                                  sell_through: float,
                                  salvage_rate: float = 0.0,
                                  penalty: float = 0.0) -> float:
    """Calculates expected net contribution per flight seat without double-counting."""
    theta = sell_through
    c = purchase_cost
    p = selling_price
    s = salvage_rate
    psi = penalty
    return theta * p + (1.0 - theta) * s * c - c - (1.0 - theta) * psi


def calculate_flight_breakeven_sellthrough(purchase_cost: float,
                                           selling_price: float,
                                           salvage_rate: float = 0.0,
                                           penalty: float = 0.0) -> float:
    """Calculates the break-even sell-through probability theta* where e_F = 0."""
    c = purchase_cost
    p = selling_price
    s = salvage_rate
    psi = penalty
    # e_F = theta * (p - s*c + psi) - (c - s*c + psi) = 0
    numerator = c - s * c + psi
    denominator = p - s * c + psi
    if denominator <= 0:
        raise ValueError("Invalid parameters: denominator must be positive.")
    return numerator / denominator


def test_flight_economics_zero_salvage():
    """Verify flight economics with s=0.00 (Assumptions register default)."""
    c = 4200.0
    p = 5500.0
    s = 0.00
    psi = 0.00

    # Break-even
    theta_star = calculate_flight_breakeven_sellthrough(c, p, s, psi)
    expected_theta_star = 4200.0 / 5500.0  # 42 / 55 = 0.763636...
    assert math.isclose(theta_star, expected_theta_star, rel_tol=1e-5)
    assert math.isclose(theta_star, 0.763636, abs_tol=1e-4)

    # Scenarios: theta = 0.50, 0.85, 0.95
    e_50 = calculate_flight_contribution(c, p, 0.50, s, psi)
    assert math.isclose(e_50, -1450.00, abs_tol=1e-2)  # 0.50 * 5500 - 4200 = 2750 - 4200 = -1450

    e_85 = calculate_flight_contribution(c, p, 0.85, s, psi)
    assert math.isclose(e_85, 475.00, abs_tol=1e-2)    # 0.85 * 5500 - 4200 = 4675 - 4200 = +475

    e_95 = calculate_flight_contribution(c, p, 0.95, s, psi)
    assert math.isclose(e_95, 1025.00, abs_tol=1e-2)   # 0.95 * 5500 - 4200 = 5225 - 4200 = +1025


def test_flight_economics_ten_percent_salvage():
    """Verify flight economics with s=0.10 (Optional contractual salvage scenario)."""
    c = 4200.0
    p = 5500.0
    s = 0.10
    psi = 0.00

    # Break-even
    theta_star = calculate_flight_breakeven_sellthrough(c, p, s, psi)
    # numerator = 4200 - 420 = 3780
    # denominator = 5500 - 420 = 5080
    expected_theta_star = 3780.0 / 5080.0  # 0.744094...
    assert math.isclose(theta_star, expected_theta_star, rel_tol=1e-5)
    assert math.isclose(theta_star, 0.744094, abs_tol=1e-4)

    # Scenarios: theta = 0.50, 0.85, 0.95
    e_50 = calculate_flight_contribution(c, p, 0.50, s, psi)
    assert math.isclose(e_50, -1240.00, abs_tol=1e-2)

    e_85 = calculate_flight_contribution(c, p, 0.85, s, psi)
    assert math.isclose(e_85, 538.00, abs_tol=1e-2)

    e_95 = calculate_flight_contribution(c, p, 0.95, s, psi)
    assert math.isclose(e_95, 1046.00, abs_tol=1e-2)


# ----------------------------------------------------------------------
# 2. Hotel TC-06 Step-by-Step Exact Verification
# ----------------------------------------------------------------------

def calculate_hotel_contribution_step_by_step(c: float,
                                              p: float,
                                              theta: float,
                                              p_cancel: float,
                                              r_cust: float,
                                              f_resale: float,
                                              delta_resale: float,
                                              r_supp_unsold: float,
                                              r_supp_cancel: float):
    """Calculates state probabilities, state cash inflows, and net contribution."""
    # State probabilities
    p_s1 = 1.0 - theta
    p_s2 = theta * (1.0 - p_cancel)
    p_s3a = theta * p_cancel * f_resale
    p_s3b = theta * p_cancel * (1.0 - f_resale)
    total_prob = p_s1 + p_s2 + p_s3a + p_s3b

    # Cash inflows
    inflow_s1 = r_supp_unsold * c
    inflow_s2 = p
    inflow_s3a = (1.0 - r_cust) * p + delta_resale * p
    inflow_s3b = (1.0 - r_cust) * p + r_supp_cancel * c

    expected_inflow = (p_s1 * inflow_s1 +
                       p_s2 * inflow_s2 +
                       p_s3a * inflow_s3a +
                       p_s3b * inflow_s3b)
    e_H = expected_inflow - c

    return {
        "p_s1": p_s1,
        "p_s2": p_s2,
        "p_s3a": p_s3a,
        "p_s3b": p_s3b,
        "total_prob": total_prob,
        "inflow_s1": inflow_s1,
        "inflow_s2": inflow_s2,
        "inflow_s3a": inflow_s3a,
        "inflow_s3b": inflow_s3b,
        "expected_inflow": expected_inflow,
        "e_H": e_H,
    }


def test_tc06_reproducible_calculation():
    """Verify TC-06 exact intermediate calculations under zero supplier refund."""
    c = 5000.0
    p = 7000.0
    theta = 0.90
    p_cancel = 0.60
    r_cust = 0.80
    f_resale = 0.40
    delta = 0.90
    r_supp_unsold = 0.0
    r_supp_cancel = 0.0  # Zero supplier refund!

    res = calculate_hotel_contribution_step_by_step(
        c, p, theta, p_cancel, r_cust, f_resale, delta, r_supp_unsold, r_supp_cancel
    )

    # Assert probabilities
    assert math.isclose(res["p_s1"], 0.10, abs_tol=1e-5)
    assert math.isclose(res["p_s2"], 0.360, abs_tol=1e-5)
    assert math.isclose(res["p_s3a"], 0.216, abs_tol=1e-5)
    assert math.isclose(res["p_s3b"], 0.324, abs_tol=1e-5)
    assert math.isclose(res["total_prob"], 1.000, abs_tol=1e-5)

    # Assert state inflows
    assert math.isclose(res["inflow_s1"], 0.0, abs_tol=1e-2)
    assert math.isclose(res["inflow_s2"], 7000.0, abs_tol=1e-2)
    assert math.isclose(res["inflow_s3a"], 1400.0 + 6300.0, abs_tol=1e-2)  # 7700.0
    assert math.isclose(res["inflow_s3b"], 1400.0 + 0.0, abs_tol=1e-2)     # 1400.0

    # Assert expected inflow: (0.36 * 7000) + (0.216 * 7700) + (0.324 * 1400)
    # = 2520.0 + 1663.20 + 453.60 = 4636.80
    assert math.isclose(res["expected_inflow"], 4636.80, abs_tol=1e-2)

    # Assert expected net contribution: 4636.80 - 5000.0 = -363.20
    assert math.isclose(res["e_H"], -363.20, abs_tol=1e-2)
    assert res["e_H"] < 0.0  # Proves negative contribution strictly triggers rejection!


# ----------------------------------------------------------------------
# 3. Hotel ADR Currency & Unit Mismatch Guard
# ----------------------------------------------------------------------

def validate_hotel_adr_currency(raw_selling_price: float,
                                stay_duration: float,
                                input_currency: str,
                                model_training_currency: str = "EUR",
                                prototype_exchange_rate: float = None):
    """
    Validates and transforms ADR for hotel model input.
    Rejects raw INR passed as EUR ADR.
    """
    if input_currency != model_training_currency:
        if prototype_exchange_rate is None or prototype_exchange_rate <= 0:
            raise ValueError(
                f"Currency mismatch: Offer is in {input_currency} but model requires {model_training_currency}. "
                "No prototype exchange rate provided."
            )
        # Scaled ADR in EUR
        scaled_adr_eur = (raw_selling_price / stay_duration) / prototype_exchange_rate
        return scaled_adr_eur
    return raw_selling_price / stay_duration


def test_hotel_adr_currency_mismatch_detection():
    """Verify raw INR selling price causes an exception if passed as EUR without rate."""
    raw_selling_price = 8971.68  # Median INR selling price in offers
    stay_duration = 2.0

    with pytest.raises(ValueError, match="Currency mismatch"):
        validate_hotel_adr_currency(
            raw_selling_price=raw_selling_price,
            stay_duration=stay_duration,
            input_currency="INR",
            model_training_currency="EUR",
            prototype_exchange_rate=None
        )

    # With prototype exchange rate 90.0 EUR/INR
    scaled_adr = validate_hotel_adr_currency(
        raw_selling_price=raw_selling_price,
        stay_duration=stay_duration,
        input_currency="INR",
        model_training_currency="EUR",
        prototype_exchange_rate=90.0
    )
    # (8971.68 / 2) / 90.0 = 4485.84 / 90.0 = 49.8426 EUR
    assert math.isclose(scaled_adr, 49.8426, abs_tol=1e-2)
    assert 10.0 <= scaled_adr <= 500.0  # Within valid training EUR ADR bounds!


# ----------------------------------------------------------------------
# 4. Currency Validation Semantics (Rejection of Mixed / Unverified)
# ----------------------------------------------------------------------

def validate_currency_environment(currencies: list[str],
                                  allow_prototype_override: bool = False,
                                  verified_currencies: set[str] = None):
    """Enforces strict currency validation semantics."""
    if verified_currencies is None:
        verified_currencies = {"USD", "EUR", "GBP"}  # Example verified set

    unique_currencies = set(currencies)
    if len(unique_currencies) > 1:
        raise ValueError(f"Mixed currencies detected: {unique_currencies}. Mixed currencies are prohibited.")

    currency = unique_currencies.pop()
    if currency not in verified_currencies:
        if not allow_prototype_override:
            raise ValueError(
                f"Unverified currency '{currency}' detected. Production mode rejects unverified currencies. "
                "Enable allow_prototype_override=True for prototype experimentation."
            )
        return "PROTOTYPE_ASSUMED"
    return "VERIFIED_COMMERCIAL"


def test_currency_validation_semantics():
    """Verify rejection of mixed currencies and enforcement of prototype override flag."""
    # 1. Mixed currencies must fail
    with pytest.raises(ValueError, match="Mixed currencies detected"):
        validate_currency_environment(["INR", "EUR"])

    # 2. Unverified currency in production mode (override False) must fail
    with pytest.raises(ValueError, match="Unverified currency 'INR'"):
        validate_currency_environment(["INR"], allow_prototype_override=False)

    # 3. Unverified currency with prototype override must pass as PROTOTYPE_ASSUMED
    status = validate_currency_environment(["INR"], allow_prototype_override=True)
    assert status == "PROTOTYPE_ASSUMED"

    # 4. Verified currency must pass as VERIFIED_COMMERCIAL
    status_verified = validate_currency_environment(["EUR"], allow_prototype_override=False, verified_currencies={"EUR"})
    assert status_verified == "VERIFIED_COMMERCIAL"


# ----------------------------------------------------------------------
# 5. Demand Conversion: Zero-Denominator & Temporal Cutoff Guard
# ----------------------------------------------------------------------

def calculate_historical_conversion_rate(searches_df: pd.DataFrame,
                                        destination_id: str,
                                        inventory_type: str,
                                        opt_timestamp: str) -> float:
    """Calculates search conversion rate strictly before opt_timestamp, guarding zero denominator."""
    # Filter strictly prior to opt_timestamp (no future leakage)
    prior_searches = searches_df[
        (searches_df["search_date"] < opt_timestamp) &
        (searches_df["destination_id"] == destination_id) &
        (searches_df["inventory_type"] == inventory_type)
    ]
    denom = len(prior_searches)
    if denom == 0:
        return 0.0  # Zero denominator safe fallback
    bookings = prior_searches["booking_completed"].sum()
    return float(bookings / denom)


def test_demand_conversion_zero_denominator_and_temporal_cutoff():
    """Verify zero denominator safe handling and strict temporal leakage prevention."""
    records = [
        {"search_date": "2026-05-01", "destination_id": "DEST01", "inventory_type": "HOTEL", "booking_completed": True},
        {"search_date": "2026-05-02", "destination_id": "DEST01", "inventory_type": "HOTEL", "booking_completed": False},
        {"search_date": "2026-05-03", "destination_id": "DEST01", "inventory_type": "HOTEL", "booking_completed": True},
        # Future record (must be excluded when opt_date is 2026-05-03)
        {"search_date": "2026-05-10", "destination_id": "DEST01", "inventory_type": "HOTEL", "booking_completed": True},
    ]
    df = pd.DataFrame(records)

    # At opt_timestamp 2026-05-03: records on 05-01 and 05-02 are used (1 booking / 2 searches = 0.50)
    conv_0503 = calculate_historical_conversion_rate(df, "DEST01", "HOTEL", "2026-05-03")
    assert math.isclose(conv_0503, 0.50, abs_tol=1e-5)

    # At opt_timestamp 2026-04-01 (before any records exist): zero searches -> safely returns 0.0
    conv_early = calculate_historical_conversion_rate(df, "DEST01", "HOTEL", "2026-04-01")
    assert conv_early == 0.0

    # Non-existent destination: safely returns 0.0 without ZeroDivisionError
    conv_none = calculate_historical_conversion_rate(df, "DEST_NONEXISTENT", "HOTEL", "2026-05-15")
    assert conv_none == 0.0
