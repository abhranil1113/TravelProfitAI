from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.schema import InventoryCategory


class CustomerSearchEventCreateRequest(BaseModel):
    search_id: Optional[str] = None
    search_date: Optional[date] = None
    travel_date: Optional[date] = None
    dest_id: str = Field(..., max_length=32)
    origin_dest_id: Optional[str] = Field(None, max_length=32)
    inventory_category: InventoryCategory = InventoryCategory.HOTEL
    travellers_count: int = Field(1, ge=1)
    rooms_count: int = Field(1, ge=1)
    search_price: Decimal = Field(Decimal("5000.00"), ge=0)
    currency_code: str = Field("INR", max_length=8)
    clicked: bool = False
    booking_completed: bool = False
    user_session_id: Optional[str] = Field(None, max_length=64)
    conversion_value_inr: Optional[Decimal] = None

    search_timestamp: Optional[Any] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    stay_duration_nights: Optional[int] = None
    converted: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("search_id"):
                data["search_id"] = f"srch_{uuid.uuid4().hex[:12]}"
            if not data.get("search_date"):
                if data.get("search_timestamp"):
                    try:
                        ts = data["search_timestamp"]
                        data["search_date"] = ts.date() if isinstance(ts, datetime) else date.fromisoformat(str(ts)[:10])
                    except Exception:
                        data["search_date"] = date.today()
                else:
                    data["search_date"] = date.today()
            if not data.get("travel_date"):
                data["travel_date"] = data.get("check_in_date") or date.today()
            if "converted" in data and "booking_completed" not in data:
                data["booking_completed"] = bool(data["converted"])
            if not data.get("search_price"):
                data["search_price"] = data.get("conversion_value_inr") or Decimal("5000.00")
        return data


class BulkSearchEventIngestRequest(BaseModel):
    events: List[CustomerSearchEventCreateRequest]


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
    conversions: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def populate_conversions(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "conversions" not in data:
                data["conversions"] = data.get("total_bookings", 0)
        return data


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
    hourly_velocity: Optional[List[Any]] = None

    @model_validator(mode="before")
    @classmethod
    def populate_hourly_velocity(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "hourly_velocity" not in data:
                data["hourly_velocity"] = data.get("aggregates", [])
        return data


class BulkSearchEventIngestResponse(BaseModel):
    received_count: int
    ingested_count: int
    inserted_count: Optional[int] = None
    rejected_count: Optional[int] = 0
    status: str
