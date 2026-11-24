from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import InventoryCategory


class CustomerSearchEventCreateRequest(BaseModel):
    search_id: str = Field(..., max_length=64)
    search_date: date
    travel_date: date
    dest_id: str = Field(..., max_length=32)
    origin_dest_id: Optional[str] = Field(None, max_length=32)
    inventory_category: InventoryCategory
    travellers_count: int = Field(1, ge=1)
    rooms_count: int = Field(1, ge=1)
    search_price: Decimal = Field(..., ge=0)
    currency_code: str = Field("INR", max_length=8)
    clicked: bool = False
    booking_completed: bool = False
    user_session_id: Optional[str] = Field(None, max_length=64)
    conversion_value_inr: Optional[Decimal] = None


class CustomerSearchEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    search_id: str
    search_date: date
    travel_date: date
    dest_id: str
    origin_dest_id: Optional[str] = None
    inventory_category: InventoryCategory
    travellers_count: int
    rooms_count: int
    search_price: Decimal
    currency_code: str
    clicked: bool
    booking_completed: bool
    user_session_id: Optional[str] = None
    conversion_value_inr: Optional[Decimal] = None
    created_at: datetime


class CustomerSearchEventListResponse(BaseModel):
    items: List[CustomerSearchEventResponse]
    total: int
    page: int
    page_size: int


class FunnelStepMetric(BaseModel):
    step: str
    count: int
    conversion_from_previous_pct: float
    conversion_from_search_pct: float


class FunnelAnalyticsResponse(BaseModel):
    total_searches: int
    total_clicks: int
    total_bookings: int
    search_to_click_ctr_pct: float
    click_to_book_conversion_pct: float
    overall_funnel_conversion_pct: float
    funnel_steps: List[FunnelStepMetric]


class VelocityAggregateMetric(BaseModel):
    dest_id: str
    destination_name: str
    searches_7d: int
    searches_30d: int
    velocity_growth_pct: float
    category: str


class VelocityAnalyticsResponse(BaseModel):
    aggregates: List[VelocityAggregateMetric]
    generated_at: datetime


class BulkSearchEventIngestResponse(BaseModel):
    received_count: int
    ingested_count: int
    status: str
