from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.schema import FulfillmentStatus, POStatus


class PurchaseOrderCreateLine(BaseModel):
    offer_id: Any
    ordered_qty: int = Field(..., gt=0)
    unit_cost_inr: Decimal = Field(..., gt=0)
    recommendation_id: Optional[int] = None


class PurchaseOrderCreateRequest(BaseModel):
    supplier_id: Any
    budget_id: Optional[int] = None
    lines: List[PurchaseOrderCreateLine] = Field(..., min_length=1)
    notes: Optional[str] = None


class PurchaseOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    recommendation_id: Optional[int] = None
    offer_id: Any
    ordered_qty: int
    unit_cost_inr: Decimal
    line_total_inr: Decimal
    created_at: datetime
    updated_at: datetime


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    po_number: str
    supplier_id: Any
    budget_id: Optional[int] = None
    ordered_by_user_id: Optional[int] = None
    ordered_at: datetime
    currency: str
    total_committed_spend_inr: Decimal
    status: POStatus
    notes: Optional[str] = None
    lines: Optional[List[PurchaseOrderLineResponse]] = None
    created_at: datetime
    updated_at: datetime


class PurchaseOrderListResponse(BaseModel):
    items: List[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int


class PurchaseOrderConfirmRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


class PurchaseOrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class FulfillmentCreateRequest(BaseModel):
    delivered_qty: int = Field(..., ge=0)
    delivered_at: Optional[datetime] = None
    actual_unit_cost_inr: Optional[Decimal] = None
    notes: Optional[str] = None


class FulfillmentUpdateRequest(BaseModel):
    status: Optional[FulfillmentStatus] = None
    fulfilled_units: Optional[int] = Field(None, ge=0)
    cancelled_units: Optional[int] = Field(None, ge=0)
    spoilage_units: Optional[int] = Field(None, ge=0)
    salvaged_units: Optional[int] = Field(None, ge=0)
    resold_units: Optional[int] = Field(None, ge=0)
    unsold_units: Optional[int] = Field(None, ge=0)
    supplier_refund_received_inr: Optional[Decimal] = None
    actual_revenue_inr: Optional[Decimal] = None
    actual_net_profit_inr: Optional[Decimal] = None
    notes: Optional[str] = None


class FulfillmentDisputeRequest(BaseModel):
    dispute_reason: str = Field(..., min_length=5, max_length=1000)


class FulfillmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_line_id: int
    delivered_qty: int
    delivered_at: Optional[datetime] = None
    actual_unit_cost_inr: Optional[Decimal] = None
    actual_total_cost_inr: Optional[Decimal] = None
    spoilage_units: int = 0
    salvaged_units: int = 0
    fulfilled_units: int = 0
    cancelled_units: int = 0
    resold_units: int = 0
    unsold_units: int = 0
    supplier_refund_received_inr: Decimal = Decimal("0.00")
    actual_revenue_inr: Optional[Decimal] = None
    actual_net_profit_inr: Optional[Decimal] = None
    status: Any = None
    notes: Optional[str] = None
    dispute_reason: Optional[str] = None
    dispute_status: Optional[str] = None
    disputed_at: Optional[datetime] = None
    disputed_by_user_id: Optional[int] = None
    dispute_resolved_at: Optional[datetime] = None
    dispute_resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def check_dispute(cls, data):
        if hasattr(data, "dispute_status") and getattr(data, "dispute_status") == "OPEN":
            d = {c.name: getattr(data, c.name) for c in data.__table__.columns}
            d["status"] = "DISPUTED"
            return d
        return data


class FulfillmentListResponse(BaseModel):
    items: List[FulfillmentResponse]
    total: int
