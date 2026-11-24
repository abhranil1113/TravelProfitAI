from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MarketSignalCreateRequest(BaseModel):
    dest_id: str = Field(..., max_length=32)
    signal_type: str = Field(..., min_length=2, max_length=64)
    start_date: date
    end_date: date
    severity: str = Field("MEDIUM", max_length=16)
    demand_impact_multiplier: float = Field(1.0, gt=0.0)
    description: Optional[str] = None


class MarketSignalUpdateRequest(BaseModel):
    signal_type: Optional[str] = Field(None, min_length=2, max_length=64)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    severity: Optional[str] = Field(None, max_length=16)
    demand_impact_multiplier: Optional[float] = Field(None, gt=0.0)
    description: Optional[str] = None


class MarketSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dest_id: str
    signal_type: str
    start_date: date
    end_date: date
    severity: str
    demand_impact_multiplier: float
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MarketSignalListResponse(BaseModel):
    items: List[MarketSignalResponse]
    total: int
    page: int
    page_size: int


class ExchangeRateCreateRequest(BaseModel):
    currency_pair: str = Field(..., min_length=6, max_length=8)  # e.g. "EUR/INR"
    as_of_date: date
    rate: Decimal = Field(..., gt=0)
    source: Optional[str] = Field(None, max_length=64)


class ExchangeRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    currency_pair: str
    as_of_date: date
    rate: Decimal
    source: Optional[str] = None
    created_at: datetime


class ExchangeRateListResponse(BaseModel):
    items: List[ExchangeRateResponse]
    total: int
    page: int
    page_size: int


class MarketSegmentBaselineUpsertRequest(BaseModel):
    segment_name: str = Field(..., min_length=2, max_length=64)
    baseline_adr_inr: Optional[Decimal] = None
    baseline_cancellation_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    baseline_lead_time_days: Optional[float] = Field(None, ge=0.0)
    notes: Optional[str] = None


class MarketSegmentBaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    segment_name: str
    baseline_adr_inr: Optional[Decimal] = None
    baseline_cancellation_rate: Optional[float] = None
    baseline_lead_time_days: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
