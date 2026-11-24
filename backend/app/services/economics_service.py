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
            # Hotel economics: probability-weighted revenue factoring cancellation and salvage
            expected_revenue = price * (Decimal("1.00") - p_cancel) + cost * salvage_rate * p_cancel
            unit_contribution = expected_revenue - cost - penalty
        else:
            # Flight economics: partial non-refundable inventory with salvage / resale
            expected_revenue = price * (Decimal("1.00") - p_cancel * Decimal("0.50")) + cost * salvage_rate * (p_cancel * Decimal("0.50"))
            unit_contribution = expected_revenue - cost - penalty

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
