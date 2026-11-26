from __future__ import annotations

from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import User, UserRole
from backend.app.schemas.policy import (
    ComplianceAuditRecordResponse,
    ComplianceAuditTriggerRequest,
)
from backend.app.services.policy_service import PolicyService

router = APIRouter(prefix="/compliance", tags=["28. Compliance Audits"])


@router.post("/audits", response_model=ComplianceAuditRecordResponse, status_code=status.HTTP_201_CREATED)
def run_compliance_audit(
    req: ComplianceAuditTriggerRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Run an end-to-end compliance audit across policies, procurement, and FX (Admin only)."""
    rec = PolicyService.run_compliance_audit(db, req, admin_user_id=current_admin.id)
    return ComplianceAuditRecordResponse.model_validate(rec)


@router.get("/audits", response_model=List[ComplianceAuditRecordResponse])
def list_compliance_audits(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """View compliance audit results."""
    items = PolicyService.list_compliance_audits(db)
    return [ComplianceAuditRecordResponse.model_validate(i) for i in items]
