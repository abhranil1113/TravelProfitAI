from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class DashboardMetricsResponse(BaseModel):
    total_spend_inr: Decimal
    total_expected_profit_inr: Decimal
    portfolio_roi_pct: Decimal
    active_budgets_count: int
    total_active_budget_inr: Decimal
    active_offers_count: int
    recent_optimization_runs_count: int
    pending_po_count: int


class ProfitabilityItem(BaseModel):
    entity_id: str
    entity_name: str
    category: str
    total_spend_inr: Decimal
    expected_profit_inr: Decimal
    profit_margin_pct: Decimal


class ProfitabilityAnalyticsResponse(BaseModel):
    destination_profitability: List[ProfitabilityItem]
    supplier_profitability: List[ProfitabilityItem]


class CancellationPricingAnalyticsResponse(BaseModel):
    average_hotel_cancellation_rate: Decimal
    high_risk_destinations: List[Dict[str, Any]]
    price_elasticity_summary: List[Dict[str, Any]]


class SupplierScorecardItem(BaseModel):
    supplier_id: int
    supplier_name: str
    supplier_type: str
    total_spend_inr: Decimal
    on_time_delivery_rate: Decimal
    fulfillment_accuracy_rate: Decimal
    quality_score: Decimal
    status: str


class SupplierScorecardResponse(BaseModel):
    items: List[SupplierScorecardItem]
    total: int
