from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from backend.app.models.schema import (
    ApprovalStatus,
    AuditLog,
    InventoryCategory,
    ProcurementRecommendation,
    RejectedOpportunity,
    RejectionReasonCode,
)
from backend.app.schemas.recommendation import (
    BulkRecommendationDecisionResponse,
    RejectionReasonSummaryItem,
    RejectionSummaryResponse,
)


class RecommendationService:

    @staticmethod
    def list_recommendations(
        db: Session,
        run_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        dest_id: Optional[str] = None,
        category: Optional[InventoryCategory] = None,
        approval_status: Optional[ApprovalStatus] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[ProcurementRecommendation], int]:
        stmt = select(ProcurementRecommendation)
        if run_id:
            stmt = stmt.where(ProcurementRecommendation.run_id == run_id)
        if supplier_id:
            stmt = stmt.where(ProcurementRecommendation.supplier_id == supplier_id.strip().upper())
        if dest_id:
            stmt = stmt.where(ProcurementRecommendation.dest_id == dest_id.strip().upper())
        if category:
            stmt = stmt.where(ProcurementRecommendation.inventory_category == category)
        if approval_status:
            stmt = stmt.where(ProcurementRecommendation.approval_status == approval_status)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(ProcurementRecommendation.expected_total_contribution_inr.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_recommendation(db: Session, rec_id: int) -> ProcurementRecommendation:
        rec = db.execute(
            select(ProcurementRecommendation).where(ProcurementRecommendation.id == rec_id)
        ).scalar_one_or_none()
        if not rec:
            raise NotFoundException(f"Recommendation {rec_id} not found")
        return rec

    @staticmethod
    def approve_recommendation(
        db: Session,
        rec_id: int,
        notes: Optional[str],
        user_id: int,
    ) -> ProcurementRecommendation:
        rec = db.execute(
            select(ProcurementRecommendation)
            .where(ProcurementRecommendation.id == rec_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not rec:
            raise NotFoundException(f"Recommendation {rec_id} not found")
        if rec.approval_status == ApprovalStatus.ORDERED:
            raise BadRequestException(f"Recommendation {rec_id} is already ORDERED and cannot be re-approved.")
        from backend.app.models.schema import PolicyScope
        from backend.app.services.policy_service import PolicyService
        PolicyService.enforce_workflow_policies(
            db=db,
            scope=PolicyScope.RECOMMENDATION_APPROVAL,
            entity_type="procurement_recommendations",
            entity_id=str(rec_id),
            context={
                "recommendation_id": rec.id,
                "run_id": rec.run_id,
                "supplier_id": rec.supplier_id,
                "dest_id": rec.dest_id,
                "recommended_qty": rec.recommended_qty,
                "total_spend_inr": float(rec.total_spend_inr),
                "sell_through_rate": float(rec.sell_through_rate),
            },
            user_id=user_id,
        )
        rec.approval_status = ApprovalStatus.APPROVED
        rec.approved_by_user_id = user_id
        rec.approved_at = datetime.utcnow()
        rec.decision_notes = notes

        audit = AuditLog(
            user_id=user_id,
            action="APPROVE_RECOMMENDATION",
            entity_type="PROCUREMENT_RECOMMENDATION",
            entity_id=str(rec_id),
            new_value_json={"notes": notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def reject_recommendation(
        db: Session,
        rec_id: int,
        notes: Optional[str],
        user_id: int,
    ) -> ProcurementRecommendation:
        rec = db.execute(
            select(ProcurementRecommendation)
            .where(ProcurementRecommendation.id == rec_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not rec:
            raise NotFoundException(f"Recommendation {rec_id} not found")
        if rec.approval_status == ApprovalStatus.ORDERED:
            raise BadRequestException(f"Recommendation {rec_id} is already ORDERED and cannot be rejected.")
        rec.approval_status = ApprovalStatus.REJECTED
        rec.approved_by_user_id = user_id
        rec.approved_at = datetime.utcnow()
        rec.decision_notes = notes

        audit = AuditLog(
            user_id=user_id,
            action="REJECT_RECOMMENDATION",
            entity_type="PROCUREMENT_RECOMMENDATION",
            entity_id=str(rec_id),
            new_value_json={"notes": notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def bulk_approve(
        db: Session,
        run_id: str,
        rec_ids: List[int],
        notes: Optional[str],
        user_id: int,
    ) -> BulkRecommendationDecisionResponse:
        recs = list(
            db.execute(
                select(ProcurementRecommendation).where(
                    ProcurementRecommendation.run_id == run_id,
                    ProcurementRecommendation.id.in_(rec_ids),
                ).with_for_update()
            ).scalars().all()
        )
        for r in recs:
            if r.approval_status == ApprovalStatus.ORDERED:
                raise BadRequestException(f"Recommendation {r.id} is already ORDERED and cannot be bulk-approved.")
        now = datetime.utcnow()
        from backend.app.models.schema import PolicyScope
        from backend.app.services.policy_service import PolicyService
        for r in recs:
            PolicyService.enforce_workflow_policies(
                db=db,
                scope=PolicyScope.RECOMMENDATION_APPROVAL,
                entity_type="procurement_recommendations",
                entity_id=str(r.id),
                context={
                    "recommendation_id": r.id,
                    "run_id": r.run_id,
                    "supplier_id": r.supplier_id,
                    "dest_id": r.dest_id,
                    "recommended_qty": r.recommended_qty,
                    "total_spend_inr": float(r.total_spend_inr),
                    "sell_through_rate": float(r.sell_through_rate),
                },
                user_id=user_id,
            )
        for r in recs:
            r.approval_status = ApprovalStatus.APPROVED
            r.approved_by_user_id = user_id
            r.approved_at = now
            r.decision_notes = notes

        audit = AuditLog(
            user_id=user_id,
            action="BULK_APPROVE_RECOMMENDATIONS",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"count": len(recs), "ids": rec_ids},
        )
        db.add(audit)
        db.commit()
        return BulkRecommendationDecisionResponse(updated_count=len(recs), status=ApprovalStatus.APPROVED)

    @staticmethod
    def bulk_reject(
        db: Session,
        run_id: str,
        rec_ids: List[int],
        notes: Optional[str],
        user_id: int,
    ) -> BulkRecommendationDecisionResponse:
        recs = list(
            db.execute(
                select(ProcurementRecommendation).where(
                    ProcurementRecommendation.run_id == run_id,
                    ProcurementRecommendation.id.in_(rec_ids),
                ).with_for_update()
            ).scalars().all()
        )
        for r in recs:
            if r.approval_status == ApprovalStatus.ORDERED:
                raise BadRequestException(f"Recommendation {r.id} is already ORDERED and cannot be bulk-approved.")
        now = datetime.utcnow()
        for r in recs:
            r.approval_status = ApprovalStatus.REJECTED
            r.approved_by_user_id = user_id
            r.approved_at = now
            r.decision_notes = notes

        audit = AuditLog(
            user_id=user_id,
            action="BULK_REJECT_RECOMMENDATIONS",
            entity_type="OPTIMIZATION_RUN",
            entity_id=run_id,
            new_value_json={"count": len(recs), "ids": rec_ids},
        )
        db.add(audit)
        db.commit()
        return BulkRecommendationDecisionResponse(updated_count=len(recs), status=ApprovalStatus.REJECTED)

    @staticmethod
    def export_recommendations(db: Session, run_id: str, export_format: str = "csv") -> str:
        recs = list(
            db.execute(
                select(ProcurementRecommendation).where(ProcurementRecommendation.run_id == run_id)
            ).scalars().all()
        )

        if export_format.lower() == "json":
            data = [
                {
                    "id": r.id,
                    "offer_id": r.offer_id,
                    "supplier_id": r.supplier_id,
                    "dest_id": r.dest_id,
                    "category": r.inventory_category.value,
                    "recommended_qty": r.recommended_qty,
                    "unit_cost_inr": str(r.unit_cost_inr),
                    "total_spend_inr": str(r.total_spend_inr),
                    "expected_profit_inr": str(r.expected_total_contribution_inr),
                    "approval_status": r.approval_status.value,
                }
                for r in recs
            ]
            return json.dumps(data, indent=2)

        # Default CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "OfferID", "SupplierID", "DestID", "Category", "UnitType",
            "RecommendedQty", "UnitCostINR", "TotalSpendINR", "ExpectedProfitINR",
            "SellThroughRate", "ApprovalStatus"
        ])
        for r in recs:
            writer.writerow([
                r.id, r.offer_id, r.supplier_id, r.dest_id, r.inventory_category.value, r.unit_type.value,
                r.recommended_qty, r.unit_cost_inr, r.total_spend_inr, r.expected_total_contribution_inr,
                r.sell_through_rate, r.approval_status.value,
            ])
        return output.getvalue()

    @staticmethod
    def list_rejections(
        db: Session,
        run_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[RejectedOpportunity], int]:
        stmt = select(RejectedOpportunity).where(RejectedOpportunity.run_id == run_id)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_rejection_summary(db: Session, run_id: str) -> RejectionSummaryResponse:
        stmt = (
            select(
                RejectedOpportunity.reason_code,
                func.count(RejectedOpportunity.id).label("count"),
                func.coalesce(func.sum(RejectedOpportunity.moq_cost_inr), Decimal("0.00")).label("total_moq_cost"),
            )
            .where(RejectedOpportunity.run_id == run_id)
            .group_by(RejectedOpportunity.reason_code)
        )
        rows = db.execute(stmt).all()
        breakdown = [
            RejectionReasonSummaryItem(
                reason_code=r[0],
                count=r[1],
                total_moq_cost_inr=r[2],
            )
            for r in rows
        ]
        total_rej = sum(b.count for b in breakdown)
        return RejectionSummaryResponse(
            run_id=run_id,
            total_rejections=total_rej,
            breakdown=breakdown,
        )
