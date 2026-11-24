from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends
from backend.app.dependencies import require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.economics import (
    EconomicsSimulateRequest,
    EconomicsSimulateResponse,
)
from backend.app.services.economics_service import EconomicsService

router = APIRouter(prefix="/economics", tags=["20. Economics"])


@router.post(
    "/simulate",
    response_model=EconomicsSimulateResponse,
)
def simulate_economics(
    req: EconomicsSimulateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
):
    """177. Stateless unit economic simulation factoring demand, cancellation risk, and salvage value."""
    return EconomicsService.simulate(req)
