from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import InventoryCategory, User, UserRole
from backend.app.schemas.forecast import (
    DemandChartResponse,
    DemandForecastListResponse,
    DemandForecastResponse,
    ForecastMaterializeRequest,
    ForecastMaterializeResponse,
    InventoryForecastListResponse,
    InventoryForecastResponse,
    OfferPredictionListResponse,
    PredictionGenerateRequest,
    PredictionGenerateResponse,
)
from backend.app.schemas.supplier_offer import OfferPredictionBriefResponse
from backend.app.services.forecasting_service import ForecastingService

predictions_router = APIRouter(prefix="/predictions", tags=["10. Predictions"])
forecasts_router = APIRouter(prefix="/forecasts", tags=["10. Forecasts"])


# --- Predictions (82-83) ---

@predictions_router.get("/offers")
def list_offer_predictions(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    as_of_date: Optional[date] = None,
    run_id: Optional[str] = None,
    offer_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List historical offer ML predictions with filters."""
    items, total = ForecastingService.list_offer_predictions(
        db, as_of_date=as_of_date, run_id=run_id, offer_id=offer_id, page=page, page_size=page_size
    )
    return {
        "items": [OfferPredictionBriefResponse.model_validate(p) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@predictions_router.post("/offers/generate", response_model=PredictionGenerateResponse)
def generate_offer_predictions(
    payload: PredictionGenerateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Batch-generate offer predictions asynchronously."""
    return ForecastingService.generate_predictions(db, payload, user_id=current_user.id)


# --- Forecasts (84-87) ---
# NOTE: /demand/{dest_id}/chart defined before /demand/{dest_id} if any

@forecasts_router.get("/demand/{dest_id}/chart", response_model=DemandChartResponse)
def get_demand_forecast_chart(
    dest_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Chart-ready time-series of historical actuals and forward-looking predictions (Tier 2)."""
    return ForecastingService.get_demand_chart(db, dest_id)


@forecasts_router.get("/demand", response_model=DemandForecastListResponse)
def list_demand_forecasts(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    dest_id: Optional[str] = None,
    category: Optional[InventoryCategory] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List forward-looking destination demand forecasts."""
    items, total = ForecastingService.list_demand_forecasts(
        db, dest_id=dest_id, category=category, start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )
    return DemandForecastListResponse(
        items=[DemandForecastResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@forecasts_router.get("/inventory", response_model=InventoryForecastListResponse)
def list_inventory_forecasts(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    dest_id: Optional[str] = None,
    category: Optional[InventoryCategory] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List forward-looking inventory depletion forecasts."""
    items, total = ForecastingService.list_inventory_forecasts(
        db, dest_id=dest_id, category=category, start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )
    return InventoryForecastListResponse(
        items=[InventoryForecastResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@forecasts_router.post("/materialize", response_model=ForecastMaterializeResponse)
def materialize_forecasts(
    payload: ForecastMaterializeRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Trigger asynchronous materialization of forward-looking forecasts (Admin only, Tier 2)."""
    return ForecastingService.materialize_forecasts(db, payload, user_id=current_admin.id)
