from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

from backend.app.models.schema import SupplierType


class SupplierCreateRequest(BaseModel):
    supplier_id: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=150)
    supplier_type: SupplierType
    fulfillment_rate: float = Field(1.0, ge=0.0, le=1.0)
    avg_lead_time_days: float = Field(0.0, ge=0.0)
    cancellation_lead_time_days: float = Field(0.0, ge=0.0)
    flight_salvage_rate: float = Field(0.0, ge=0.0, le=1.0)
    max_portfolio_share: float = Field(1.0, ge=0.0, le=1.0)
    is_active: bool = True


class SupplierUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    supplier_type: Optional[SupplierType] = None
    fulfillment_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    avg_lead_time_days: Optional[float] = Field(None, ge=0.0)
    cancellation_lead_time_days: Optional[float] = Field(None, ge=0.0)
    flight_salvage_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_portfolio_share: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    supplier_id: str
    name: str
    supplier_type: SupplierType
    fulfillment_rate: float
    avg_lead_time_days: float
    cancellation_lead_time_days: float
    flight_salvage_rate: float
    max_portfolio_share: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierListResponse(BaseModel):
    items: List[SupplierResponse]
    total: int
    page: int
    page_size: int


class SupplierContactCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    contact_role: Optional[str] = Field(None, max_length=64)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    is_primary: bool = False


class SupplierContactUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    contact_role: Optional[str] = Field(None, max_length=64)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    is_primary: Optional[bool] = None


class SupplierContactResponse(BaseModel):
    id: int
    supplier_id: str
    name: str
    contact_role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierPerformanceSnapshotResponse(BaseModel):
    id: int
    supplier_id: str
    snapshot_date: date
    rolling_30d_fulfillment_rate: float
    rolling_30d_on_time_rate: float
    rolling_30d_cancellation_rate: float
    dispute_count_30d: int
    total_spend_30d_inr: Decimal
    composite_reliability_score: float

    class Config:
        from_attributes = True
