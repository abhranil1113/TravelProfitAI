from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import RiskScenarioType, User, UserRole
from backend.app.schemas.risk import (
    PortfolioRiskSummaryResponse,
    RiskScenarioCreateRequest,
    RiskScenarioListResponse,
    RiskScenarioResponse,
    RiskScenarioUpdateRequest,
)
from backend.app.services.risk_service import RiskService

router = APIRouter(prefix="/risk", tags=["23. Portfolio Risk & Scenarios"])


@router.get("/scenarios", response_model=RiskScenarioListResponse)
def list_risk_scenarios(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    scenario_type: Optional[RiskScenarioType] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List risk scenarios with filtering and pagination."""
    items, total = RiskService.list_scenarios(
        db, scenario_type=scenario_type, is_active=is_active, page=page, page_size=page_size
    )
    return RiskScenarioListResponse(
        items=[RiskScenarioResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/scenarios", response_model=RiskScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_risk_scenario(
    req: RiskScenarioCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Configure a single-factor or correlated multivariate risk scenario (Admin only)."""
    scen = RiskService.create_scenario(db, req, user_id=current_admin.id)
    return RiskScenarioResponse.model_validate(scen)


@router.get("/scenarios/{scenario_id}", response_model=RiskScenarioResponse)
def get_risk_scenario(
    scenario_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get risk scenario definition."""
    return RiskScenarioResponse.model_validate(RiskService.get_scenario(db, scenario_id))


@router.patch("/scenarios/{scenario_id}", response_model=RiskScenarioResponse)
def update_risk_scenario(
    scenario_id: int,
    req: RiskScenarioUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update risk scenario configuration (Admin only)."""
    scen = RiskService.update_scenario(db, scenario_id, req, user_id=current_admin.id)
    return RiskScenarioResponse.model_validate(scen)


@router.delete("/scenarios/{scenario_id}", response_model=RiskScenarioResponse)
def delete_risk_scenario(
    scenario_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Soft-deactivate risk scenario (Admin only)."""
    scen = RiskService.delete_scenario(db, scenario_id, user_id=current_admin.id)
    return RiskScenarioResponse.model_validate(scen)


@router.get("/portfolio-summary", response_model=PortfolioRiskSummaryResponse)
def get_portfolio_risk_summary(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    run_id: Optional[str] = None,
):
    """Portfolio risk summary: VaR, CVaR, concentration HHI, availability & demand fulfillment."""
    return RiskService.get_portfolio_risk_summary(db, run_id=run_id)
