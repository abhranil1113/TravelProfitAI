from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import (
    BudgetScope,
    BudgetStatus,
    User,
    UserRole,
)
from backend.app.schemas.budget import (
    BudgetAdjustRequest,
    BudgetCreateRequest,
    BudgetLedgerEntryResponse,
    BudgetResponse,
    BudgetUpdateRequest,
    BudgetUtilizationResponse,
)
from backend.app.services.budget_service import BudgetService

router = APIRouter(prefix="/budgets", tags=["12. Budgets & Ledger"])


@router.get(
    "",
    response_model=List[BudgetResponse],
)
def list_budgets(
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    scope: Optional[BudgetScope] = None,
    budget_status: Optional[BudgetStatus] = Query(None, alias="status"),
    period: Optional[str] = None,
):
    """97. List procurement budget envelopes with filters."""
    return BudgetService.list_budgets(db, scope=scope, status=budget_status, period=period)


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    req: BudgetCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """98. Create a new procurement budget envelope."""
    return BudgetService.create_budget(db, req, current_user.id)


@router.get(
    "/{id}",
    response_model=BudgetResponse,
)
def get_budget(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """99. Get detailed budget envelope with current spent and reserved amounts."""
    return BudgetService.get_budget_by_id(db, id)


@router.patch(
    "/{id}",
    response_model=BudgetResponse,
)
def update_draft_budget(
    id: int,
    req: BudgetUpdateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """100. Update a procurement budget in DRAFT status."""
    return BudgetService.update_draft_budget(db, id, req, current_user.id)


@router.post(
    "/{id}/activate",
    response_model=BudgetResponse,
)
def activate_budget(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """101. Transition budget envelope from DRAFT to ACTIVE."""
    return BudgetService.activate_budget(db, id, current_user.id)


@router.post(
    "/{id}/close",
    response_model=BudgetResponse,
)
def close_budget(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """102. Close an active budget envelope (must have zero uncommitted reservations)."""
    return BudgetService.close_budget(db, id, current_user.id)


@router.post(
    "/{id}/adjust",
    response_model=BudgetResponse,
)
def adjust_budget(
    id: int,
    req: BudgetAdjustRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """103. Manually adjust budget envelope with append-only ledger audit trail."""
    return BudgetService.adjust_budget(db, id, req, current_user.id)


@router.get(
    "/{id}/ledger",
    response_model=List[BudgetLedgerEntryResponse],
)
def list_budget_ledger_entries(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """104. List immutable, append-only ledger entries for a budget envelope."""
    return BudgetService.list_ledger_entries(db, id)


@router.get(
    "/{id}/utilization",
    response_model=BudgetUtilizationResponse,
)
def get_budget_utilization(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """105. Get detailed utilization breakdown (reserved vs spent vs available)."""
    return BudgetService.get_budget_utilization(db, id)
