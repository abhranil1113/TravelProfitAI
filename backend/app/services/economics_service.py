from __future__ import annotations

from decimal import Decimal
from backend.app.models.schema import InventoryCategory
from backend.app.schemas.economics import (
    EconomicsSimulateRequest,
    EconomicsSimulateResponse,
)


class EconomicsService:

    @staticmethod
    def simulate(req: EconomicsSimulateRequest) -> EconomicsSimulateResponse:
        cost = req.unit_cost_inr
        price = req.expected_sale_price_inr
        margin = price - cost
        p_cancel = req.cancellation_probability
        salvage_rate = req.salvage_rate_pct
        penalty = req.penalty_cost_inr or Decimal("0.00")

        if req.inventory_category == InventoryCategory.HOTEL:
            # Four-outcome scenario economics aligned with optimization/economics/hotel_economics.py
            theta = Decimal("0.85")      # Base sell-through
            r_cust = Decimal("0.80")     # Customer refund rate
            f_resale = Decimal("0.40")   # Resale probability
            delta = Decimal("0.90")      # Resale discount factor
            r_supp_cancel = Decimal("0.85") if getattr(req, "refundable", False) else Decimal("0.00")
            r_supp_unsold = Decimal("0.00")

            p_s1 = Decimal("1.00") - theta                     # Unsold
            p_s2 = theta * (Decimal("1.00") - p_cancel)         # Completed
            p_s3a = theta * p_cancel * f_resale                 # Cancelled & Resold
            p_s3b = theta * p_cancel * (Decimal("1.00") - f_resale)  # Cancelled & Unresold

            inflow_s1 = r_supp_unsold * cost
            inflow_s2 = price
            inflow_s3a = (Decimal("1.00") - r_cust) * price + delta * price
            inflow_s3b = (Decimal("1.00") - r_cust) * price + r_supp_cancel * cost

            expected_revenue = (p_s1 * inflow_s1 + p_s2 * inflow_s2 + p_s3a * inflow_s3a + p_s3b * inflow_s3b)
            unit_contribution = expected_revenue - cost - penalty
        else:
            # Flight procurement economics aligned with optimization/economics/flight_economics.py
            theta = Decimal("0.85")
            expected_gross_revenue = theta * price + (Decimal("1.00") - theta) * salvage_rate * cost
            expected_penalty = (Decimal("1.00") - theta) * penalty
            unit_contribution = expected_gross_revenue - cost - expected_penalty

        total_net_profit = unit_contribution * req.demand_quantity
        profit_margin = (unit_contribution / price * 100) if price > 0 else Decimal("0.00")
        roi = (unit_contribution / cost * 100) if cost > 0 else Decimal("0.00")

        breakeven = int(cost / unit_contribution) if unit_contribution > 0 else req.demand_quantity

        if p_cancel > Decimal("0.35"):
            risk = "HIGH_RISK_CANCELLATION"
        elif unit_contribution < Decimal("0.00"):
            risk = "NEGATIVE_CONTRIBUTION_REJECTED"
        elif roi < Decimal("10.00"):
            risk = "LOW_MARGIN_MONITOR"
        else:
            risk = "HIGH_CONFIDENCE_ATTRACTIVE"

        return EconomicsSimulateResponse(
            unit_cost_inr=cost,
            expected_sale_price_inr=price,
            unit_margin_inr=margin,
            expected_unit_contribution_inr=round(unit_contribution, 2),
            expected_net_profit_inr=round(total_net_profit, 2),
            profit_margin_pct=round(profit_margin, 2),
            return_on_spend_pct=round(roi, 2),
            breakeven_units=max(1, breakeven),
            risk_assessment=risk,
        )
