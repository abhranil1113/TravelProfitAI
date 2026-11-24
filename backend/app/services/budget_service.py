from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from backend.app.models.schema import (
    AuditLog,
    BudgetLedgerEntry,
    BudgetPeriodType,
    BudgetScope,
    BudgetStatus,
    BudgetTransactionType,
    ProcurementBudget,
)
from backend.app.schemas.budget import (
    BudgetAdjustRequest,
    BudgetCreateRequest,
    BudgetUpdateRequest,
    BudgetUtilizationResponse,
)


class BudgetService:

    @staticmethod
    def _compute_available(budget: ProcurementBudget) -> Decimal:
        return budget.total_amount_inr - budget.spent_amount_inr - budget.reserved_amount_inr

    @staticmethod
    def list_budgets(
        db: Session,
        scope: Optional[BudgetScope] = None,
        status: Optional[BudgetStatus] = None,
        period: Optional[str] = None,
    ) -> List[ProcurementBudget]:
        stmt = select(ProcurementBudget)
        if scope:
            stmt = stmt.where(ProcurementBudget.scope == scope)
        if status:
            stmt = stmt.where(ProcurementBudget.status == status)
        if period:
            try:
                period_enum = BudgetPeriodType(period.upper())
                stmt = stmt.where(ProcurementBudget.period_type == period_enum)
            except ValueError:
                pass

        stmt = stmt.order_by(ProcurementBudget.created_at.desc())
        budgets = list(db.execute(stmt).scalars().all())
        for b in budgets:
            b.available_amount_inr = BudgetService._compute_available(b)
        return budgets

    @staticmethod
    def create_budget(
        db: Session,
        req: BudgetCreateRequest,
        user_id: int,
    ) -> ProcurementBudget:
        existing = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.budget_code == req.budget_code)
        ).scalar_one_or_none()

        if existing:
            raise ConflictException(f"Budget with code '{req.budget_code}' already exists")

        budget = ProcurementBudget(
            budget_code=req.budget_code,
            name=req.name,
            scope=req.scope,
            scope_dest_id=req.scope_dest_id,
            period_type=req.period_type,
            period_start=req.period_start,
            period_end=req.period_end,
            total_amount_inr=req.total_amount_inr,
            spent_amount_inr=Decimal("0.00"),
            reserved_amount_inr=Decimal("0.00"),
            status=BudgetStatus.DRAFT,
            created_by_user_id=user_id,
            notes=req.notes,
        )
        db.add(budget)
        db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="PROCUREMENT_BUDGET",
            entity_id=str(budget.id),
            details_json={"budget_code": budget.budget_code, "total_amount_inr": str(budget.total_amount_inr)},
        )
        db.add(audit)
        db.commit()
        db.refresh(budget)
        budget.available_amount_inr = BudgetService._compute_available(budget)
        return budget

    @staticmethod
    def get_budget_by_id(db: Session, budget_id: int) -> ProcurementBudget:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        budget.available_amount_inr = BudgetService._compute_available(budget)
        return budget

    @staticmethod
    def update_draft_budget(
        db: Session,
        budget_id: int,
        req: BudgetUpdateRequest,
        user_id: int,
    ) -> ProcurementBudget:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        if budget.status != BudgetStatus.DRAFT:
            raise BadRequestException(f"Cannot edit budget in status '{budget.status.value}'. Only DRAFT can be edited.")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(budget, field, value)

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="PROCUREMENT_BUDGET",
            entity_id=str(budget.id),
            details_json={k: str(v) if isinstance(v, Decimal) else v for k, v in update_data.items()},
        )
        db.add(audit)
        db.commit()
        db.refresh(budget)
        budget.available_amount_inr = BudgetService._compute_available(budget)
        return budget

    @staticmethod
    def activate_budget(db: Session, budget_id: int, user_id: int) -> ProcurementBudget:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        if budget.status != BudgetStatus.DRAFT:
            raise BadRequestException(f"Cannot activate budget in status '{budget.status.value}'. Must be DRAFT.")

        budget.status = BudgetStatus.ACTIVE

        # Create initial allocation ledger entry
        ledger_entry = BudgetLedgerEntry(
            budget_id=budget.id,
            transaction_type=BudgetTransactionType.ALLOCATION,
            amount_inr=budget.total_amount_inr,
            previous_balance_inr=Decimal("0.00"),
            new_balance_inr=budget.total_amount_inr,
            created_by_user_id=user_id,
            description="Initial budget envelope activation",
        )
        db.add(ledger_entry)

        audit = AuditLog(
            user_id=user_id,
            action="ACTIVATE",
            entity_type="PROCUREMENT_BUDGET",
            entity_id=str(budget.id),
            details_json={"status": BudgetStatus.ACTIVE.value},
        )
        db.add(audit)
        db.commit()
        db.refresh(budget)
        budget.available_amount_inr = BudgetService._compute_available(budget)
        return budget

    @staticmethod
    def close_budget(db: Session, budget_id: int, user_id: int) -> ProcurementBudget:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        if budget.status != BudgetStatus.ACTIVE:
            raise BadRequestException(f"Cannot close budget in status '{budget.status.value}'. Must be ACTIVE.")

        if budget.reserved_amount_inr > 0:
            raise BadRequestException(
                f"Cannot close budget with pending reservations (reserved INR {budget.reserved_amount_inr}). Release or commit them first."
            )

        budget.status = BudgetStatus.CLOSED
        audit = AuditLog(
            user_id=user_id,
            action="CLOSE",
            entity_type="PROCUREMENT_BUDGET",
            entity_id=str(budget.id),
            details_json={"status": BudgetStatus.CLOSED.value},
        )
        db.add(audit)
        db.commit()
        db.refresh(budget)
        budget.available_amount_inr = BudgetService._compute_available(budget)
        return budget

    @staticmethod
    def adjust_budget(
        db: Session,
        budget_id: int,
        req: BudgetAdjustRequest,
        user_id: int,
    ) -> ProcurementBudget:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        if budget.status != BudgetStatus.ACTIVE:
            raise BadRequestException(f"Cannot adjust budget in status '{budget.status.value}'. Must be ACTIVE.")

        if req.idempotency_key:
            existing_ledger = db.execute(
                select(BudgetLedgerEntry).where(
                    BudgetLedgerEntry.budget_id == budget_id,
                    BudgetLedgerEntry.idempotency_key == req.idempotency_key,
                )
            ).scalar_one_or_none()
            if existing_ledger:
                budget.available_amount_inr = BudgetService._compute_available(budget)
                return budget

        prev_total = budget.total_amount_inr
        new_total = prev_total + req.amount_inr

        if new_total < (budget.spent_amount_inr + budget.reserved_amount_inr):
            raise BadRequestException(
                f"Budget reduction of INR {req.amount_inr} would bring total ({new_total}) below committed and reserved amount ({budget.spent_amount_inr + budget.reserved_amount_inr})"
            )

        budget.total_amount_inr = new_total

        ledger_entry = BudgetLedgerEntry(
            budget_id=budget.id,
            idempotency_key=req.idempotency_key,
            transaction_type=BudgetTransactionType.MANUAL_ADJUSTMENT,
            amount_inr=req.amount_inr,
            previous_balance_inr=prev_total,
            new_balance_inr=new_total,
            created_by_user_id=user_id,
            description=req.description,
        )
        db.add(ledger_entry)

        audit = AuditLog(
            user_id=user_id,
            action="ADJUST",
            entity_type="PROCUREMENT_BUDGET",
            entity_id=str(budget.id),
            details_json={
                "previous_total": str(prev_total),
                "amount": str(req.amount_inr),
                "new_total": str(new_total),
                "reason": req.description,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(budget)
        budget.available_amount_inr = BudgetService._compute_available(budget)
        return budget

    @staticmethod
    def list_ledger_entries(db: Session, budget_id: int) -> List[BudgetLedgerEntry]:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        stmt = select(BudgetLedgerEntry).where(
            BudgetLedgerEntry.budget_id == budget_id
        ).order_by(BudgetLedgerEntry.created_at.desc(), BudgetLedgerEntry.id.desc())

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_budget_utilization(db: Session, budget_id: int) -> BudgetUtilizationResponse:
        budget = db.execute(
            select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
        ).scalar_one_or_none()

        if not budget:
            raise NotFoundException(f"Budget {budget_id} not found")

        available = BudgetService._compute_available(budget)
        rate = float((budget.spent_amount_inr + budget.reserved_amount_inr) / budget.total_amount_inr) if budget.total_amount_inr > 0 else 0.0

        return BudgetUtilizationResponse(
            budget_id=budget.id,
            budget_code=budget.budget_code,
            name=budget.name,
            total_amount_inr=budget.total_amount_inr,
            spent_amount_inr=budget.spent_amount_inr,
            reserved_amount_inr=budget.reserved_amount_inr,
            available_amount_inr=available,
            utilization_rate=round(rate, 4),
            status=budget.status,
        )
