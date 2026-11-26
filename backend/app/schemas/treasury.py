from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.models.schema import (
    FXAlertSeverity,
    FXContractDirection,
    FXContractStatus,
    FXRateSource,
    MarginBreachAction,
)


# =============================================================================
# DOMAIN 4: MULTI-CURRENCY TREASURY & FX HEDGING
# =============================================================================

class FXForwardCreateRequest(BaseModel):
    base_currency: str = Field(..., min_length=3, max_length=3)
    quote_currency: str = Field("INR", min_length=3, max_length=3)
    direction: FXContractDirection
    notional_amount_base: Decimal = Field(..., gt=0)
    contracted_forward_rate: Decimal = Field(..., gt=0)
    spot_rate_at_booking: Optional[Decimal] = Field(None, gt=0)
    rate_source: FXRateSource = FXRateSource.RBI
    trade_date: date
    maturity_date: date
    valuation_timestamp: Optional[datetime] = None
    counterparty: str = Field(..., min_length=2, max_length=120)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_contract_fields(self) -> FXForwardCreateRequest:
        if self.base_currency == self.quote_currency:
            raise ValueError("base_currency and quote_currency must be distinct.")
        if self.trade_date > self.maturity_date:
            raise ValueError("trade_date cannot be after maturity_date.")
        return self


class FXForwardExecuteRequest(BaseModel):
    approval_notes: Optional[str] = Field(None, max_length=500)


class FXForwardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_number: str
    base_currency: str
    quote_currency: str
    direction: FXContractDirection
    notional_amount_base: Decimal
    contracted_forward_rate: Decimal
    spot_rate_at_booking: Decimal
    rate_source: FXRateSource
    trade_date: date
    maturity_date: date
    valuation_timestamp: datetime
    counterparty: str
    status: FXContractStatus
    mark_to_market_inr: Decimal
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    executed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FXForwardListResponse(BaseModel):
    items: List[FXForwardResponse]
    total: int
    page: int
    page_size: int


class CurrencyExposureSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_uid: str
    currency_code: str
    target_currency: str
    spot_rate_used: Decimal
    rate_source: str
    valuation_timestamp: datetime
    gross_exposure_base: Decimal
    gross_exposure_inr: Decimal
    hedged_amount_base: Decimal
    net_unhedged_base: Decimal
    net_unhedged_inr: Decimal
    hedge_ratio_pct: float
    unrealized_fx_pnl_inr: Decimal
    breakdown_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HedgeEffectivenessCreateRequest(BaseModel):
    contract_id: int = Field(..., ge=1)
    measurement_date: Optional[date] = None
    hedged_item_fv_change_inr: Optional[Decimal] = None
    notes: Optional[str] = Field(None, max_length=1000)


class HedgeEffectivenessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    measurement_date: date
    spot_rate_at_measurement: Decimal
    hedged_item_fv_change_inr: Decimal
    hedging_instrument_fv_change_inr: Decimal
    effectiveness_ratio_pct: float
    is_effective: bool
    notes: Optional[str] = None
    created_at: datetime


class MarginProtectionRuleCreateRequest(BaseModel):
    rule_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(..., min_length=2, max_length=150)
    currency_code: str = Field(..., min_length=3, max_length=3)
    min_gross_margin_pct: float = Field(..., ge=0.0, le=100.0)
    max_fx_drawdown_pct: float = Field(..., gt=0.0, le=100.0)
    min_hedge_coverage_pct: float = Field(50.0, ge=0.0, le=100.0)
    action_on_breach: MarginBreachAction = MarginBreachAction.ALERT_ONLY
    is_active: bool = True

    @field_validator("rule_code", "currency_code")
    @classmethod
    def upper_codes(cls, v: str) -> str:
        return v.strip().upper()


class MarginProtectionRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    min_gross_margin_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    max_fx_drawdown_pct: Optional[float] = Field(None, gt=0.0, le=100.0)
    min_hedge_coverage_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    action_on_breach: Optional[MarginBreachAction] = None
    is_active: Optional[bool] = None


class MarginProtectionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_code: str
    name: str
    currency_code: str
    min_gross_margin_pct: float
    max_fx_drawdown_pct: float
    min_hedge_coverage_pct: float
    action_on_breach: MarginBreachAction
    is_active: bool
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MarginImpactEvaluateRequest(BaseModel):
    currency_code: str = Field(..., min_length=3, max_length=3)
    purchase_cost_base: Decimal = Field(..., gt=0)
    selling_price_inr: Decimal = Field(..., gt=0)
    fx_shock_pct: float = Field(0.0, ge=-0.50, le=1.0)
    include_active_hedges: bool = True

    @field_validator("currency_code")
    @classmethod
    def upper_ccy(cls, v: str) -> str:
        return v.strip().upper()


class MarginImpactEvaluateResponse(BaseModel):
    currency_code: str
    spot_rate_used: Decimal
    effective_rate_with_hedges: Decimal
    hedge_coverage_pct: float
    unshocked_cost_inr: Decimal
    shocked_cost_inr: Decimal
    hedged_cost_inr: Decimal
    unhedged_margin_pct: float
    hedged_margin_pct: float
    fx_margin_erosion_pct: float
    breached_rules: List[str] = Field(default_factory=list)
    recommended_action: MarginBreachAction
    alerts_generated: int = 0


class FXAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_uid: str
    currency_code: str
    rule_id: Optional[int] = None
    severity: FXAlertSeverity
    title: str
    message: str
    observed_margin_pct: Optional[float] = None
    observed_fx_move_pct: Optional[float] = None
    is_acknowledged: bool
    acknowledged_by_user_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
