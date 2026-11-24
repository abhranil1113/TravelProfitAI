from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import InventoryCategory, OfferStatus, UnitType
from backend.app.schemas.inventory import InventorySnapshotResponse


class SupplierOfferCreateRequest(BaseModel):
    offer_id: str = Field(..., min_length=2, max_length=64)
    supplier_id: str = Field(..., max_length=32)
    inventory_id: str = Field(..., max_length=64)
    dest_id: str = Field(..., max_length=32)
    origin_dest_id: Optional[str] = Field(None, max_length=32)
    inventory_category: InventoryCategory
    unit_type: UnitType
    available_qty: int = Field(..., gt=0)
    moq: int = Field(1, ge=1)
    cost_per_unit_inr: Decimal = Field(..., gt=0)
    currency: str = Field("INR", max_length=8)
    original_cost: Optional[Decimal] = None
    original_currency: Optional[str] = Field(None, max_length=8)
    travel_date: date
    valid_from: Optional[datetime] = None
    valid_until: datetime
    cancellation_deadline: Optional[datetime] = None
    refundable: bool = False
    refund_penalty_pct: float = Field(0.0, ge=0.0, le=1.0)
    status: OfferStatus = OfferStatus.ACTIVE


class SupplierOfferUpdateRequest(BaseModel):
    available_qty: Optional[int] = Field(None, gt=0)
    moq: Optional[int] = Field(None, ge=1)
    cost_per_unit_inr: Optional[Decimal] = Field(None, gt=0)
    valid_until: Optional[datetime] = None
    cancellation_deadline: Optional[datetime] = None
    refundable: Optional[bool] = None
    refund_penalty_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[OfferStatus] = None


class OfferPredictionBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    offer_id: str
    as_of_date: date
    predicted_selling_price_inr: Optional[Decimal] = None
    predicted_cancellation_prob: Optional[float] = None
    expected_net_margin_inr: Optional[Decimal] = None
    expected_margin_pct: Optional[float] = None
    break_even_sell_through: Optional[float] = None
    spoilage_risk_pct: Optional[float] = None
    model_version_used: Optional[str] = None
    created_at: datetime


class SupplierOfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offer_id: str
    supplier_id: str
    inventory_id: str
    dest_id: str
    origin_dest_id: Optional[str] = None
    inventory_category: InventoryCategory
    unit_type: UnitType
    available_qty: int
    moq: int
    cost_per_unit_inr: Decimal
    currency: str
    original_cost: Optional[Decimal] = None
    original_currency: Optional[str] = None
    travel_date: date
    valid_from: Optional[datetime] = None
    valid_until: datetime
    cancellation_deadline: Optional[datetime] = None
    refundable: bool
    refund_penalty_pct: float
    status: OfferStatus
    created_at: datetime
    updated_at: datetime
    latest_prediction: Optional[OfferPredictionBriefResponse] = None
    latest_snapshot: Optional[InventorySnapshotResponse] = None


class SupplierOfferListResponse(BaseModel):
    items: List[SupplierOfferResponse]
    total: int
    page: int
    page_size: int


class BulkImportResponse(BaseModel):
    batch_uid: str
    rows_received: int
    rows_valid: int
    rows_imported: int
    rows_failed: int
    status: str
    error_summary: Optional[str] = None
