from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.app.models.schema import InventoryCategory, UnitType


class InventoryItemCreateRequest(BaseModel):
    inventory_id: str = Field(..., min_length=2, max_length=64)
    category: InventoryCategory
    unit_type: UnitType
    dest_id: str = Field(..., max_length=32)
    origin_dest_id: Optional[str] = Field(None, max_length=32)
    name: str = Field(..., min_length=2, max_length=150)
    reference_code: Optional[str] = Field(None, max_length=64)
    star_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    total_capacity: int = Field(0, ge=0)
    is_active: bool = True


class InventoryItemUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    reference_code: Optional[str] = Field(None, max_length=64)
    star_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    total_capacity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class InventorySnapshotCreateRequest(BaseModel):
    inventory_id: str = Field(..., max_length=64)
    snapshot_date: date
    available_units: int = Field(..., ge=0)
    depletion_velocity: float = Field(0.0, ge=0.0)
    avg_selling_price_inr: Optional[Decimal] = None
    historical_cancellation_rate: Optional[float] = Field(None, ge=0.0, le=1.0)


class InventorySnapshotResponse(BaseModel):
    id: int
    inventory_id: str
    snapshot_date: date
    available_units: int
    depletion_velocity: float
    avg_selling_price_inr: Optional[Decimal] = None
    historical_cancellation_rate: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class InventoryItemResponse(BaseModel):
    inventory_id: str
    category: InventoryCategory
    unit_type: UnitType
    dest_id: str
    origin_dest_id: Optional[str] = None
    name: str
    reference_code: Optional[str] = None
    star_rating: Optional[float] = None
    total_capacity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    latest_snapshot: Optional[InventorySnapshotResponse] = None

    class Config:
        from_attributes = True


class InventoryItemListResponse(BaseModel):
    items: List[InventoryItemResponse]
    total: int
    page: int
    page_size: int
