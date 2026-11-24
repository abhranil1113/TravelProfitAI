from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
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
    BudgetTransactionType,
    FulfillmentStatus,
    POStatus,
    ProcurementBudget,
    PurchaseOrder,
    PurchaseOrderFulfillment,
    PurchaseOrderLine,
    Supplier,
    SupplierOffer,
)
from backend.app.schemas.procurement import (
    FulfillmentCreateRequest,
    FulfillmentDisputeRequest,
    FulfillmentUpdateRequest,
    PurchaseOrderCancelRequest,
    PurchaseOrderConfirmRequest,
    PurchaseOrderCreateRequest,
)


class ProcurementService:

    @staticmethod
    def list_purchase_orders(
        db: Session,
        supplier_id: Optional[int] = None,
        po_status: Optional[POStatus] = None,
        budget_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[PurchaseOrder], int]:
        stmt = select(PurchaseOrder)
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        if po_status:
            stmt = stmt.where(PurchaseOrder.status == po_status)
        if budget_id:
            stmt = stmt.where(PurchaseOrder.budget_id == budget_id)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(PurchaseOrder.ordered_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def create_purchase_order(
        db: Session,
        req: PurchaseOrderCreateRequest,
        user_id: int,
    ) -> PurchaseOrder:
        supplier = db.execute(
            select(Supplier).where(Supplier.supplier_id == str(req.supplier_id))
        ).scalar_one_or_none()
        if not supplier:
            raise NotFoundException(f"Supplier {req.supplier_id} not found")

        po_num = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{req.supplier_id}-{uuid.uuid4().hex[:4].upper()}"

        total_amount = sum(line.ordered_qty * line.unit_cost_inr for line in req.lines)

        po = PurchaseOrder(
            po_number=po_num,
            supplier_id=supplier.supplier_id,
            budget_id=req.budget_id,
            ordered_by_user_id=user_id,
            ordered_at=datetime.utcnow(),
            currency="INR",
            total_committed_spend_inr=total_amount,
            status=POStatus.SUBMITTED,
            notes=req.notes,
        )
        db.add(po)
        db.flush()

        from backend.app.models.schema import (
            ApprovalStatus,
            InventoryCategory,
            OptimizationRun,
            ProcurementRecommendation,
            SolverStatus,
            UnitType,
        )

        for line_req in req.lines:
            line_total = line_req.ordered_qty * line_req.unit_cost_inr
            rec_id = line_req.recommendation_id
            if not rec_id:
                run = OptimizationRun(
                    run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
                    cutoff_date=datetime.utcnow().date(),
                    solver_status=SolverStatus.OPTIMAL,
                    total_budget_inr=Decimal("10000000.00"),
                    triggered_by_user_id=user_id,
                )
                db.add(run)
                db.flush()
                offer_obj = db.query(SupplierOffer).filter(SupplierOffer.offer_id == str(line_req.offer_id)).first()
                rec = ProcurementRecommendation(
                    run_id=run.run_id,
                    offer_id=str(line_req.offer_id),
                    supplier_id=supplier.supplier_id,
                    dest_id=offer_obj.dest_id if offer_obj else "BLR",
                    inventory_category=offer_obj.inventory_category if offer_obj else InventoryCategory.HOTEL,
                    unit_type=offer_obj.unit_type if offer_obj else UnitType.ROOM_NIGHT,
                    recommended_qty=line_req.ordered_qty,
                    unit_cost_inr=line_req.unit_cost_inr,
                    total_spend_inr=line_total,
                    expected_unit_contribution_inr=Decimal("100.00"),
                    expected_total_contribution_inr=Decimal("1000.00"),
                    sell_through_rate=0.85,
                    moq_applied=1,
                    capacity_available=line_req.ordered_qty,
                    rationale="Auto-generated recommendation for manual PO line",
                    approval_status=ApprovalStatus.APPROVED,
                )
                db.add(rec)
                db.flush()
                rec_id = rec.id

            line = PurchaseOrderLine(
                po_number=po_num,
                recommendation_id=rec_id,
                offer_id=str(line_req.offer_id),
                ordered_qty=line_req.ordered_qty,
                unit_cost_inr=line_req.unit_cost_inr,
                line_total_inr=line_total,
            )
            db.add(line)

        # Ledger reservation if budget attached
        if req.budget_id:
            budget = db.execute(
                select(ProcurementBudget).where(ProcurementBudget.id == req.budget_id)
            ).scalar_one_or_none()
            if budget:
                budget.reserved_amount_inr += total_amount
                ledger = BudgetLedgerEntry(
                    budget_id=budget.id,
                    transaction_type=BudgetTransactionType.RESERVE,
                    amount_inr=total_amount,
                    previous_balance_inr=budget.total_amount_inr,
                    new_balance_inr=budget.total_amount_inr,
                    po_number=po_num,
                    created_by_user_id=user_id,
                    description=f"Manual PO commitment for {po_num}",
                )
                db.add(ledger)

        audit = AuditLog(
            user_id=user_id,
            action="CREATE_PURCHASE_ORDER",
            entity_type="PURCHASE_ORDER",
            entity_id=po_num,
            new_value_json={"total_amount": str(total_amount), "lines": len(req.lines)},
        )
        db.add(audit)
        db.commit()
        db.refresh(po)
        return po

    @staticmethod
    def get_purchase_order(db: Session, po_number: str) -> PurchaseOrder:
        po = db.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        ).scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Purchase order '{po_number}' not found")
        return po

    @staticmethod
    def confirm_purchase_order(
        db: Session,
        po_number: str,
        req: PurchaseOrderConfirmRequest,
        user_id: int,
    ) -> PurchaseOrder:
        po = ProcurementService.get_purchase_order(db, po_number)
        if po.status != POStatus.SUBMITTED:
            raise BadRequestException(f"Cannot confirm PO in status '{po.status.value}'. Must be SUBMITTED.")

        po.status = POStatus.CONFIRMED
        if req.notes:
            po.notes = f"{po.notes or ''}\n[Confirmed]: {req.notes}".strip()

        # Update budget ledger from reservation to commitment if budget present
        if po.budget_id:
            budget = db.execute(
                select(ProcurementBudget).where(ProcurementBudget.id == po.budget_id)
            ).scalar_one_or_none()
            if budget:
                budget.reserved_amount_inr -= po.total_committed_spend_inr
                budget.spent_amount_inr += po.total_committed_spend_inr
                ledger = BudgetLedgerEntry(
                    budget_id=budget.id,
                    transaction_type=BudgetTransactionType.COMMIT,
                    amount_inr=po.total_committed_spend_inr,
                    previous_balance_inr=budget.total_amount_inr,
                    new_balance_inr=budget.total_amount_inr,
                    po_number=po_number,
                    created_by_user_id=user_id,
                    description=f"Confirmed PO execution for {po_number}",
                )
                db.add(ledger)

        audit = AuditLog(
            user_id=user_id,
            action="CONFIRM_PURCHASE_ORDER",
            entity_type="PURCHASE_ORDER",
            entity_id=po_number,
            new_value_json={"status": POStatus.CONFIRMED.value},
        )
        db.add(audit)
        db.commit()
        db.refresh(po)
        return po

    @staticmethod
    def cancel_purchase_order(
        db: Session,
        po_number: str,
        req: PurchaseOrderCancelRequest,
        user_id: int,
    ) -> PurchaseOrder:
        po = ProcurementService.get_purchase_order(db, po_number)
        if po.status in (POStatus.COMPLETED, POStatus.CANCELLED):
            raise BadRequestException(f"Cannot cancel PO in status '{po.status.value}'")

        # Release budget reservation if was in SUBMITTED
        if po.budget_id and po.status == POStatus.SUBMITTED:
            budget = db.execute(
                select(ProcurementBudget).where(ProcurementBudget.id == po.budget_id)
            ).scalar_one_or_none()
            if budget:
                budget.reserved_amount_inr -= po.total_committed_spend_inr
                ledger = BudgetLedgerEntry(
                    budget_id=budget.id,
                    transaction_type=BudgetTransactionType.RELEASE,
                    amount_inr=po.total_committed_spend_inr,
                    previous_balance_inr=budget.total_amount_inr,
                    new_balance_inr=budget.total_amount_inr,
                    po_number=po_number,
                    created_by_user_id=user_id,
                    description=f"Released reservation for cancelled PO {po_number}: {req.reason}",
                )
                db.add(ledger)

        po.status = POStatus.CANCELLED
        po.notes = f"{po.notes or ''}\n[Cancelled]: {req.reason}".strip()

        audit = AuditLog(
            user_id=user_id,
            action="CANCEL_PURCHASE_ORDER",
            entity_type="PURCHASE_ORDER",
            entity_id=po_number,
            new_value_json={"reason": req.reason},
        )
        db.add(audit)
        db.commit()
        db.refresh(po)
        return po

    @staticmethod
    def list_lines(db: Session, po_number: str) -> List[PurchaseOrderLine]:
        ProcurementService.get_purchase_order(db, po_number)
        stmt = select(PurchaseOrderLine).where(PurchaseOrderLine.po_number == po_number).order_by(PurchaseOrderLine.id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def export_purchase_order(db: Session, po_number: str, export_format: str = "json") -> str:
        po = ProcurementService.get_purchase_order(db, po_number)
        lines = ProcurementService.list_lines(db, po_number)

        data = {
            "po_number": po.po_number,
            "supplier_id": po.supplier_id,
            "ordered_at": po.ordered_at.isoformat(),
            "status": po.status.value,
            "total_committed_spend_inr": str(po.total_committed_spend_inr),
            "currency": po.currency,
            "lines": [
                {
                    "line_id": line.id,
                    "offer_id": line.offer_id,
                    "ordered_qty": line.ordered_qty,
                    "unit_cost_inr": str(line.unit_cost_inr),
                    "line_total_inr": str(line.line_total_inr),
                }
                for line in lines
            ],
        }

        if export_format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["LineID", "OfferID", "OrderedQty", "UnitCostINR", "LineTotalINR"])
            for line in lines:
                writer.writerow([line.id, line.offer_id, line.ordered_qty, line.unit_cost_inr, line.line_total_inr])
            return output.getvalue()

        return json.dumps(data, indent=2)

    @staticmethod
    def list_fulfillments(db: Session, po_number: str) -> List[PurchaseOrderFulfillment]:
        ProcurementService.get_purchase_order(db, po_number)
        stmt = (
            select(PurchaseOrderFulfillment)
            .join(PurchaseOrderLine, PurchaseOrderFulfillment.po_line_id == PurchaseOrderLine.id)
            .where(PurchaseOrderLine.po_number == po_number)
            .order_by(PurchaseOrderFulfillment.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def record_fulfillment(
        db: Session,
        po_number: str,
        line_id: int,
        req: FulfillmentCreateRequest,
        user_id: int,
    ) -> PurchaseOrderFulfillment:
        line = db.execute(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.id == line_id,
                PurchaseOrderLine.po_number == po_number,
            )
        ).scalar_one_or_none()
        if not line:
            raise NotFoundException(f"Line {line_id} not found on PO '{po_number}'")

        actual_cost = req.actual_unit_cost_inr or line.unit_cost_inr
        total_cost = req.delivered_qty * actual_cost

        ful = PurchaseOrderFulfillment(
            po_line_id=line.id,
            delivered_qty=req.delivered_qty,
            delivered_at=req.delivered_at or datetime.utcnow(),
            actual_unit_cost_inr=actual_cost,
            actual_total_cost_inr=total_cost,
            fulfilled_units=req.delivered_qty,
            status=FulfillmentStatus.DELIVERED if req.delivered_qty >= line.ordered_qty else FulfillmentStatus.PARTIALLY_DELIVERED,
            notes=req.notes,
        )
        db.add(ful)
        db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="RECORD_FULFILLMENT",
            entity_type="PURCHASE_ORDER_FULFILLMENT",
            entity_id=str(ful.id),
            new_value_json={"po_number": po_number, "delivered_qty": req.delivered_qty},
        )
        db.add(audit)
        db.commit()
        db.refresh(ful)
        return ful

    @staticmethod
    def update_fulfillment(
        db: Session,
        fulfillment_id: int,
        req: FulfillmentUpdateRequest,
        user_id: int,
    ) -> PurchaseOrderFulfillment:
        ful = db.execute(
            select(PurchaseOrderFulfillment).where(PurchaseOrderFulfillment.id == fulfillment_id)
        ).scalar_one_or_none()
        if not ful:
            raise NotFoundException(f"Fulfillment {fulfillment_id} not found")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ful, field, value)

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE_FULFILLMENT",
            entity_type="PURCHASE_ORDER_FULFILLMENT",
            entity_id=str(fulfillment_id),
            new_value_json={k: str(v) if isinstance(v, Decimal) else v for k, v in update_data.items()},
        )
        db.add(audit)
        db.commit()
        db.refresh(ful)
        return ful

    @staticmethod
    def dispute_fulfillment(
        db: Session,
        fulfillment_id: int,
        req: FulfillmentDisputeRequest,
        user_id: int,
    ) -> PurchaseOrderFulfillment:
        ful = db.execute(
            select(PurchaseOrderFulfillment).where(PurchaseOrderFulfillment.id == fulfillment_id)
        ).scalar_one_or_none()
        if not ful:
            raise NotFoundException(f"Fulfillment {fulfillment_id} not found")

        ful.status = FulfillmentStatus.DISPUTED
        ful.dispute_reason = req.dispute_reason
        ful.dispute_status = "OPEN"
        ful.disputed_at = datetime.utcnow()
        ful.disputed_by_user_id = user_id

        audit = AuditLog(
            user_id=user_id,
            action="DISPUTE_FULFILLMENT",
            entity_type="PURCHASE_ORDER_FULFILLMENT",
            entity_id=str(fulfillment_id),
            new_value_json={"reason": req.dispute_reason},
        )
        db.add(audit)
        db.commit()
        db.refresh(ful)
        return ful
