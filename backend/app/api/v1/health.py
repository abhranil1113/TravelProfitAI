from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.health import (
    ChampionModelHealthResponse,
    HealthResponse,
    ReadinessResponse,
    VersionResponse,
)
from backend.app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["22. Health & System"])


@router.get(
    "",
    response_model=HealthResponse,
)
def health_liveness():
    """168. Liveness probe for cluster orchestration and monitoring."""
    return HealthService.get_health()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
)
def health_readiness(
    db: Annotated[Session, Depends(get_db)],
):
    """169. Readiness probe verifying relational database and caching layer readiness."""
    return HealthService.check_readiness(db)


@router.get(
    "/version",
    response_model=VersionResponse,
)
def health_version():
    """170. System release version, build environment, and API specification level."""
    return HealthService.get_version_info()


@router.get(
    "/champion-models",
    response_model=ChampionModelHealthResponse,
)
def health_champion_models(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """171. Deployment health check for all champion machine learning models."""
    return HealthService.get_champion_models_health(db)
