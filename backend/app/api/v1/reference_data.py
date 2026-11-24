from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.auth import AuthMessageResponse
from backend.app.schemas.reference_data import (
    ExchangeRateCreateRequest,
    ExchangeRateListResponse,
    ExchangeRateResponse,
    MarketSegmentBaselineResponse,
    MarketSegmentBaselineUpsertRequest,
    MarketSignalCreateRequest,
    MarketSignalListResponse,
    MarketSignalResponse,
    MarketSignalUpdateRequest,
)
from backend.app.services.reference_data_service import ReferenceDataService

signals_router = APIRouter(prefix="/market-signals", tags=["7. Reference Data - Market Signals"])
rates_router = APIRouter(prefix="/exchange-rates", tags=["7. Reference Data - Exchange Rates"])
baselines_router = APIRouter(prefix="/market-segment-baselines", tags=["7. Reference Data - Baselines"])


# --- Market Signals (55-58) ---

@signals_router.get("", response_model=MarketSignalListResponse)
def list_market_signals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    dest_id: Optional[str] = None,
    signal_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List market signals with destination and date range filters."""
    items, total = ReferenceDataService.list_market_signals(
        db, dest_id=dest_id, signal_type=signal_type, start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )
    return MarketSignalListResponse(
        items=[MarketSignalResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@signals_router.post("", response_model=MarketSignalResponse, status_code=status.HTTP_201_CREATED)
def create_market_signal(
    payload: MarketSignalCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create market signal (Admin only)."""
    signal = ReferenceDataService.create_market_signal(db, payload, user_id=current_admin.id)
    return MarketSignalResponse.model_validate(signal)


@signals_router.patch("/{id}", response_model=MarketSignalResponse)
def update_market_signal(
    id: int,
    payload: MarketSignalUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update market signal parameters (Admin only, Tier 2)."""
    signal = ReferenceDataService.update_market_signal(db, id, payload, user_id=current_admin.id)
    return MarketSignalResponse.model_validate(signal)


@signals_router.delete("/{id}", response_model=AuthMessageResponse)
def delete_market_signal(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete market signal (Admin only, Tier 2)."""
    ReferenceDataService.delete_market_signal(db, id, user_id=current_admin.id)
    return AuthMessageResponse(message=f"Market signal {id} deleted successfully.")


# --- Exchange Rates (59-61) ---

@rates_router.get("/latest", response_model=list[ExchangeRateResponse])
def get_latest_exchange_rates(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get latest exchange rate for each currency pair."""
    rates = ReferenceDataService.get_latest_rates(db)
    return [ExchangeRateResponse.model_validate(r) for r in rates]


@rates_router.get("", response_model=ExchangeRateListResponse)
def list_exchange_rates(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    pair: Optional[str] = None,
    as_of: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List historical exchange rates."""
    items, total = ReferenceDataService.list_exchange_rates(
        db, currency_pair=pair, as_of_date=as_of, page=page, page_size=page_size
    )
    return ExchangeRateListResponse(
        items=[ExchangeRateResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@rates_router.post("", response_model=ExchangeRateResponse, status_code=status.HTTP_201_CREATED)
def create_exchange_rate(
    payload: ExchangeRateCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Ingest exchange rate (Worker / Admin only, Tier 2)."""
    rate = ReferenceDataService.create_exchange_rate(db, payload)
    return ExchangeRateResponse.model_validate(rate)


# --- Market Segment Baselines (62-63) ---

@baselines_router.get("", response_model=list[MarketSegmentBaselineResponse])
def list_market_segment_baselines(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """List market segment baseline benchmarks."""
    baselines = ReferenceDataService.list_segment_baselines(db)
    return [MarketSegmentBaselineResponse.model_validate(b) for b in baselines]


@baselines_router.put("/{segment_name}", response_model=MarketSegmentBaselineResponse)
def upsert_market_segment_baseline(
    segment_name: str,
    payload: MarketSegmentBaselineUpsertRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Upsert market segment baseline benchmark (EDA job / Admin only, Tier 2)."""
    seg = ReferenceDataService.upsert_segment_baseline(db, segment_name, payload, user_id=current_admin.id)
    return MarketSegmentBaselineResponse.model_validate(seg)
