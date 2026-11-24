from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

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

    @model_validator(mode="before")
    @classmethod
    def resolve_supplier_fields(cls, data):
        if isinstance(data, dict):
            if "supplier_id" not in data and "supplier_code" in data:
                data["supplier_id"] = data["supplier_code"]
            if "avg_lead_time_days" not in data and "lead_time_days" in data:
                data["avg_lead_time_days"] = data["lead_time_days"]
            if "is_active" not in data and "status" in data:
                data["is_active"] = (str(data["status"]).upper() == "ACTIVE")
        return data


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
    supplier_code: Optional[str] = None
    name: str
    supplier_type: SupplierType
    fulfillment_rate: float
    avg_lead_time_days: float
    cancellation_lead_time_days: float = 0.0
    flight_salvage_rate: float = 0.0
    max_portfolio_share: float = 1.0
    is_active: bool
    status: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data):
        if hasattr(data, "default_salvage_rate") and not hasattr(data, "flight_salvage_rate"):
            return {
                "supplier_id": data.supplier_id,
                "supplier_code": data.supplier_id,
                "id": data.supplier_id,
                "name": data.name,
                "supplier_type": data.supplier_type,
                "fulfillment_rate": float(data.fulfillment_rate or 1.0),
                "avg_lead_time_days": float(data.avg_lead_time_days or 0.0),
                "cancellation_lead_time_days": 0.0,
                "flight_salvage_rate": float(data.default_salvage_rate or 0.0),
                "max_portfolio_share": float(data.max_spend_share_cap or 1.0),
                "is_active": data.is_active,
                "status": "ACTIVE" if data.is_active else "INACTIVE",
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        elif isinstance(data, dict):
            if "supplier_id" in data:
                if "id" not in data:
                    data["id"] = data["supplier_id"]
                if "supplier_code" not in data:
                    data["supplier_code"] = data["supplier_id"]
                if "status" not in data and "is_active" in data:
                    data["status"] = "ACTIVE" if data["is_active"] else "INACTIVE"
        return data


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

    @model_validator(mode="before")
    @classmethod
    def resolve_contact_fields(cls, data):
        if isinstance(data, dict):
            if "name" not in data and "contact_name" in data:
                data["name"] = data["contact_name"]
            if "contact_role" not in data and "designation" in data:
                data["contact_role"] = data["designation"]
        return data


class SupplierContactUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    contact_role: Optional[str] = Field(None, max_length=64)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=32)
    is_primary: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_contact_fields(cls, data):
        if isinstance(data, dict):
            if "contact_role" not in data and "designation" in data:
                data["contact_role"] = data["designation"]
        return data


class SupplierContactResponse(BaseModel):
    id: int
    supplier_id: str
    name: str
    contact_role: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data):
        if hasattr(data, "contact_role"):
            role = getattr(data, "contact_role")
            try:
                setattr(data, "designation", role)
            except Exception:
                pass
        elif isinstance(data, dict):
            if "designation" not in data and "contact_role" in data:
                data["designation"] = data["contact_role"]
        return data


class SupplierPerformanceSnapshotResponse(BaseModel):
    id: int
    supplier_id: str
    snapshot_date: Optional[date] = None
    as_of_date: Optional[date] = None
    rolling_30d_fulfillment_rate: Optional[float] = 1.0
    rolling_30d_on_time_rate: Optional[float] = 1.0
    rolling_30d_cancellation_rate: Optional[float] = 0.0
    dispute_count_30d: int = 0
    total_spend_30d_inr: Optional[Decimal] = Decimal("0.00")
    composite_reliability_score: Optional[float] = 1.0

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data):
        if hasattr(data, "as_of_date"):
            return {
                "id": data.id,
                "supplier_id": data.supplier_id,
                "snapshot_date": data.as_of_date,
                "as_of_date": data.as_of_date,
                "rolling_30d_fulfillment_rate": float(getattr(data, "fulfillment_rate_30d", 1.0) or 1.0),
                "rolling_30d_on_time_rate": float(getattr(data, "fulfillment_rate_7d", 1.0) or 1.0),
                "rolling_30d_cancellation_rate": 0.0,
                "dispute_count_30d": getattr(data, "dispute_count_30d", 0) or 0,
                "total_spend_30d_inr": Decimal("0.00"),
                "composite_reliability_score": float(getattr(data, "fulfillment_rate_30d", 1.0) or 1.0),
            }
        return data
