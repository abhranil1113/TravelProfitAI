from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarketSignalCreateRequest(BaseModel):
    dest_id: str = Field(..., max_length=32)
    signal_type: str = Field(..., min_length=2, max_length=64)
    signal_date: Optional[date] = None
    event_name: Optional[str] = None
    demand_multiplier: Optional[float] = None
    is_peak_season: bool = False

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    severity: Optional[str] = "MEDIUM"
    demand_impact_multiplier: Optional[float] = None
    description: Optional[str] = None
    signal_value: Optional[float] = None
    headline: Optional[str] = None
    confidence: Optional[float] = None
    is_active: Optional[bool] = None


class MarketSignalUpdateRequest(BaseModel):
    signal_type: Optional[str] = Field(None, min_length=2, max_length=64)
    signal_date: Optional[date] = None
    event_name: Optional[str] = None
    demand_multiplier: Optional[float] = None
    is_peak_season: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    severity: Optional[str] = Field(None, max_length=16)
    demand_impact_multiplier: Optional[float] = Field(None, gt=0.0)
    description: Optional[str] = None
    signal_value: Optional[float] = None
    headline: Optional[str] = None


class MarketSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dest_id: str
    signal_date: date
    signal_type: str
    event_name: str
    headline: Optional[str] = None
    demand_multiplier: float
    signal_value: Optional[float] = None
    is_peak_season: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    severity: Optional[str] = "MEDIUM"
    demand_impact_multiplier: Optional[float] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data):
        if hasattr(data, "signal_date"):
            return {
                "id": data.id,
                "dest_id": data.dest_id,
                "signal_date": data.signal_date,
                "signal_type": data.signal_type,
                "event_name": data.event_name,
                "headline": data.event_name,
                "demand_multiplier": data.demand_multiplier,
                "signal_value": data.demand_multiplier,
                "is_peak_season": data.is_peak_season,
                "start_date": data.signal_date,
                "end_date": data.signal_date,
                "severity": "HIGH" if data.is_peak_season else "MEDIUM",
                "demand_impact_multiplier": data.demand_multiplier,
                "description": data.event_name,
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        elif isinstance(data, dict):
            if "demand_multiplier" in data and "signal_value" not in data:
                data["signal_value"] = data["demand_multiplier"]
            if "signal_value" in data and "demand_multiplier" not in data:
                data["demand_multiplier"] = data["signal_value"]
            if "event_name" in data and "headline" not in data:
                data["headline"] = data["event_name"]
            if "headline" in data and "event_name" not in data:
                data["event_name"] = data["headline"]
        return data


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

    source_currency: Optional[str] = None
    target_currency: Optional[str] = None
    rate_date: Optional[date] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data):
        if isinstance(data, dict):
            if "currency_pair" not in data and "source_currency" in data and "target_currency" in data:
                data["currency_pair"] = f"{data['source_currency']}/{data['target_currency']}"
            if "as_of_date" not in data and "rate_date" in data:
                data["as_of_date"] = data["rate_date"]
        return data


class ExchangeRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    currency_pair: str
    as_of_date: date
    rate: Decimal
    source: Optional[str] = None
    created_at: datetime
    source_currency: Optional[str] = None
    target_currency: Optional[str] = None
    rate_date: Optional[date] = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data):
        if hasattr(data, "from_currency"):
            pair = f"{data.from_currency}/{data.to_currency}"
            return {
                "id": data.id,
                "currency_pair": pair,
                "as_of_date": data.as_of_date,
                "rate": data.rate,
                "source": data.source,
                "created_at": getattr(data, "created_at", None) or datetime.now(),
                "source_currency": data.from_currency,
                "target_currency": data.to_currency,
                "rate_date": data.as_of_date,
            }
        elif hasattr(data, "currency_pair"):
            pair = data.currency_pair or ""
            parts = pair.split("/")
            s_curr = parts[0] if len(parts) > 0 else None
            t_curr = parts[1] if len(parts) > 1 else None
            return {
                "id": data.id,
                "currency_pair": data.currency_pair,
                "as_of_date": data.as_of_date,
                "rate": data.rate,
                "source": data.source,
                "created_at": getattr(data, "created_at", None) or datetime.now(),
                "source_currency": s_curr,
                "target_currency": t_curr,
                "rate_date": data.as_of_date,
            }
        elif isinstance(data, dict):
            if "currency_pair" in data and "source_currency" not in data:
                parts = data["currency_pair"].split("/")
                if len(parts) == 2:
                    data["source_currency"] = parts[0]
                    data["target_currency"] = parts[1]
            if "as_of_date" in data and "rate_date" not in data:
                data["rate_date"] = data["as_of_date"]
        return data


class ExchangeRateListResponse(BaseModel):
    items: List[ExchangeRateResponse]
    total: int
    page: int
    page_size: int


class MarketSegmentBaselineUpsertRequest(BaseModel):
    segment_name: Optional[str] = Field(None, max_length=64)
    baseline_adr_inr: Optional[Decimal] = None
    baseline_cancellation_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    baseline_lead_time_days: Optional[float] = Field(None, ge=0.0)
    notes: Optional[str] = None
    inventory_category: Optional[str] = None
    avg_base_price_inr: Optional[Decimal] = None
    avg_cancellation_rate: Optional[float] = None
    typical_lead_time_days: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data):
        if isinstance(data, dict):
            if "baseline_adr_inr" not in data and "avg_base_price_inr" in data:
                data["baseline_adr_inr"] = data["avg_base_price_inr"]
            if "baseline_cancellation_rate" not in data and "avg_cancellation_rate" in data:
                data["baseline_cancellation_rate"] = data["avg_cancellation_rate"]
            if "baseline_lead_time_days" not in data and "typical_lead_time_days" in data:
                data["baseline_lead_time_days"] = data["typical_lead_time_days"]
        return data


class MarketSegmentBaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    segment_name: str
    baseline_adr_inr: Optional[Decimal] = None
    baseline_cancellation_rate: Optional[float] = None
    baseline_lead_time_days: Optional[float] = None
    avg_base_price_inr: Optional[Decimal] = None
    avg_cancellation_rate: Optional[float] = None
    typical_lead_time_days: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data):
        if hasattr(data, "baseline_adr_inr"):
            return {
                "id": data.id,
                "segment_name": data.segment_name,
                "baseline_adr_inr": data.baseline_adr_inr,
                "avg_base_price_inr": data.baseline_adr_inr,
                "baseline_cancellation_rate": data.baseline_cancellation_rate,
                "avg_cancellation_rate": data.baseline_cancellation_rate,
                "baseline_lead_time_days": data.baseline_lead_time_days,
                "typical_lead_time_days": data.baseline_lead_time_days,
                "notes": getattr(data, "notes", None),
                "created_at": getattr(data, "created_at", None) or datetime.now(),
                "updated_at": getattr(data, "updated_at", None) or datetime.now(),
            }
        return data
