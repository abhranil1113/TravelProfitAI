from __future__ import annotations

from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.admin_config import (
    OptimizationConfigTemplateCreateRequest,
    OptimizationConfigTemplateResponse,
    OptimizationConfigTemplateUpdateRequest,
    PlatformConfigCreateRequest,
    PlatformConfigResponse,
    PlatformConfigUpdateRequest,
)
from backend.app.services.admin_config_service import AdminConfigService

router = APIRouter(prefix="/admin", tags=["11. Admin Config"])


# --- Platform Optimization Config (88-92) ---

# Note: Static sub-path '/platform-config/history' declared before parameterized paths
@router.get(
    "/platform-config/history",
    response_model=List[PlatformConfigResponse],
)
def list_platform_config_history(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """89. List all versioned platform optimization configurations."""
    return AdminConfigService.list_config_history(db)


@router.get(
    "/platform-config",
    response_model=PlatformConfigResponse,
)
def get_active_platform_config(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """88. Get current active platform optimization configuration profile."""
    return AdminConfigService.get_active_config(db)


@router.post(
    "/platform-config",
    response_model=PlatformConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_platform_config(
    req: PlatformConfigCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """90. Create a new draft platform optimization configuration profile."""
    return AdminConfigService.create_draft_config(db, req, current_user.id)


@router.patch(
    "/platform-config/{id}",
    response_model=PlatformConfigResponse,
)
def update_draft_platform_config(
    id: int,
    req: PlatformConfigUpdateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """91. Update draft platform optimization configuration profile."""
    return AdminConfigService.update_draft_config(db, id, req, current_user.id)


@router.post(
    "/platform-config/{id}/activate",
    response_model=PlatformConfigResponse,
)
def activate_platform_config(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """92. Atomically activate this profile and archive prior active profiles."""
    return AdminConfigService.activate_config(db, id, current_user.id)


# --- Optimization Config Templates (93-96) ---

@router.get(
    "/config-templates",
    response_model=List[OptimizationConfigTemplateResponse],
)
def list_config_templates(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """93. List all reusable optimization configuration templates."""
    return AdminConfigService.list_templates(db)


@router.post(
    "/config-templates",
    response_model=OptimizationConfigTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_config_template(
    req: OptimizationConfigTemplateCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """94. Create a new optimization configuration template."""
    return AdminConfigService.create_template(db, req, current_user.id)


@router.patch(
    "/config-templates/{id}",
    response_model=OptimizationConfigTemplateResponse,
)
def update_config_template(
    id: int,
    req: OptimizationConfigTemplateUpdateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """95. Update an optimization configuration template."""
    return AdminConfigService.update_template(db, id, req, current_user.id)


@router.delete(
    "/config-templates/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_config_template(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """96. Delete an unreferenced optimization configuration template."""
    AdminConfigService.delete_template(db, id, current_user.id)
    return None
