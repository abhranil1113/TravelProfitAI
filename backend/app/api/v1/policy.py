from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import (
    PolicyExceptionStatus,
    PolicyRuleStatus,
    PolicyScope,
    User,
    UserRole,
)
from backend.app.schemas.policy import (
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluationLogResponse,
    PolicyExceptionCreateRequest,
    PolicyExceptionDecisionRequest,
    PolicyExceptionResponse,
    PolicyRuleCreateRequest,
    PolicyRuleListResponse,
    PolicyRuleResponse,
    PolicyRuleUpdateRequest,
)
from backend.app.services.policy_service import PolicyService

router = APIRouter(prefix="/policy", tags=["27. Policy-as-Code Engine"])


@router.post("/rules", response_model=PolicyRuleResponse, status_code=status.HTTP_201_CREATED)
def create_policy_rule(
    req: PolicyRuleCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a declarative, versioned policy rule (Admin only)."""
    rule = PolicyService.create_rule(db, req, user_id=current_admin.id)
    return PolicyRuleResponse.model_validate(rule)


@router.get("/rules", response_model=PolicyRuleListResponse)
def list_policy_rules(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    scope: Optional[PolicyScope] = None,
    status_filter: Optional[PolicyRuleStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List policy rules and their versions."""
    items, total = PolicyService.list_rules(
        db, scope=scope, status=status_filter, page=page, page_size=page_size
    )
    return PolicyRuleListResponse(
        items=[PolicyRuleResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/rules/{rule_id}", response_model=PolicyRuleResponse)
def get_policy_rule(
    rule_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get policy rule details and version history."""
    return PolicyRuleResponse.model_validate(PolicyService.get_rule(db, rule_id))


@router.patch("/rules/{rule_id}", response_model=PolicyRuleResponse)
def update_policy_rule(
    rule_id: int,
    req: PolicyRuleUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update a policy rule and append a new immutable rule version if conditions change (Admin only)."""
    rule = PolicyService.update_rule(db, rule_id, req, user_id=current_admin.id)
    return PolicyRuleResponse.model_validate(rule)


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
def evaluate_policy_rules(
    req: PolicyEvaluateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Evaluate active policy rules for a given scope and context."""
    return PolicyService.evaluate_policies(db, req, user_id=current_user.id)


@router.get("/evaluations", response_model=List[PolicyEvaluationLogResponse])
def list_policy_evaluation_history(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    scope: Optional[PolicyScope] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    passed: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """View immutable policy evaluation history."""
    items = PolicyService.list_evaluation_logs(
        db, scope=scope, entity_type=entity_type, entity_id=entity_id, passed=passed, limit=limit
    )
    return [PolicyEvaluationLogResponse.model_validate(i) for i in items]


# --- Policy Exception Request Workflow ---

@router.post("/exceptions", response_model=PolicyExceptionResponse, status_code=status.HTTP_201_CREATED)
def submit_policy_exception(
    req: PolicyExceptionCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Submit a time-bound policy exception request (Admin & Procurement Manager only)."""
    exc = PolicyService.submit_exception(db, req, user_id=current_user.id)
    return PolicyExceptionResponse.model_validate(exc)


@router.get("/exceptions", response_model=List[PolicyExceptionResponse])
def list_policy_exceptions(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Optional[PolicyExceptionStatus] = Query(None, alias="status"),
):
    """List policy exception requests (Procurement Manager sees own submissions; Admin/Analyst see all)."""
    req_by = current_user.id if current_user.role == UserRole.PROCUREMENT_MANAGER else None
    items = PolicyService.list_exceptions(db, status=status_filter, requested_by_user_id=req_by)
    return [PolicyExceptionResponse.model_validate(i) for i in items]


@router.post("/exceptions/{exception_id}/approve", response_model=PolicyExceptionResponse)
def approve_policy_exception(
    exception_id: int,
    req: PolicyExceptionDecisionRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Approve a pending policy exception request (Admin only)."""
    exc = PolicyService.decide_exception(db, exception_id, approve=True, req=req, admin_user_id=current_admin.id)
    return PolicyExceptionResponse.model_validate(exc)


@router.post("/exceptions/{exception_id}/reject", response_model=PolicyExceptionResponse)
def reject_policy_exception(
    exception_id: int,
    req: PolicyExceptionDecisionRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Reject a pending policy exception request (Admin only)."""
    exc = PolicyService.decide_exception(db, exception_id, approve=False, req=req, admin_user_id=current_admin.id)
    return PolicyExceptionResponse.model_validate(exc)
