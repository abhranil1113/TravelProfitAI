from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.app.models.schema import InventoryCategory


class DestinationCreateRequest(BaseModel):
    dest_id: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=120)
    city: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    airport_code: Optional[str] = Field(None, max_length=8)
    search_volume_ceiling: int = Field(0, ge=0)
    is_active: bool = True


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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


class SearchVelocityResponse(BaseModel):
    dest_id: str
    rolling_7d_searches: int
    rolling_30d_searches: int
    velocity_growth_pct: float
    search_volume_ceiling: int
    ceiling_utilization_pct: float
