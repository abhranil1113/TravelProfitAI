from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.models.schema import (
    ComplianceAuditStatus,
    PolicyExceptionStatus,
    PolicyOutcome,
    PolicyRuleStatus,
    PolicyScope,
)


# =============================================================================
# DOMAIN 5: POLICY-AS-CODE & COMPLIANCE ENGINE
# =============================================================================

ALLOWED_POLICY_OPERATORS = frozenset({
    "eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "between", "contains",
})


def validate_condition_tree(node: Any, depth: int = 0) -> None:
    """Strictly validates declarative JSON policy AST. Never permits arbitrary code or SQL."""
    if depth > 8:
        raise ValueError("Policy condition tree exceeds maximum nesting depth of 8.")
    if not isinstance(node, dict):
        raise ValueError("Policy condition node must be a dictionary.")

    if "all" in node:
        children = node["all"]
        if not isinstance(children, list) or not children:
            raise ValueError("'all' group must be a non-empty list.")
        for child in children:
            validate_condition_tree(child, depth + 1)
        return

    if "any" in node:
        children = node["any"]
        if not isinstance(children, list) or not children:
            raise ValueError("'any' group must be a non-empty list.")
        for child in children:
            validate_condition_tree(child, depth + 1)
        return

    field = node.get("field")
    op = node.get("operator")
    if not isinstance(field, str) or not field.strip():
        raise ValueError("Leaf condition must specify a non-empty 'field' string.")
    if not all(c.isalnum() or c in "._" for c in field):
        raise ValueError(f"Invalid characters in policy field name '{field}'.")
    if op not in ALLOWED_POLICY_OPERATORS:
        raise ValueError(f"Unsupported policy operator '{op}'. Allowed: {sorted(ALLOWED_POLICY_OPERATORS)}.")
    if "value" not in node:
        raise ValueError("Leaf condition must specify 'value'.")
    if op == "between":
        val = node["value"]
        if not isinstance(val, (list, tuple)) or len(val) != 2:
            raise ValueError("'between' operator requires a 2-element [min, max] list.")
    if op in ("in", "not_in") and not isinstance(node["value"], list):
        raise ValueError(f"'{op}' operator requires a list value.")


class PolicyRuleCreateRequest(BaseModel):
    rule_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    scope: PolicyScope
    outcome: PolicyOutcome = PolicyOutcome.BLOCK
    priority: int = Field(100, ge=1, le=10000)
    condition_json: Dict[str, Any]
    remediation_hint: Optional[str] = Field(None, max_length=1000)

    @field_validator("rule_code")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("condition_json")
    @classmethod
    def check_ast(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        validate_condition_tree(v)
        return v


class PolicyRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    outcome: Optional[PolicyOutcome] = None
    priority: Optional[int] = Field(None, ge=1, le=10000)
    status: Optional[PolicyRuleStatus] = None
    condition_json: Optional[Dict[str, Any]] = None
    remediation_hint: Optional[str] = Field(None, max_length=1000)

    @field_validator("condition_json")
    @classmethod
    def check_ast(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None:
            validate_condition_tree(v)
        return v


class PolicyRuleVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    version_number: int
    condition_json: Dict[str, Any]
    remediation_hint: Optional[str] = None
    checksum_sha256: str
    created_by_user_id: Optional[int] = None
    created_at: datetime


class PolicyRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_code: str
    name: str
    description: Optional[str] = None
    scope: PolicyScope
    outcome: PolicyOutcome
    priority: int
    status: PolicyRuleStatus
    active_version_number: int
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    versions: List[PolicyRuleVersionResponse] = Field(default_factory=list)


class PolicyRuleListResponse(BaseModel):
    items: List[PolicyRuleResponse]
    total: int
    page: int
    page_size: int


class PolicyEvaluateRequest(BaseModel):
    scope: PolicyScope
    entity_type: str = Field(..., min_length=2, max_length=64)
    entity_id: str = Field(..., min_length=1, max_length=64)
    context: Dict[str, Any] = Field(default_factory=dict)
    persist_history: bool = True


class PolicyEvaluationFinding(BaseModel):
    rule_id: int
    rule_code: str
    rule_version: int
    outcome: PolicyOutcome
    triggered: bool
    passed: bool
    exception_applied_id: Optional[int] = None
    detail: str
    remediation_hint: Optional[str] = None


class PolicyEvaluateResponse(BaseModel):
    scope: PolicyScope
    entity_type: str
    entity_id: str
    allowed: bool
    blocking_violations: int
    warnings_count: int
    info_count: int
    findings: List[PolicyEvaluationFinding]


class PolicyEvaluationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_uid: str
    rule_id: Optional[int] = None
    rule_code: str
    rule_version: int
    scope: PolicyScope
    entity_type: str
    entity_id: str
    outcome: PolicyOutcome
    passed: bool
    exception_applied_id: Optional[int] = None
    input_context_json: Dict[str, Any] = Field(default_factory=dict)
    evaluation_detail: str
    evaluated_by_user_id: Optional[int] = None
    evaluated_at: datetime


class PolicyExceptionCreateRequest(BaseModel):
    rule_id: int = Field(..., ge=1)
    entity_type: str = Field(..., min_length=2, max_length=64)
    entity_id: str = Field(..., min_length=1, max_length=64)
    justification: str = Field(..., min_length=10, max_length=2000)
    expires_at: datetime


class PolicyExceptionDecisionRequest(BaseModel):
    review_notes: str = Field(..., min_length=3, max_length=1000)


class PolicyExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exception_uid: str
    rule_id: int
    entity_type: str
    entity_id: str
    justification: str
    status: PolicyExceptionStatus
    requested_by_user_id: int
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ComplianceAuditTriggerRequest(BaseModel):
    audit_scope: str = Field("ALL", min_length=2, max_length=64)


class ComplianceAuditRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audit_uid: str
    audit_scope: str
    status: ComplianceAuditStatus
    total_checks: int
    passed_checks: int
    blocked_violations: int
    warnings_count: int
    active_exceptions_count: int
    findings_json: List[Dict[str, Any]] = Field(default_factory=list)
    triggered_by_user_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
