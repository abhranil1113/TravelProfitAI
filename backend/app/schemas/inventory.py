from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator

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

    base_cost_inr: Optional[Decimal] = None
    published_price_inr: Optional[Decimal] = None
    available_units: Optional[int] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "is_active" not in data and "status" in data:
                data["is_active"] = (str(data["status"]).upper() == "ACTIVE")
        return data


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

    inventory_item_id: Optional[str] = None
    available_capacity: Optional[int] = None
    booked_units: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_snapshot_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "inventory_id" not in data and "inventory_item_id" in data:
                data["inventory_id"] = data["inventory_item_id"]
            if "available_units" not in data and "available_capacity" in data:
                data["available_units"] = data["available_capacity"]
        return data


class BulkInventorySnapshotRequest(BaseModel):
    snapshots: List[InventorySnapshotCreateRequest]


class InventorySnapshotResponse(BaseModel):
    id: int
    inventory_id: str
    snapshot_date: Optional[date] = None
    available_units: int
    available_capacity: Optional[int] = None
    depletion_velocity: float = 0.0
    avg_selling_price_inr: Optional[Decimal] = None
    historical_cancellation_rate: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def populate_snapshot(cls, data: Any) -> Any:
        if hasattr(data, "snapshot_at"):
            snap_d = data.snapshot_at.date() if isinstance(data.snapshot_at, datetime) else data.snapshot_at
            return {
                "id": data.id,
                "inventory_id": data.inventory_id,
                "snapshot_date": snap_d,
                "available_units": data.available_units,
                "available_capacity": data.available_units,
                "depletion_velocity": data.depletion_velocity_per_day or 0.0,
                "avg_selling_price_inr": None,
                "historical_cancellation_rate": None,
                "created_at": getattr(data, "created_at", None) or data.snapshot_at,
            }
        elif isinstance(data, dict):
            if "available_units" in data and "available_capacity" not in data:
                data["available_capacity"] = data["available_units"]
            if "available_capacity" in data and "available_units" not in data:
                data["available_units"] = data["available_capacity"]
        return data


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
    id: Optional[str] = None
    published_price_inr: Optional[Decimal] = Decimal("13500.00")
    base_cost_inr: Optional[Decimal] = Decimal("8500.00")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    latest_snapshot: Optional[InventorySnapshotResponse] = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def populate_id(cls, data: Any) -> Any:
        if hasattr(data, "inventory_id"):
            category = getattr(data, "inventory_category", None) or getattr(data, "category", None)
            ref = getattr(data, "external_reference", None) or getattr(data, "name", None) or data.inventory_id
            return {
                "inventory_id": data.inventory_id,
                "id": data.inventory_id,
                "category": category,
                "unit_type": data.unit_type,
                "dest_id": data.dest_id,
                "origin_dest_id": getattr(data, "origin_dest_id", None),
                "name": ref,
                "reference_code": getattr(data, "external_reference", None),
                "star_rating": 4.5,
                "total_capacity": 50,
                "is_active": data.is_active,
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
                "latest_snapshot": None,
            }
        elif isinstance(data, dict) and "inventory_id" in data and "id" not in data:
            data["id"] = data["inventory_id"]
        return data


class InventoryItemListResponse(BaseModel):
    items: List[InventoryItemResponse]
    total: int
    page: int
    page_size: int
