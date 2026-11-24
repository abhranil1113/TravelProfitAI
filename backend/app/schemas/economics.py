from __future__ import annotations

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import InventoryCategory


class EconomicsSimulateRequest(BaseModel):
    inventory_category: InventoryCategory = InventoryCategory.HOTEL
    unit_cost_inr: Decimal = Field(..., gt=0)
    expected_sale_price_inr: Decimal = Field(..., gt=0)
    demand_quantity: int = Field(..., gt=0)
    cancellation_probability: Decimal = Field(Decimal("0.15"), ge=0, le=1)
    salvage_rate_pct: Decimal = Field(Decimal("0.10"), ge=0, le=1)
    penalty_cost_inr: Optional[Decimal] = Field(Decimal("0.00"), ge=0)


class EconomicsSimulateResponse(BaseModel):
    unit_cost_inr: Decimal
    expected_sale_price_inr: Decimal
    unit_margin_inr: Decimal
    expected_unit_contribution_inr: Decimal
    expected_net_profit_inr: Decimal
    profit_margin_pct: Decimal
    return_on_spend_pct: Decimal
    breakeven_units: int
    risk_assessment: str
