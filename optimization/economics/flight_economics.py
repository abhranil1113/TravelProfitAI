"""
optimization/economics/flight_economics.py

Flight procurement economics without double-counting acquisition costs.
Evaluates 0% and 10% salvage scenarios, break-even sell-through, and price elasticity.
"""

from typing import Dict, Any
from optimization.config import FinancialAssumptions


class FlightEconomicsCalculator:
    """Calculates expected net contribution per flight seat under audited terms."""

    def __init__(self, assumptions: FinancialAssumptions, use_optional_salvage: bool = False):
        self.assumptions = assumptions
        self.salvage_rate = (self.assumptions.flight_salvage_rate_optional
                             if use_optional_salvage else self.assumptions.flight_salvage_rate_default)
        self.penalty = self.assumptions.flight_unsold_penalty

    def calculate_adjusted_sell_through(self,
                                        contract_price: float,
                                        market_ceiling_price: float) -> float:
        """
        Adjusts baseline sell-through probability using price elasticity if contract price
        exceeds consumer market ceiling price.
        """
        p = float(contract_price)
        p_ml = float(market_ceiling_price)
        theta_0 = self.assumptions.flight_base_sell_through
        eta = self.assumptions.flight_price_elasticity

        if p <= 0 or p_ml <= 0:
            return theta_0

        if p > p_ml:
            ratio = p_ml / p
            theta_adj = theta_0 * (ratio ** eta)
        else:
            theta_adj = theta_0

        return max(self.assumptions.flight_min_sell_through, min(self.assumptions.flight_max_sell_through, theta_adj))

    def calculate_expected_contribution(self,
                                        purchase_cost: float,
                                        contract_selling_price: float,
                                        sell_through: float) -> Dict[str, float]:
        """
        Calculates expected net contribution per seat.
        e_F = theta * p + (1 - theta) * s * c - c - (1 - theta) * psi
        """
        c = float(purchase_cost)
        p = float(contract_selling_price)
        theta = float(sell_through)
        s = self.salvage_rate
        psi = self.penalty

        expected_gross_revenue = theta * p + (1.0 - theta) * s * c
        expected_penalty = (1.0 - theta) * psi
        expected_net_contribution = expected_gross_revenue - c - expected_penalty

        return {
            "expected_net_contribution": expected_net_contribution,
            "expected_gross_revenue": expected_gross_revenue,
            "purchase_cost": c,
            "contract_selling_price": p,
            "sell_through": theta,
            "salvage_rate": s,
            "penalty": psi,
        }

    def calculate_breakeven_sell_through(self, purchase_cost: float, contract_selling_price: float) -> float:
        """Calculates theta* where expected net contribution equals zero."""
        c = float(purchase_cost)
        p = float(contract_selling_price)
        s = self.salvage_rate
        psi = self.penalty

        numerator = c * (1.0 - s) + psi
        denominator = p - s * c + psi
        if denominator <= 0:
            return 1.0
        return max(0.0, min(1.0, numerator / denominator))
