from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import InventoryCategory, UnitType


class OfferPredictionListResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class PredictionGenerateRequest(BaseModel):
    as_of_date: Optional[date] = None
    offer_ids: Optional[List[Any]] = None
    destination_ids: Optional[List[Any]] = None
    force_recompute: bool = False


class PredictionGenerateResponse(BaseModel):
    batch_task_id: str
    as_of_date: date
    target_offers_count: int
    status: str
    message: str


class DemandForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    dest_id: str
    inventory_category: InventoryCategory
    unit_type: UnitType
    origin_dest_id: Optional[str] = None
    forecast_date: date
    as_of_date: date
    predicted_demand_units: int
    predicted_search_volume: Optional[int] = None
    confidence_lower: Optional[float] = None
    confidence_upper: Optional[float] = None
    demand_multiplier: float
    model_version: str


class DemandForecastListResponse(BaseModel):
    items: List[DemandForecastResponse]
    total: int
    page: int
    page_size: int


class InventoryForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    dest_id: str
    inventory_category: InventoryCategory
    unit_type: UnitType
    origin_dest_id: Optional[str] = None
    inventory_id: Optional[str] = None
    forecast_date: date
    as_of_date: date
    predicted_available_units: int
    predicted_depletion_velocity: float
    confidence_lower: Optional[float] = None
    confidence_upper: Optional[float] = None
    model_version: str


class InventoryForecastListResponse(BaseModel):
    items: List[InventoryForecastResponse]
    total: int
    page: int
    page_size: int


class ChartDataPoint(BaseModel):
    date: date
    actual_searches: Optional[int] = None
    actual_bookings: Optional[int] = None
    predicted_demand: Optional[int] = None
    confidence_lower: Optional[float] = None
    confidence_upper: Optional[float] = None


class DemandChartResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    dest_id: str
    time_series: List[ChartDataPoint]
    model_version: str
    generated_at: datetime


class ForecastMaterializeRequest(BaseModel):
    horizon_days: int = Field(30, ge=1, le=90)
    as_of_date: Optional[date] = None
    dest_ids: Optional[List[str]] = None


class ForecastMaterializeResponse(BaseModel):
    task_id: str
    destinations_queued: int
    horizon_days: int
    status: str
