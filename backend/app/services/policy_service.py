from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PermissionDeniedError,
)
from backend.app.models.schema import (
    AuditLog,
    ComplianceAuditRecord,
    ComplianceAuditStatus,
    FXContractStatus,
    FXForwardContract,
    OptimizationRun,
    PolicyEvaluationLog,
    PolicyExceptionRequest,
    PolicyExceptionStatus,
    PolicyOutcome,
    PolicyRule,
    PolicyRuleStatus,
    PolicyRuleVersion,
    PolicyScope,
    PurchaseOrder,
    SupplierVerificationProfile,
    SupplierVerificationStatus,
)
from backend.app.schemas.policy import (
    ComplianceAuditTriggerRequest,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluationFinding,
    PolicyExceptionCreateRequest,
    PolicyExceptionDecisionRequest,
    PolicyRuleCreateRequest,
    PolicyRuleUpdateRequest,
    validate_condition_tree,
)

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _resolve_field(context: Dict[str, Any], path: str) -> Any:
    """Safely resolves a dotted field path from an evaluation context dictionary."""
    curr: Any = context
    for part in path.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


def _evaluate_condition_ast(node: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Deterministic, side-effect-free evaluator for declarative policy ASTs.
    Never invokes eval(), exec(), or dynamic SQL.
    """
    if "all" in node:
        return all(_evaluate_condition_ast(child, context) for child in node["all"])
    if "any" in node:
        return any(_evaluate_condition_ast(child, context) for child in node["any"])

    field_val = _resolve_field(context, node["field"])
    op = node["operator"]
    target = node["value"]

    if field_val is None:
        return False

    try:
        if op == "eq":
            return field_val == target
        if op == "neq":
            return field_val != target
        if op in ("gt", "gte", "lt", "lte"):
            if isinstance(field_val, bool) or isinstance(target, bool):
                return False
            fv = float(field_val)
            tv = float(target)
            if op == "gt":
                return fv > tv
            if op == "gte":
                return fv >= tv
            if op == "lt":
                return fv < tv
            return fv <= tv
        if op == "in":
            return field_val in target
        if op == "not_in":
            return field_val not in target
        if op == "between":
            if (
                not isinstance(target, (list, tuple))
                or len(target) != 2
                or isinstance(field_val, bool)
                or isinstance(target[0], bool)
                or isinstance(target[1], bool)
            ):
                return False
            lo, hi = float(target[0]), float(target[1])
            return lo <= float(field_val) <= hi
        if op == "contains":
            if isinstance(field_val, (list, tuple, set)):
                return target in field_val
            if isinstance(field_val, str):
                return str(target) in field_val
            return False
    except (TypeError, ValueError):
        return False
    return False


class PolicyService:
    """Service layer for Domain 5: Policy-as-Code & Compliance Engine."""

    @staticmethod
    def _hash_condition(cond: Dict[str, Any]) -> str:
        canonical = json.dumps(cond, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def create_rule(
        db: Session, req: PolicyRuleCreateRequest, user_id: int
    ) -> PolicyRule:
        existing = db.execute(
            select(PolicyRule).where(PolicyRule.rule_code == req.rule_code)
        ).scalar_one_or_none()
        if existing:
            raise ConflictException(f"Policy rule '{req.rule_code}' already exists.")

        validate_condition_tree(req.condition_json)
        rule = PolicyRule(
            rule_code=req.rule_code,
            name=req.name.strip(),
            description=req.description,
            scope=req.scope,
            outcome=req.outcome,
            priority=req.priority,
            status=PolicyRuleStatus.ACTIVE,
            active_version_number=1,
            created_by_user_id=user_id,
        )
        db.add(rule)
        db.flush()

        ver = PolicyRuleVersion(
            rule_id=rule.id,
            version_number=1,
            condition_json=req.condition_json,
            remediation_hint=req.remediation_hint,
            checksum_sha256=PolicyService._hash_condition(req.condition_json),
            created_by_user_id=user_id,
        )
        db.add(ver)
        db.add(AuditLog(
            user_id=user_id,
            action="POLICY_RULE_CREATED",
            entity_type="policy_rules",
            entity_id=rule.rule_code,
            new_value_json={"scope": rule.scope.value, "outcome": rule.outcome.value, "version": 1},
        ))
        db.commit()
        db.refresh(rule)
        return rule

    @staticmethod
    def update_rule(
        db: Session, rule_id: int, req: PolicyRuleUpdateRequest, user_id: int
    ) -> PolicyRule:
        rule = PolicyService.get_rule(db, rule_id)
        if req.name is not None:
            rule.name = req.name.strip()
        if req.description is not None:
            rule.description = req.description
        if req.outcome is not None:
            rule.outcome = req.outcome
        if req.priority is not None:
            rule.priority = req.priority
        if req.status is not None:
            rule.status = req.status

        if req.condition_json is not None:
            validate_condition_tree(req.condition_json)
            next_ver = rule.active_version_number + 1
            ver = PolicyRuleVersion(
                rule_id=rule.id,
                version_number=next_ver,
                condition_json=req.condition_json,
                remediation_hint=req.remediation_hint,
                checksum_sha256=PolicyService._hash_condition(req.condition_json),
                created_by_user_id=user_id,
            )
            db.add(ver)
            rule.active_version_number = next_ver

        db.add(AuditLog(
            user_id=user_id,
            action="POLICY_RULE_UPDATED",
            entity_type="policy_rules",
            entity_id=rule.rule_code,
            new_value_json={"active_version": rule.active_version_number, "status": rule.status.value},
        ))
        db.commit()
        db.refresh(rule)
        return rule

    @staticmethod
    def list_rules(
        db: Session,
        scope: Optional[PolicyScope] = None,
        status: Optional[PolicyRuleStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PolicyRule], int]:
        stmt = select(PolicyRule)
        if scope:
            stmt = stmt.where(PolicyRule.scope == scope)
        if status:
            stmt = stmt.where(PolicyRule.status == status)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            db.execute(
                stmt.order_by(PolicyRule.priority.asc(), PolicyRule.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return items, total

    @staticmethod
    def get_rule(db: Session, rule_id: int) -> PolicyRule:
        rule = db.execute(select(PolicyRule).where(PolicyRule.id == rule_id)).scalar_one_or_none()
        if not rule:
            raise EntityNotFoundError("PolicyRule", rule_id)
        return rule

    @staticmethod
    def evaluate_policies(
        db: Session,
        req: PolicyEvaluateRequest,
        user_id: Optional[int] = None,
        commit_logs: bool = True,
    ) -> PolicyEvaluateResponse:
        rules = list(
            db.execute(
                select(PolicyRule)
                .where(PolicyRule.scope == req.scope, PolicyRule.status == PolicyRuleStatus.ACTIVE)
                .order_by(PolicyRule.priority.asc(), PolicyRule.id.asc())
            ).scalars().all()
        )
        now = datetime.now(timezone.utc)
        findings: List[PolicyEvaluationFinding] = []
        blocking = 0
        warnings = 0
        infos = 0

        for rule in rules:
            ver = db.execute(
                select(PolicyRuleVersion).where(
                    PolicyRuleVersion.rule_id == rule.id,
                    PolicyRuleVersion.version_number == rule.active_version_number,
                )
            ).scalar_one_or_none()
            if not ver:
                continue

            triggered = _evaluate_condition_ast(ver.condition_json, req.context)
            exception_applied_id: Optional[int] = None
            passed = True
            detail = f"Rule '{rule.rule_code}' v{ver.version_number} did not trigger."

            if triggered:
                if rule.outcome == PolicyOutcome.BLOCK:
                    # Check for valid, approved, unexpired exception for this exact entity
                    exc = db.execute(
                        select(PolicyExceptionRequest).where(
                            PolicyExceptionRequest.rule_id == rule.id,
                            PolicyExceptionRequest.entity_type == req.entity_type,
                            PolicyExceptionRequest.entity_id == req.entity_id,
                            PolicyExceptionRequest.status == PolicyExceptionStatus.APPROVED,
                            PolicyExceptionRequest.expires_at > now,
                        ).order_by(PolicyExceptionRequest.reviewed_at.desc())
                    ).scalars().first()
                    if exc:
                        passed = True
                        exception_applied_id = exc.id
                        detail = (
                            f"Rule '{rule.rule_code}' triggered BLOCK, waived by approved exception {exc.exception_uid}."
                        )
                    else:
                        passed = False
                        blocking += 1
                        detail = f"Policy BLOCK violation on '{rule.rule_code}' ({rule.name})."
                elif rule.outcome == PolicyOutcome.WARN:
                    passed = True
                    warnings += 1
                    detail = f"Policy WARN triggered on '{rule.rule_code}' ({rule.name})."
                else:
                    passed = True
                    infos += 1
                    detail = f"Policy INFO triggered on '{rule.rule_code}' ({rule.name})."

            findings.append(PolicyEvaluationFinding(
                rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_version=ver.version_number,
                outcome=rule.outcome,
                triggered=triggered,
                passed=passed,
                exception_applied_id=exception_applied_id,
                detail=detail,
                remediation_hint=ver.remediation_hint,
            ))

            if req.persist_history:
                db.add(PolicyEvaluationLog(
                    rule_id=rule.id,
                    rule_code=rule.rule_code,
                    rule_version=ver.version_number,
                    scope=req.scope,
                    entity_type=req.entity_type,
                    entity_id=req.entity_id,
                    outcome=rule.outcome,
                    passed=passed,
                    exception_applied_id=exception_applied_id,
                    input_context_json=req.context,
                    evaluation_detail=detail,
                    evaluated_by_user_id=user_id,
                    evaluated_at=now,
                ))

        if req.persist_history and commit_logs and rules:
            db.commit()

        return PolicyEvaluateResponse(
            scope=req.scope,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            allowed=(blocking == 0),
            blocking_violations=blocking,
            warnings_count=warnings,
            info_count=infos,
            findings=findings,
        )

    @staticmethod
    def enforce_workflow_policies(
        db: Session,
        scope: PolicyScope,
        entity_type: str,
        entity_id: str,
        context: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> PolicyEvaluateResponse:
        """
        Called inside business workflows (optimization, recommendation approval, PO creation, FX execution).
        Persists immutable evaluation history and raises PermissionDeniedError (403) / BadRequestException
        when any BLOCK rule is violated without an approved exception.
        """
        req_eval = PolicyEvaluateRequest(
            scope=scope,
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
            persist_history=True,
        )
        res = PolicyService.evaluate_policies(
            db,
            req_eval,
            user_id=user_id,
            commit_logs=False,
        )
        if not res.allowed:
            # Roll back uncommitted caller mutations before committing immutable violation logs
            db.rollback()
            PolicyService.evaluate_policies(
                db,
                req_eval,
                user_id=user_id,
                commit_logs=True,
            )
            blocked_codes = [f.rule_code for f in res.findings if not f.passed]
            raise PermissionDeniedError(
                f"Blocked by active policy rules {blocked_codes} in scope {scope.value}."
            )
        return res

    @staticmethod
    def list_evaluation_logs(
        db: Session,
        scope: Optional[PolicyScope] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        passed: Optional[bool] = None,
        limit: int = 100,
    ) -> List[PolicyEvaluationLog]:
        stmt = select(PolicyEvaluationLog)
        if scope:
            stmt = stmt.where(PolicyEvaluationLog.scope == scope)
        if entity_type:
            stmt = stmt.where(PolicyEvaluationLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(PolicyEvaluationLog.entity_id == entity_id)
        if passed is not None:
            stmt = stmt.where(PolicyEvaluationLog.passed == passed)
        return list(
            db.execute(stmt.order_by(PolicyEvaluationLog.evaluated_at.desc()).limit(limit)).scalars().all()
        )

    # --- Exception Request Workflow ---

    @staticmethod
    def submit_exception(
        db: Session, req: PolicyExceptionCreateRequest, user_id: int
    ) -> PolicyExceptionRequest:
        rule = PolicyService.get_rule(db, req.rule_id)
        now = datetime.now(timezone.utc)
        exp = _ensure_utc(req.expires_at)
        if exp <= now:
            raise BadRequestException("Exception expires_at must be in the future.")

        exc = PolicyExceptionRequest(
            rule_id=rule.id,
            entity_type=req.entity_type.strip(),
            entity_id=req.entity_id.strip(),
            justification=req.justification.strip(),
            status=PolicyExceptionStatus.PENDING,
            requested_by_user_id=user_id,
            expires_at=exp,
        )
        db.add(exc)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="POLICY_EXCEPTION_SUBMITTED",
            entity_type="policy_exception_requests",
            entity_id=exc.exception_uid,
            new_value_json={"rule_code": rule.rule_code, "entity": f"{exc.entity_type}:{exc.entity_id}"},
        ))
        db.commit()
        db.refresh(exc)
        return exc

    @staticmethod
    def decide_exception(
        db: Session,
        exception_id: int,
        approve: bool,
        req: PolicyExceptionDecisionRequest,
        admin_user_id: int,
    ) -> PolicyExceptionRequest:
        exc = db.execute(
            select(PolicyExceptionRequest).where(PolicyExceptionRequest.id == exception_id).with_for_update()
        ).scalar_one_or_none()
        if not exc:
            raise EntityNotFoundError("PolicyExceptionRequest", exception_id)
        if exc.status != PolicyExceptionStatus.PENDING:
            target_st = PolicyExceptionStatus.APPROVED if approve else PolicyExceptionStatus.REJECTED
            raise InvalidStateTransitionError(exc.status.value, target_st.value)
        if approve and exc.requested_by_user_id == admin_user_id:
            raise PermissionDeniedError(
                "Separation of duties violation: exception requester cannot approve their own request."
            )

        exc.status = PolicyExceptionStatus.APPROVED if approve else PolicyExceptionStatus.REJECTED
        exc.reviewed_by_user_id = admin_user_id
        exc.reviewed_at = datetime.now(timezone.utc)
        exc.review_notes = req.review_notes.strip()

        db.add(AuditLog(
            user_id=admin_user_id,
            action="POLICY_EXCEPTION_APPROVED" if approve else "POLICY_EXCEPTION_REJECTED",
            entity_type="policy_exception_requests",
            entity_id=exc.exception_uid,
            new_value_json={"status": exc.status.value, "review_notes": exc.review_notes},
        ))
        db.commit()
        db.refresh(exc)
        return exc

    @staticmethod
    def list_exceptions(
        db: Session,
        status: Optional[PolicyExceptionStatus] = None,
        requested_by_user_id: Optional[int] = None,
    ) -> List[PolicyExceptionRequest]:
        stmt = select(PolicyExceptionRequest)
        if status:
            stmt = stmt.where(PolicyExceptionRequest.status == status)
        if requested_by_user_id is not None:
            stmt = stmt.where(PolicyExceptionRequest.requested_by_user_id == requested_by_user_id)
        return list(db.execute(stmt.order_by(PolicyExceptionRequest.created_at.desc())).scalars().all())

    # --- Compliance Audits ---

    @staticmethod
    def run_compliance_audit(
        db: Session, req: ComplianceAuditTriggerRequest, admin_user_id: int
    ) -> ComplianceAuditRecord:
        now = datetime.now(timezone.utc)
        scope = req.audit_scope.strip().upper()
        findings: List[Dict[str, Any]] = []
        total_checks = 0
        passed_checks = 0
        blocked_count = 0
        warnings_count = 0

        # 1. Check PolicyEvaluationLog violations
        eval_logs = list(db.execute(select(PolicyEvaluationLog)).scalars().all())
        for ev in eval_logs:
            total_checks += 1
            if ev.passed:
                passed_checks += 1
                if ev.outcome == PolicyOutcome.WARN and "triggered WARN" in ev.evaluation_detail:
                    warnings_count += 1
            else:
                blocked_count += 1
                findings.append({
                    "category": "POLICY_VIOLATION",
                    "rule_code": ev.rule_code,
                    "entity": f"{ev.entity_type}:{ev.entity_id}",
                    "detail": ev.evaluation_detail,
                })

        # 2. Check Purchase Orders for unlinked budgets or suspended suppliers
        if scope in ("ALL", "PROCUREMENT"):
            pos = list(db.execute(select(PurchaseOrder)).scalars().all())
            for po in pos:
                total_checks += 1
                prof = db.execute(
                    select(SupplierVerificationProfile).where(
                        SupplierVerificationProfile.supplier_id == po.supplier_id
                    )
                ).scalar_one_or_none()
                if prof and prof.verification_status == SupplierVerificationStatus.SUSPENDED:
                    blocked_count += 1
                    findings.append({
                        "category": "SUSPENDED_SUPPLIER_PO",
                        "entity": f"purchase_orders:{po.po_number}",
                        "detail": f"PO {po.po_number} references suspended supplier {po.supplier_id}.",
                    })
                else:
                    passed_checks += 1

        # 3. Check FX Forward Contracts for unexecuted drafts past trade date
        if scope in ("ALL", "TREASURY"):
            fx_contracts = list(db.execute(select(FXForwardContract)).scalars().all())
            for fx in fx_contracts:
                total_checks += 1
                if fx.status == FXContractStatus.DRAFT and fx.trade_date < now.date():
                    warnings_count += 1
                    findings.append({
                        "category": "STALE_FX_DRAFT",
                        "entity": f"fx_forward_contracts:{fx.contract_number}",
                        "detail": f"FX forward {fx.contract_number} remains DRAFT past trade_date {fx.trade_date}.",
                    })
                else:
                    passed_checks += 1

        active_excs = db.execute(
            select(func.count(PolicyExceptionRequest.id)).where(
                PolicyExceptionRequest.status == PolicyExceptionStatus.APPROVED,
                PolicyExceptionRequest.expires_at > now,
            )
        ).scalar_one()

        record = ComplianceAuditRecord(
            audit_scope=scope,
            status=ComplianceAuditStatus.COMPLETED,
            total_checks=total_checks,
            passed_checks=passed_checks,
            blocked_violations=blocked_count,
            warnings_count=warnings_count,
            active_exceptions_count=active_excs,
            findings_json=findings,
            triggered_by_user_id=admin_user_id,
            completed_at=now,
        )
        db.add(record)
        db.flush()
        db.add(AuditLog(
            user_id=admin_user_id,
            action="COMPLIANCE_AUDIT_COMPLETED",
            entity_type="compliance_audit_records",
            entity_id=record.audit_uid,
            new_value_json={"total_checks": total_checks, "blocked": blocked_count, "warnings": warnings_count},
        ))
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def list_compliance_audits(db: Session) -> List[ComplianceAuditRecord]:
        return list(
            db.execute(select(ComplianceAuditRecord).order_by(ComplianceAuditRecord.created_at.desc())).scalars().all()
        )
