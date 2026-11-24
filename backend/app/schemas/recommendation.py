from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import (
    ApprovalStatus,
    InventoryCategory,
    RejectionReasonCode,
    UnitType,
)


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    offer_id: int
    prediction_id: Optional[int] = None
    supplier_id: int
    dest_id: int
    inventory_category: InventoryCategory
    unit_type: UnitType
    recommended_qty: int
    unit_cost_inr: Decimal
    total_spend_inr: Decimal
    expected_unit_contribution_inr: Decimal
    expected_total_contribution_inr: Decimal
    sell_through_rate: Decimal
    moq_applied: int
    capacity_available: int
    rationale: Optional[str] = None
    approval_status: ApprovalStatus
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RecommendationListResponse(BaseModel):
    items: List[RecommendationResponse]
    total: int
    page: int
    page_size: int


class RecommendationDecisionRequest(BaseModel):
    decision_notes: Optional[str] = Field(None, max_length=500)


class BulkRecommendationDecisionRequest(BaseModel):
    recommendation_ids: List[int] = Field(..., min_length=1)
    decision_notes: Optional[str] = Field(None, max_length=500)


class BulkRecommendationDecisionResponse(BaseModel):
    updated_count: int
    status: ApprovalStatus


class RejectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    offer_id: int
    prediction_id: Optional[int] = None
    supplier_id: int
    dest_id: int
    inventory_category: InventoryCategory
    unit_type: UnitType
    reason_code: RejectionReasonCode
    reason_detail: Optional[str] = None
    expected_unit_contribution_inr: Optional[Decimal] = None
    moq_cost_inr: Optional[Decimal] = None


class RejectionListResponse(BaseModel):
    items: List[RejectionResponse]
    total: int
    page: int
    page_size: int


class RejectionReasonSummaryItem(BaseModel):
    reason_code: RejectionReasonCode
    count: int
    total_moq_cost_inr: Decimal


class RejectionSummaryResponse(BaseModel):
    run_id: str
    total_rejections: int
    breakdown: List[RejectionReasonSummaryItem]
