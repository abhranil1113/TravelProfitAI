from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["21. Audit Logs"])


@router.get(
    "",
    response_model=AuditLogListResponse,
)
def list_audit_logs(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """166. Search and review immutable system security audit logs."""
    items, total = AuditService.list_audit_logs(db, entity_type=entity_type, action=action, user_id=user_id, page=page, page_size=page_size)
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{id}",
    response_model=AuditLogResponse,
)
def get_audit_log_entry(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """167. Get detailed single audit log record with state changes."""
    log = AuditService.get_audit_log(db, id)
    return AuditLogResponse.model_validate(log)
