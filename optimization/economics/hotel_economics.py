"""
optimization/economics/hotel_economics.py

Four-outcome scenario economics for hotel room-night procurement.
Partitions outcome space into Unsold, Completed, Cancelled & Resold, and Cancelled & Unresold.
"""

from typing import Dict, Any
from optimization.config import FinancialAssumptions


class HotelEconomicsCalculator:
    """Calculates expected net contribution per room-night under audited commercial terms."""

    def __init__(self, assumptions: FinancialAssumptions):
        self.assumptions = assumptions

    def calculate_expected_contribution(self,
                                        purchase_cost: float,
                                        selling_price: float,
                                        cancellation_prob: float,
                                        is_supplier_refundable: bool,
                                        sell_through_prob: float = None) -> Dict[str, float]:
        """
        Calculates expected net contribution and state breakdown for a hotel room-night offer.
        """
        c = float(purchase_cost)
        p = float(selling_price)
        theta = max(0.0, min(1.0, float(sell_through_prob if sell_through_prob is not None else self.assumptions.hotel_base_sell_through)))
        p_c = max(0.0, min(1.0, float(cancellation_prob)))

        r_cust = self.assumptions.hotel_customer_refund_rate
        f_resale = self.assumptions.hotel_room_resale_probability
        delta = self.assumptions.hotel_resale_discount_factor
        r_supp_unsold = self.assumptions.hotel_supplier_refund_rate_unsold
        
        # Supplier refund on cancellation applies only if contract is refundable
        r_supp_cancel = (self.assumptions.hotel_supplier_refund_rate_cancel
                         if is_supplier_refundable else 0.0)

        # State probabilities (Sum = 1.0)
        p_s1 = 1.0 - theta                               # Unsold
        p_s2 = theta * (1.0 - p_c)                       # Completed
        p_s3a = theta * p_c * f_resale                   # Cancelled & Resold
        p_s3b = theta * p_c * (1.0 - f_resale)           # Cancelled & Unresold

        # State Cash Inflows
        inflow_s1 = r_supp_unsold * c
        inflow_s2 = p
        inflow_s3a = (1.0 - r_cust) * p + delta * p
        inflow_s3b = (1.0 - r_cust) * p + r_supp_cancel * c

        expected_gross_revenue = (p_s1 * inflow_s1 +
                                  p_s2 * inflow_s2 +
                                  p_s3a * inflow_s3a +
                                  p_s3b * inflow_s3b)

        expected_net_contribution = expected_gross_revenue - c

        return {
            "expected_net_contribution": expected_net_contribution,
            "expected_gross_revenue": expected_gross_revenue,
            "purchase_cost": c,
            "selling_price": p,
            "p_unsold": p_s1,
            "p_completed": p_s2,
            "p_cancelled_resold": p_s3a,
            "p_cancelled_unresold": p_s3b,
        }
