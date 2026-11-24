from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import (
    BudgetPeriodType,
    BudgetScope,
    BudgetStatus,
    BudgetTransactionType,
)


class BudgetCreateRequest(BaseModel):
    budget_code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=128)
    scope: BudgetScope = BudgetScope.GLOBAL
    scope_dest_id: Optional[int] = None
    period_type: BudgetPeriodType = BudgetPeriodType.QUARTERLY
    period_start: date
    period_end: date
    total_amount_inr: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class BudgetUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    scope_dest_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_amount_inr: Optional[Decimal] = Field(None, gt=0)
    notes: Optional[str] = None


class BudgetAdjustRequest(BaseModel):
    amount_inr: Decimal = Field(..., description="Positive for budget increase, negative for budget reduction")
    description: str = Field(..., min_length=3, max_length=500)
    idempotency_key: Optional[str] = Field(None, max_length=128)


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_code: str
    name: str
    scope: BudgetScope
    scope_dest_id: Optional[int] = None
    period_type: BudgetPeriodType
    period_start: date
    period_end: date
    total_amount_inr: Decimal
    spent_amount_inr: Decimal
    reserved_amount_inr: Decimal
    available_amount_inr: Optional[Decimal] = None
    status: BudgetStatus
    created_by_user_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BudgetListResponse(BaseModel):
    items: List[BudgetResponse]
    total: int


class BudgetLedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: int
    idempotency_key: Optional[str] = None
    transaction_type: BudgetTransactionType
    amount_inr: Decimal
    previous_balance_inr: Decimal
    new_balance_inr: Decimal
    optimization_run_id: Optional[int] = None
    po_number: Optional[str] = None
    created_by_user_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime


class BudgetLedgerListResponse(BaseModel):
    items: List[BudgetLedgerEntryResponse]
    total: int


class BudgetUtilizationResponse(BaseModel):
    budget_id: int
    budget_code: str
    name: str
    total_amount_inr: Decimal
    spent_amount_inr: Decimal
    reserved_amount_inr: Decimal
    available_amount_inr: Decimal
    utilization_rate: float
    status: BudgetStatus
