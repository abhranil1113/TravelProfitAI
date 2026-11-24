from __future__ import annotations

from datetime import date
from typing import Annotated, Optional, Union
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles, require_worker_token
from backend.app.models.schema import InventoryCategory, User, UserRole
from backend.app.schemas.search_event import (
    BulkSearchEventIngestRequest,
    BulkSearchEventIngestResponse,
    CustomerSearchEventCreateRequest,
    CustomerSearchEventListResponse,
    CustomerSearchEventResponse,
    FunnelAnalyticsResponse,
    VelocityAnalyticsResponse,
)
from backend.app.services.search_event_service import SearchEventService

router = APIRouter(prefix="/search-events", tags=["18. Search Events"])


@router.get("/analytics/funnel", response_model=FunnelAnalyticsResponse)
def get_search_funnel_analytics(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dest: Optional[str] = None,
    category: Optional[InventoryCategory] = None,
):
    """Customer search-to-book conversion funnel analytics (Tier 2)."""
    return SearchEventService.get_funnel_analytics(
        db, start_date=start_date, end_date=end_date, dest_id=dest, category=category
    )


@router.get("/analytics/velocity", response_model=VelocityAnalyticsResponse)
def get_search_velocity_analytics(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Rolling search demand velocity across all active destinations (Tier 2)."""
    return SearchEventService.get_velocity_analytics(db)


@router.post("/bulk", response_model=BulkSearchEventIngestResponse, status_code=status.HTTP_201_CREATED)
def bulk_ingest_search_events(
    payload: Union[BulkSearchEventIngestRequest, list[CustomerSearchEventCreateRequest]],
    worker_token: Annotated[str, Depends(require_worker_token)],
    db: Annotated[Session, Depends(get_db)],
):
    """High-throughput bulk ingestion of search events (Worker X-Worker-Token auth only, Tier 2)."""
    event_list = payload.events if isinstance(payload, BulkSearchEventIngestRequest) else payload
    return SearchEventService.bulk_ingest_search_events(db, event_list)


@router.get("", response_model=CustomerSearchEventListResponse)
def list_search_events(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    dest: Optional[str] = None,
    category: Optional[InventoryCategory] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List raw customer search events with multi-criteria filtering (Tier 2)."""
    items, total = SearchEventService.list_search_events(
        db, dest_id=dest, category=category, start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )
    return CustomerSearchEventListResponse(
        items=[CustomerSearchEventResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )
