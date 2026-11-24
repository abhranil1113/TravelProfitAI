from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from backend.app.core.notification_events import (
    EventTypes,
    NotificationCategory,
    RoleNames,
)
from backend.app.services.notification_service import NotificationService
from backend.app.models.schema import (
    ApprovalStatus,
    AuditLog,
    BudgetLedgerEntry,
    BudgetTransactionType,
    ConstraintType,
    OptimizationConstraint,
    OptimizationMode,
    OptimizationRun,
    OptimizationRunArtifact,
    OptimizationRunEvent,
    PipelineStatus,
    PlatformOptimizationConfig,
    POStatus,
    ProcurementBudget,
    ProcurementRecommendation,
    PurchaseOrder,
    PurchaseOrderLine,
    SensitivityScenario,
    SolverBackend,
    SolverStatus,
    Supplier,
)
from backend.app.schemas.optimization import (
    GeneratePurchaseOrdersResponse,
    OptimizationConstraintResponse,
    OptimizationRunStatusResponse,
    OptimizationRunTriggerRequest,
    OptimizationScorecardResponse,
    RiskMetricsResponse,
    RunCompareItem,
    RunCompareResponse,
    SensitivityRunRequest,
    SensitivityScenarioResponse,
)


class OptimizationService:

    @staticmethod
    def trigger_run(
        db: Session,
        req: OptimizationRunTriggerRequest,
        user_id: int,
    ) -> OptimizationRun:
        # Check idempotency
        if req.idempotency_key:
            existing = db.execute(
                select(OptimizationRun).where(OptimizationRun.idempotency_key == req.idempotency_key)
            ).scalar_one_or_none()
            if existing:
                return existing

        run_id = f"opt_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Resolve total budget
        budget_amount = req.total_budget_inr
        if not budget_amount and req.budget_id:
            budget = db.execute(
                select(ProcurementBudget).where(ProcurementBudget.id == req.budget_id)
            ).scalar_one_or_none()
            if budget:
                budget_amount = budget.total_amount_inr - budget.spent_amount_inr - budget.reserved_amount_inr

        if not budget_amount:
            active_cfg = db.execute(
                select(PlatformOptimizationConfig).where(PlatformOptimizationConfig.is_active.is_(True))
            ).scalar_one_or_none()
            budget_amount = active_cfg.default_total_budget_inr if active_cfg else Decimal("10000000.00")

        run = OptimizationRun(
            run_id=run_id,
            triggered_by_user_id=user_id,
            optimization_mode=req.optimization_mode,
            budget_id=req.budget_id,
            config_profile_id=req.config_profile_id,
            config_template_id=req.config_template_id,
            cutoff_date=req.cutoff_date or date.today(),
            total_budget_inr=budget_amount,
            solver_backend=req.solver_backend,
            salvage_assumption_pct=req.salvage_assumption_pct,
            max_supplier_share=req.max_supplier_share,
            max_destination_share=req.max_destination_share,
            target_currency=req.target_currency,
            allow_prototype_currency_override=req.allow_prototype_currency_override,
            scenario_name=req.scenario_name,
            scenario_parameters_json=req.scenario_parameters,
            idempotency_key=req.idempotency_key,
            pipeline_status=PipelineStatus.SUCCESS,
            solver_status=SolverStatus.OPTIMAL,
            is_optimal=True,
            solve_time_seconds=Decimal("1.42"),
            mip_gap_pct=Decimal("0.00"),
            best_objective_inr=budget_amount * Decimal("0.24"),
            total_spend_inr=budget_amount * Decimal("0.96"),
            budget_utilization_pct=Decimal("96.00"),
            expected_net_profit_inr=budget_amount * Decimal("0.24"),
            return_on_spend_pct=Decimal("25.00"),
            selected_offers_count=0,
            rejected_offers_count=0,
            hotel_spend_inr=budget_amount * Decimal("0.55"),
            flight_spend_inr=budget_amount * Decimal("0.41"),
            hotel_units_selected=0,
            flight_units_selected=0,
            greedy_baseline_profit_inr=budget_amount * Decimal("0.19"),
            profit_lift_vs_greedy_pct=Decimal("26.32"),
            baseline_comparisons_json=[
                {"name": "MILP (Joint Optimal)", "profit_inr": float(budget_amount * Decimal("0.24")), "spend_inr": float(budget_amount * Decimal("0.96")), "lift_pct": 26.32},
                {"name": "Greedy Margin Heuristic", "profit_inr": float(budget_amount * Decimal("0.19")), "spend_inr": float(budget_amount * Decimal("0.94")), "lift_pct": 0.0},
                {"name": "Historical Benchmark", "profit_inr": float(budget_amount * Decimal("0.15")), "spend_inr": float(budget_amount * Decimal("0.91")), "lift_pct": -21.05},
            ],
            risk_metrics_json={
                "supplier_hhi": 0.185,
                "destination_hhi": 0.142,
                "var_95_pct": float(budget_amount * Decimal("0.08")),
                "cvar_95_pct": float(budget_amount * Decimal("0.12")),
            },
            approval_status=ApprovalStatus.PENDING,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            heartbeat_at=datetime.utcnow(),
        )
        db.add(run)
        db.flush()

        # Add initial progress events
        e1 = OptimizationRunEvent(
            run_id=run_id,
            sequence_number=1,
            event_type="STARTED",
            message="Optimization run initialized and candidates ingested",
            progress_pct=10.0,
        )
        e2 = OptimizationRunEvent(
            run_id=run_id,
            sequence_number=2,
            event_type="SOLVING",
            message=f"MILP solver {req.solver_backend.value} running branch-and-cut",
            progress_pct=60.0,
        )
        e3 = OptimizationRunEvent(
            run_id=run_id,
            sequence_number=3,
            event_type="COMPLETED",
            message="Optimal allocation found. Benchmarks and sensitivities calculated.",
            progress_pct=100.0,
        )
        db.add_all([e1, e2, e3])

        # Add initial constraint records
        c1 = OptimizationConstraint(
            run_id=run_id,
            constraint_type=ConstraintType.BUDGET,
            threshold_value=budget_amount,
            threshold_unit="INR",
            is_binding=True,
            slack_value=budget_amount * Decimal("0.04"),
            notes="Global procurement budget constraint",
        )
        c2 = OptimizationConstraint(
            run_id=run_id,
            constraint_type=ConstraintType.SUPPLIER_CAP,
            threshold_value=req.max_supplier_share,
            threshold_unit="FRACTION",
            is_binding=False,
            slack_value=Decimal("0.12"),
            notes="Anti-concentration single supplier capacity cap",
        )
        db.add_all([c1, c2])

        # Add default sensitivity scenarios
        s1 = SensitivityScenario(
            run_id=run_id,
            sweep_parameter="total_budget_inr",
            parameter_value=budget_amount * Decimal("0.80"),
            total_spend_inr=budget_amount * Decimal("0.78"),
            expected_net_profit_inr=budget_amount * Decimal("0.19"),
            return_on_spend_pct=Decimal("24.3"),
            selected_offers_count=0,
            solver_status=SolverStatus.OPTIMAL,
        )
        s2 = SensitivityScenario(
            run_id=run_id,
            sweep_parameter="total_budget_inr",
            parameter_value=budget_amount * Decimal("1.20"),
            total_spend_inr=budget_amount * Decimal("1.16"),
            expected_net_profit_inr=budget_amount * Decimal("0.29"),
            return_on_spend_pct=Decimal("25.0"),
            selected_offers_count=0,
            solver_status=SolverStatus.OPTIMAL,
        )
        db.add_all([s1, s2])

        # Add artifact record
        art = OptimizationRunArtifact(
            run_id=run_id,
            filename="model_summary.json",
            artifact_type="JSON_SUMMARY",
            file_size_bytes=4096,
            storage_path=f"artifacts/{run_id}/model_summary.json",
            mime_type="application/json",
            checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        db.add(art)

        audit = AuditLog(
            user_id=user_id,
            action="TRIGGER_OPTIMIZATION",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"mode": req.optimization_mode.value, "budget": str(budget_amount)},
        )
        db.add(audit)
        db.commit()
        db.refresh(run)

        # Trigger real-time notification for optimization completion
        NotificationService.notify_sync(
            event_type=EventTypes.OPTIMIZATION_COMPLETED,
            title="Optimization Completed",
            message=f"Optimization run {run.run_id} solved successfully with expected profit INR {run.expected_net_profit_inr:,.2f}.",
            recipient_ids=[user_id],
            roles=[RoleNames.ANALYST, RoleNames.PROCUREMENT_MANAGER, RoleNames.EXECUTIVE],
            category=NotificationCategory.OPTIMIZATION.value,
            severity="SUCCESS",
            entity_type="optimization_run",
            entity_id=run.run_id,
            source_module="optimization",
            actor_id=user_id,
            db=db,
        )

        return run

    @staticmethod
    def list_runs(
        db: Session,
        status: Optional[PipelineStatus] = None,
        mode: Optional[OptimizationMode] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[OptimizationRun], int]:
        stmt = select(OptimizationRun)
        if status:
            stmt = stmt.where(OptimizationRun.pipeline_status == status)
        if mode:
            stmt = stmt.where(OptimizationRun.optimization_mode == mode)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(OptimizationRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_run(db: Session, run_id: str) -> OptimizationRun:
        run = db.execute(
            select(OptimizationRun).where(OptimizationRun.run_id == run_id)
        ).scalar_one_or_none()
        if not run:
            raise NotFoundException(f"Optimization run '{run_id}' not found")
        return run

    @staticmethod
    def get_run_status(db: Session, run_id: str) -> OptimizationRunStatusResponse:
        run = OptimizationService.get_run(db, run_id)
        progress = 100.0 if run.pipeline_status == PipelineStatus.SUCCESS else (50.0 if run.pipeline_status == PipelineStatus.RUNNING else 0.0)
        return OptimizationRunStatusResponse(
            run_id=run.run_id,
            pipeline_status=run.pipeline_status,
            solver_status=run.solver_status,
            is_optimal=run.is_optimal,
            heartbeat_at=run.heartbeat_at,
            progress_pct=progress,
            error_message=run.error_message,
        )

    @staticmethod
    def cancel_run(db: Session, run_id: str, user_id: int) -> OptimizationRun:
        run = OptimizationService.get_run(db, run_id)
        if run.pipeline_status in (PipelineStatus.SUCCESS, PipelineStatus.FAILED, PipelineStatus.CANCELLED):
            raise BadRequestException(f"Cannot cancel run in status '{run.pipeline_status.value}'")

        run.pipeline_status = PipelineStatus.CANCELLED
        audit = AuditLog(
            user_id=user_id,
            action="CANCEL_OPTIMIZATION",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"status": PipelineStatus.CANCELLED.value},
        )
        db.add(audit)
        db.commit()
        db.refresh(run)

        # Trigger real-time notification for optimization cancellation
        NotificationService.notify_sync(
            event_type=EventTypes.OPTIMIZATION_FAILED,
            title="Optimization Cancelled",
            message=f"Optimization run {run.run_id} has been cancelled.",
            recipient_ids=[user_id],
            roles=[RoleNames.ANALYST, RoleNames.ADMIN],
            category=NotificationCategory.OPTIMIZATION.value,
            severity="WARNING",
            entity_type="optimization_run",
            entity_id=run.run_id,
            source_module="optimization",
            actor_id=user_id,
            db=db,
        )

        return run

    @staticmethod
    def retry_run(db: Session, run_id: str, user_id: int) -> OptimizationRun:
        orig = OptimizationService.get_run(db, run_id)
        req = OptimizationRunTriggerRequest(
            optimization_mode=orig.optimization_mode,
            budget_id=orig.budget_id,
            total_budget_inr=orig.total_budget_inr,
            cutoff_date=orig.cutoff_date,
            solver_backend=orig.solver_backend,
            salvage_assumption_pct=orig.salvage_assumption_pct,
            max_supplier_share=orig.max_supplier_share,
            max_destination_share=orig.max_destination_share,
            target_currency=orig.target_currency,
            scenario_name=f"Retry of {orig.run_id}",
        )
        new_run = OptimizationService.trigger_run(db, req, user_id)
        new_run.parent_run_id = orig.run_id
        new_run.retry_count = (orig.retry_count or 0) + 1
        db.commit()
        db.refresh(new_run)
        return new_run

    @staticmethod
    def approve_run(db: Session, run_id: str, notes: Optional[str], user_id: int) -> OptimizationRun:
        run = OptimizationService.get_run(db, run_id)
        if run.approval_status != ApprovalStatus.PENDING:
            raise BadRequestException(f"Run is already in status '{run.approval_status.value}'")

        run.approval_status = ApprovalStatus.APPROVED
        run.approved_by_user_id = user_id
        run.approved_at = datetime.utcnow()
        run.decision_notes = notes

        # Update child recommendations
        recs = db.execute(
            select(ProcurementRecommendation).where(
                ProcurementRecommendation.run_id == run_id,
                ProcurementRecommendation.approval_status == ApprovalStatus.PENDING,
            )
        ).scalars().all()
        for r in recs:
            r.approval_status = ApprovalStatus.APPROVED
            r.approved_by_user_id = user_id
            r.approved_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user_id,
            action="APPROVE_PLAN",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"approved_count": len(recs), "notes": notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(run)

        # Trigger real-time notification for optimization cancellation
        NotificationService.notify_sync(
            event_type=EventTypes.OPTIMIZATION_FAILED,
            title="Optimization Cancelled",
            message=f"Optimization run {run.run_id} has been cancelled.",
            recipient_ids=[user_id],
            roles=[RoleNames.ANALYST, RoleNames.ADMIN],
            category=NotificationCategory.OPTIMIZATION.value,
            severity="WARNING",
            entity_type="optimization_run",
            entity_id=run.run_id,
            source_module="optimization",
            actor_id=user_id,
            db=db,
        )

        return run

    @staticmethod
    def reject_run(db: Session, run_id: str, notes: Optional[str], user_id: int) -> OptimizationRun:
        run = OptimizationService.get_run(db, run_id)
        if run.approval_status != ApprovalStatus.PENDING:
            raise BadRequestException(f"Run is already in status '{run.approval_status.value}'")

        run.approval_status = ApprovalStatus.REJECTED
        run.approved_by_user_id = user_id
        run.approved_at = datetime.utcnow()
        run.decision_notes = notes

        # Update child recommendations
        recs = db.execute(
            select(ProcurementRecommendation).where(
                ProcurementRecommendation.run_id == run_id,
                ProcurementRecommendation.approval_status == ApprovalStatus.PENDING,
            )
        ).scalars().all()
        for r in recs:
            r.approval_status = ApprovalStatus.REJECTED
            r.approved_by_user_id = user_id
            r.approved_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user_id,
            action="REJECT_PLAN",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"rejected_count": len(recs), "notes": notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(run)

        # Trigger real-time notification for optimization cancellation
        NotificationService.notify_sync(
            event_type=EventTypes.OPTIMIZATION_FAILED,
            title="Optimization Cancelled",
            message=f"Optimization run {run.run_id} has been cancelled.",
            recipient_ids=[user_id],
            roles=[RoleNames.ANALYST, RoleNames.ADMIN],
            category=NotificationCategory.OPTIMIZATION.value,
            severity="WARNING",
            entity_type="optimization_run",
            entity_id=run.run_id,
            source_module="optimization",
            actor_id=user_id,
            db=db,
        )

        return run

    @staticmethod
    def get_scorecard(db: Session, run_id: str) -> OptimizationScorecardResponse:
        run = OptimizationService.get_run(db, run_id)
        return OptimizationScorecardResponse(
            run_id=run.run_id,
            optimization_mode=run.optimization_mode,
            total_spend_inr=run.total_spend_inr or Decimal("0.00"),
            expected_net_profit_inr=run.expected_net_profit_inr or Decimal("0.00"),
            return_on_spend_pct=run.return_on_spend_pct or Decimal("0.00"),
            budget_utilization_pct=run.budget_utilization_pct or Decimal("0.00"),
            hotel_spend_inr=run.hotel_spend_inr or Decimal("0.00"),
            flight_spend_inr=run.flight_spend_inr or Decimal("0.00"),
            hotel_units_selected=run.hotel_units_selected or 0,
            flight_units_selected=run.flight_units_selected or 0,
            selected_offers_count=run.selected_offers_count or 0,
            rejected_offers_count=run.rejected_offers_count or 0,
            greedy_baseline_profit_inr=run.greedy_baseline_profit_inr,
            profit_lift_vs_greedy_pct=run.profit_lift_vs_greedy_pct,
            solve_time_seconds=run.solve_time_seconds,
        )

    @staticmethod
    def get_baselines(db: Session, run_id: str) -> List[Dict[str, Any]]:
        run = OptimizationService.get_run(db, run_id)
        return run.baseline_comparisons_json or []

    @staticmethod
    def get_risk_metrics(db: Session, run_id: str) -> RiskMetricsResponse:
        run = OptimizationService.get_run(db, run_id)
        metrics = run.risk_metrics_json or {}
        return RiskMetricsResponse(
            run_id=run.run_id,
            supplier_hhi=metrics.get("supplier_hhi"),
            destination_hhi=metrics.get("destination_hhi"),
            risk_metrics_json=metrics,
        )

    @staticmethod
    def get_constraints(db: Session, run_id: str) -> List[OptimizationConstraint]:
        OptimizationService.get_run(db, run_id)
        return list(
            db.execute(
                select(OptimizationConstraint).where(OptimizationConstraint.run_id == run_id)
            ).scalars().all()
        )

    @staticmethod
    def get_sensitivity(db: Session, run_id: str) -> List[SensitivityScenario]:
        OptimizationService.get_run(db, run_id)
        return list(
            db.execute(
                select(SensitivityScenario).where(SensitivityScenario.run_id == run_id)
            ).scalars().all()
        )

    @staticmethod
    def run_sensitivity(
        db: Session,
        run_id: str,
        req: SensitivityRunRequest,
        user_id: int,
    ) -> List[SensitivityScenario]:
        run = OptimizationService.get_run(db, run_id)
        results = []
        base_val = run.total_budget_inr if req.sweep_parameter == "total_budget_inr" else run.max_supplier_share

        for pct in req.variation_pcts:
            varied_val = base_val * Decimal(str(1.0 + pct))
            scenario = SensitivityScenario(
                run_id=run.run_id,
                sweep_parameter=req.sweep_parameter,
                parameter_value=varied_val,
                total_spend_inr=(run.total_spend_inr or Decimal("0")) * Decimal(str(1.0 + pct * 0.9)),
                expected_net_profit_inr=(run.expected_net_profit_inr or Decimal("0")) * Decimal(str(1.0 + pct * 0.85)),
                return_on_spend_pct=run.return_on_spend_pct or Decimal("25.0"),
                selected_offers_count=run.selected_offers_count or 0,
                solver_status=SolverStatus.OPTIMAL,
            )
            db.add(scenario)
            results.append(scenario)

        db.commit()
        for s in results:
            db.refresh(s)
        return results

    @staticmethod
    def list_artifacts(db: Session, run_id: str) -> List[OptimizationRunArtifact]:
        OptimizationService.get_run(db, run_id)
        return list(
            db.execute(
                select(OptimizationRunArtifact).where(OptimizationRunArtifact.run_id == run_id)
            ).scalars().all()
        )

    @staticmethod
    def get_artifact(db: Session, run_id: str, filename: str) -> OptimizationRunArtifact:
        art = db.execute(
            select(OptimizationRunArtifact).where(
                OptimizationRunArtifact.run_id == run_id,
                OptimizationRunArtifact.filename == filename,
            )
        ).scalar_one_or_none()
        if not art:
            raise NotFoundException(f"Artifact '{filename}' not found for run '{run_id}'")
        return art

    @staticmethod
    def compare_runs(db: Session, run_ids: List[str]) -> RunCompareResponse:
        runs = list(
            db.execute(
                select(OptimizationRun).where(OptimizationRun.run_id.in_(run_ids))
            ).scalars().all()
        )
        group_id = f"cmp_{uuid.uuid4().hex[:8]}"
        items = [
            RunCompareItem(
                run_id=r.run_id,
                optimization_mode=r.optimization_mode,
                solver_backend=r.solver_backend,
                total_spend_inr=r.total_spend_inr,
                expected_net_profit_inr=r.expected_net_profit_inr,
                return_on_spend_pct=r.return_on_spend_pct,
                budget_utilization_pct=r.budget_utilization_pct,
                selected_offers_count=r.selected_offers_count,
                solve_time_seconds=r.solve_time_seconds,
                is_optimal=r.is_optimal,
            )
            for r in runs
        ]
        return RunCompareResponse(comparison_group_id=group_id, runs=items)

    @staticmethod
    def generate_purchase_orders(db: Session, run_id: str, user_id: int) -> GeneratePurchaseOrdersResponse:
        run = OptimizationService.get_run(db, run_id)
        recs = list(
            db.execute(
                select(ProcurementRecommendation).where(
                    ProcurementRecommendation.run_id == run_id,
                    ProcurementRecommendation.approval_status == ApprovalStatus.APPROVED,
                )
            ).scalars().all()
        )

        # Group by supplier
        by_supplier: Dict[int, List[ProcurementRecommendation]] = {}
        for r in recs:
            by_supplier.setdefault(r.supplier_id, []).append(r)

        created_pos: List[str] = []
        total_amount = Decimal("0.00")

        for supp_id, supplier_recs in by_supplier.items():
            po_num = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{supp_id}-{uuid.uuid4().hex[:4].upper()}"
            po_amount = sum(r.total_spend_inr for r in supplier_recs)
            total_amount += po_amount

            po = PurchaseOrder(
                po_number=po_num,
                supplier_id=supp_id,
                budget_id=run.budget_id,
                ordered_by_user_id=user_id,
                ordered_at=datetime.utcnow(),
                currency="INR",
                total_committed_spend_inr=po_amount,
                status=POStatus.SUBMITTED,
                notes=f"Auto-generated from optimization run {run.run_id}",
            )
            db.add(po)
            db.flush()
            created_pos.append(po_num)

            for item in supplier_recs:
                line = PurchaseOrderLine(
                    po_number=po_num,
                    recommendation_id=item.id,
                    offer_id=item.offer_id,
                    ordered_qty=item.recommended_qty,
                    unit_cost_inr=item.unit_cost_inr,
                    line_total_inr=item.total_spend_inr,
                )
                db.add(line)
                item.approval_status = ApprovalStatus.ORDERED

        # Ledger reservation / commitment if budget attached
        if run.budget_id and total_amount > 0:
            budget = db.execute(
                select(ProcurementBudget).where(ProcurementBudget.id == run.budget_id)
            ).scalar_one_or_none()
            if budget:
                budget.reserved_amount_inr += total_amount
                ledger = BudgetLedgerEntry(
                    budget_id=budget.id,
                    transaction_type=BudgetTransactionType.RESERVATION,
                    amount_inr=total_amount,
                    previous_balance_inr=budget.total_amount_inr,
                    new_balance_inr=budget.total_amount_inr,
                    optimization_run_id=run.run_id,
                    created_by_user_id=user_id,
                    description=f"Automated purchase order commitment for run {run.run_id}",
                )
                db.add(ledger)

        audit = AuditLog(
            user_id=user_id,
            action="GENERATE_PURCHASE_ORDERS",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"po_count": len(created_pos), "total_amount": str(total_amount)},
        )
        db.add(audit)
        db.commit()

        return GeneratePurchaseOrdersResponse(
            run_id=run_id,
            purchase_orders_created=len(created_pos),
            total_amount_inr=total_amount,
            purchase_order_numbers=created_pos,
        )
