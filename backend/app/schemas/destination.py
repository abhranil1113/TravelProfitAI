from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

from backend.app.models.schema import InventoryCategory


class DestinationCreateRequest(BaseModel):
    dest_id: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=120)
    city: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    airport_code: Optional[str] = Field(None, max_length=8)
    search_volume_ceiling: int = Field(0, ge=0)
    is_active: bool = True

    @model_validator(mode="before")
    @classmethod
    def resolve_dest_id(cls, data):
        if isinstance(data, dict):
            if "dest_id" not in data and "dest_code" in data:
                data["dest_id"] = data["dest_code"]
        return data


class DestinationUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=100)
    airport_code: Optional[str] = Field(None, max_length=8)
    search_volume_ceiling: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class DestinationResponse(BaseModel):
    dest_id: str
    name: str
    city: str
    country: str
    airport_code: Optional[str] = None
    search_volume_ceiling: int
    rolling_7d_searches: int
    rolling_30d_searches: int
    is_active: bool
    dest_code: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def populate_dest_code(cls, data):
        if hasattr(data, "dest_id"):
            return {
                "dest_id": data.dest_id,
                "dest_code": data.dest_id,
                "id": data.dest_id,
                "name": data.name,
                "city": data.city,
                "country": data.country,
                "airport_code": data.airport_code,
                "search_volume_ceiling": data.search_volume_ceiling,
                "rolling_7d_searches": data.rolling_7d_searches,
                "rolling_30d_searches": data.rolling_30d_searches,
                "is_active": data.is_active,
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        elif isinstance(data, dict):
            if "dest_id" in data:
                if "dest_code" not in data:
                    data["dest_code"] = data["dest_id"]
                if "id" not in data:
                    data["id"] = data["dest_id"]
        return data


class DestinationListResponse(BaseModel):
    items: List[DestinationResponse]
    total: int
    page: int
    page_size: int


class DestinationDailyMetricResponse(BaseModel):
    id: int
    dest_id: str
    inventory_category: InventoryCategory
    origin_dest_id: Optional[str] = None
    metric_date: date
    search_count: int
    booking_count: int
    avg_adr_inr: Optional[Decimal] = None
    cancellation_rate: Optional[float] = None
    load_factor: Optional[float] = None

    class Config:
        from_attributes = True


class DestinationDailyMetricsListResponse(BaseModel):
    items: List[DestinationDailyMetricResponse]
    total: int
    dest_id: str
    metrics: Optional[List[DestinationDailyMetricResponse]] = None

    @model_validator(mode="before")
    @classmethod
    def populate_metrics(cls, data):
        if isinstance(data, dict):
            if "items" in data and "metrics" not in data:
                data["metrics"] = data["items"]
        return data


class SearchVelocityResponse(BaseModel):
    dest_id: str
    rolling_7d_searches: int
    rolling_30d_searches: int
    velocity_growth_pct: float
    search_volume_ceiling: int
    ceiling_utilization_pct: float
    velocity_score: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def populate_velocity_score(cls, data):
        if isinstance(data, dict):
            if "velocity_growth_pct" in data and "velocity_score" not in data:
                data["velocity_score"] = data["velocity_growth_pct"]
        return data
