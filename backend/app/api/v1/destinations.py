from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import Destination, InventoryCategory, User, UserRole
from backend.app.schemas.auth import AuthMessageResponse
from backend.app.schemas.destination import (
    DestinationCreateRequest,
    DestinationDailyMetricResponse,
    DestinationDailyMetricsListResponse,
    DestinationListResponse,
    DestinationResponse,
    DestinationUpdateRequest,
    SearchVelocityResponse,
)
from backend.app.services.destination_service import DestinationService

router = APIRouter(prefix="/destinations", tags=["3. Destinations"])


@router.get("", response_model=DestinationListResponse)
def list_destinations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    is_active: Optional[bool] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List destinations with filtering and pagination."""
    items, total = DestinationService.list_destinations(
        db, is_active=is_active, country=country, search=search, page=page, page_size=page_size
    )
    return DestinationListResponse(
        items=[DestinationResponse.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DestinationResponse, status_code=status.HTTP_201_CREATED)
def create_destination(
    payload: DestinationCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new destination record (Admin only)."""
    dest = DestinationService.create_destination(db, payload, user_id=current_admin.id)
    return DestinationResponse.model_validate(dest)


@router.get("/{dest_id}", response_model=DestinationResponse)
def get_destination_detail(
    dest_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get destination details including rolling search metrics."""
    dest = DestinationService.get_destination(db, dest_id)
    return DestinationResponse.model_validate(dest)


@router.patch("/{dest_id}", response_model=DestinationResponse)
def update_destination(
    dest_id: str,
    payload: DestinationUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update destination metadata, ceiling, or active status (Admin only)."""
    dest = DestinationService.update_destination(db, dest_id, payload, user_id=current_admin.id)
    return DestinationResponse.model_validate(dest)


@router.delete("/{dest_id}", response_model=AuthMessageResponse)
def delete_destination(
    dest_id: str,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Soft-disable destination (Admin only, Tier 2)."""
    dest = DestinationService.delete_destination(db, dest_id, user_id=current_admin.id)
    return AuthMessageResponse(message=f"Destination {dest.dest_id} soft-disabled successfully.")


@router.get("/{dest_id}/daily-metrics", response_model=DestinationDailyMetricsListResponse)
def get_destination_daily_metrics(
    dest_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    category: Optional[InventoryCategory] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Get time-series daily metrics for a destination."""
    metrics = DestinationService.get_daily_metrics(
        db, dest_id, category=category, start_date=start_date, end_date=end_date
    )
    return DestinationDailyMetricsListResponse(
        items=[DestinationDailyMetricResponse.model_validate(m) for m in metrics],
        total=len(metrics),
        dest_id=dest_id.upper(),
    )


@router.get("/{dest_id}/search-velocity", response_model=SearchVelocityResponse)
def get_destination_search_velocity(
    dest_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get 7d and 30d rolling search velocity aggregates (Tier 2)."""
    return DestinationService.get_search_velocity(db, dest_id)
