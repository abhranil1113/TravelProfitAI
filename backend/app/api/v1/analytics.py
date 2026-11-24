from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.analytics import (
    CancellationPricingAnalyticsResponse,
    DashboardMetricsResponse,
    ProfitabilityAnalyticsResponse,
    SupplierScorecardResponse,
)
from backend.app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["19. Analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardMetricsResponse,
)
def get_dashboard_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """172. Global executive dashboard KPI overview."""
    return AnalyticsService.get_dashboard(db)


@router.get(
    "/profitability",
    response_model=ProfitabilityAnalyticsResponse,
)
def get_profitability_analytics(
    current_user: Annotated[User, Depends(require_roles(UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """173. Cross-sectional portfolio profitability breakdown by destination and supplier."""
    return AnalyticsService.get_profitability(db)


@router.get(
    "/cancellation-and-pricing",
    response_model=CancellationPricingAnalyticsResponse,
)
def get_cancellation_and_pricing_analytics(
    current_user: Annotated[User, Depends(require_roles(UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """174. Machine-learning cancellation risk and price elasticity analytics."""
    return AnalyticsService.get_cancellation_and_pricing(db)


@router.get(
    "/suppliers/scorecard",
    response_model=SupplierScorecardResponse,
)
def get_supplier_scorecard(
    current_user: Annotated[User, Depends(require_roles(UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """175. Comprehensive supplier performance and quality ranking scorecard."""
    return AnalyticsService.get_supplier_scorecard(db)
