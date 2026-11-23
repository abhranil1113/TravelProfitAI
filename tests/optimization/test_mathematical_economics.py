"""
tests/optimization/test_mathematical_economics.py

Mathematical verification tests for Stage 1.3 audited economic formulation models.
Validates:
1. Hotel 4-outcome state space partitions and probability summation to 1.0.
2. Hotel expected contribution under customer refund, cancellation fee, and room resale scenarios.
3. Flight 0% baseline spoilage vs 10% contractual salvage equations.
4. Flight break-even sell-through analytical threshold.
5. Elasticity-based sell-through adjustments.
"""

import pytest
from optimization.config import FinancialAssumptions
from optimization.economics.hotel_economics import HotelEconomicsCalculator
from optimization.economics.flight_economics import FlightEconomicsCalculator


class TestHotelEconomics:
    """Verifies hotel 4-outcome scenario economics."""

    def test_hotel_probabilities_sum_to_one(self):
        """Probability of all mutually exclusive hotel outcomes must sum identically to 1.0."""
        assumptions = FinancialAssumptions()
        calc = HotelEconomicsCalculator(assumptions)

        for theta in [0.0, 0.25, 0.50, 0.85, 1.0]:
            for p_c in [0.0, 0.15, 0.30, 0.60, 1.0]:
                res = calc.calculate_expected_contribution(
                    purchase_cost=4000.0,
                    selling_price=5000.0,
                    cancellation_prob=p_c,
                    is_supplier_refundable=True,
                    sell_through_prob=theta
                )
                prob_sum = (
                    res["p_unsold"] +
                    res["p_completed"] +
                    res["p_cancelled_resold"] +
                    res["p_cancelled_unresold"]
                )
                assert pytest.approx(prob_sum, abs=1e-9) == 1.0

    def test_hotel_expected_contribution_manual_benchmark(self):
        """
        Deterministic hand calculation:
        c = 4000, p = 5000, theta = 0.85, p_c = 0.20, refundable = True
        Assumptions: r_cust = 0.80, f = 0.40, delta = 0.90, r_supp_c = 0.85, r_supp_u = 0.0
        Probabilities:
          Unsold: 1 - 0.85 = 0.15
          Completed: 0.85 * (1 - 0.20) = 0.68
          Cancelled & Resold: 0.85 * 0.20 * 0.40 = 0.068
          Cancelled & Unresold: 0.85 * 0.20 * 0.60 = 0.102
        Inflows:
          Unsold: 0 * 4000 = 0
          Completed: 5000
          Cancelled & Resold: (1 - 0.80)*5000 + 0.90*5000 = 1000 + 4500 = 5500
          Cancelled & Unresold: (1 - 0.80)*5000 + 0.85*4000 = 1000 + 3400 = 4400
        Gross Inflows:
          0.15 * 0 + 0.68 * 5000 + 0.068 * 5500 + 0.102 * 4400
          = 0 + 3400 + 374 + 448.8 = 4222.80
        Net Contribution = 4222.80 - 4000 = +222.80
        """
        assumptions = FinancialAssumptions()
        calc = HotelEconomicsCalculator(assumptions)
        res = calc.calculate_expected_contribution(
            purchase_cost=4000.0,
            selling_price=5000.0,
            cancellation_prob=0.20,
            is_supplier_refundable=True,
            sell_through_prob=0.85
        )
        assert pytest.approx(res["expected_gross_revenue"], abs=1e-4) == 4222.80
        assert pytest.approx(res["expected_net_contribution"], abs=1e-4) == 222.80

    def test_hotel_non_refundable_supplier(self):
        """When supplier contract is non-refundable, r_supp_cancel is zero."""
        assumptions = FinancialAssumptions()
        calc = HotelEconomicsCalculator(assumptions)
        res_ref = calc.calculate_expected_contribution(
            purchase_cost=4000.0,
            selling_price=5000.0,
            cancellation_prob=0.20,
            is_supplier_refundable=True,
            sell_through_prob=0.85
        )
        res_nonref = calc.calculate_expected_contribution(
            purchase_cost=4000.0,
            selling_price=5000.0,
            cancellation_prob=0.20,
            is_supplier_refundable=False,
            sell_through_prob=0.85
        )
        # Non-refundable must be strictly lower contribution
        assert res_nonref["expected_net_contribution"] < res_ref["expected_net_contribution"]
        diff = res_ref["expected_net_contribution"] - res_nonref["expected_net_contribution"]
        # Expected supplier refund: p_s3b * r_supp_cancel * c = 0.102 * 0.85 * 4000 = 346.80
        assert pytest.approx(diff, abs=1e-4) == 346.80


class TestFlightEconomics:
    """Verifies flight spoilage, salvage, and break-even models."""

    def test_flight_baseline_0pct_salvage(self):
        """
        c = 4200, p = 5500, theta = 0.85, s = 0.0, psi = 0.0
        e_F = 0.85 * 5500 + 0.15 * 0 - 4200 - 0 = 4675 - 4200 = +475.0
        """
        assumptions = FinancialAssumptions()
        calc = FlightEconomicsCalculator(assumptions, use_optional_salvage=False)
        res = calc.calculate_expected_contribution(
            purchase_cost=4200.0,
            contract_selling_price=5500.0,
            sell_through=0.85
        )
        assert pytest.approx(res["expected_net_contribution"], abs=1e-4) == 475.0

    def test_flight_optional_10pct_salvage(self):
        """
        c = 4200, p = 5500, theta = 0.85, s = 0.10, psi = 0.0
        e_F = 0.85 * 5500 + 0.15 * (0.10 * 4200) - 4200 = 4675 + 63.0 - 4200 = +538.0
        """
        assumptions = FinancialAssumptions()
        calc = FlightEconomicsCalculator(assumptions, use_optional_salvage=True)
        res = calc.calculate_expected_contribution(
            purchase_cost=4200.0,
            contract_selling_price=5500.0,
            sell_through=0.85
        )
        assert pytest.approx(res["expected_net_contribution"], abs=1e-4) == 538.0

    def test_flight_breakeven_threshold(self):
        """
        At break-even theta*, expected net contribution must equal exactly 0.0.
        """
        assumptions = FinancialAssumptions()
        for use_opt in [False, True]:
            calc = FlightEconomicsCalculator(assumptions, use_optional_salvage=use_opt)
            theta_star = calc.calculate_breakeven_sell_through(
                purchase_cost=4200.0,
                contract_selling_price=5500.0
            )
            res = calc.calculate_expected_contribution(
                purchase_cost=4200.0,
                contract_selling_price=5500.0,
                sell_through=theta_star
            )
            assert pytest.approx(res["expected_net_contribution"], abs=1e-4) == 0.0

    def test_price_elasticity_adjustment(self):
        """If contract price exceeds consumer market ceiling, sell-through must drop."""
        assumptions = FinancialAssumptions()
        calc = FlightEconomicsCalculator(assumptions)
        theta_base = assumptions.flight_base_sell_through

        # Price equals or below market ceiling -> unchanged
        theta_eq = calc.calculate_adjusted_sell_through(5000.0, 5000.0)
        assert theta_eq == theta_base

        # Price exceeds market ceiling -> drops
        theta_high = calc.calculate_adjusted_sell_through(6000.0, 5000.0)
        assert theta_high < theta_base
