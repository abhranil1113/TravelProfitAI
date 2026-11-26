from __future__ import annotations

import csv
import io
import json
import threading
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
from backend.app.core.notification_events import (
    EventTypes,
    NotificationCategory,
    RoleNames,
)
from backend.app.services.notification_service import NotificationService
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
        from datetime import date
        from backend.app.models.schema import (
            ApprovalStatus,
            BudgetStatus,
            InventoryCategory,
            OptimizationRun,
            ProcurementRecommendation,
            SolverStatus,
            UnitType,
        )

        supplier = db.execute(
            select(Supplier).where(Supplier.supplier_id == str(req.supplier_id))
        ).scalar_one_or_none()
        if not supplier:
            raise NotFoundException(f"Supplier {req.supplier_id} not found")
        if not supplier.is_active:
            raise BadRequestException(f"Supplier '{supplier.supplier_id}' is inactive and cannot accept purchase orders")

        from backend.app.models.schema import (
            PolicyScope,
            SupplierVerificationProfile,
            SupplierVerificationStatus,
        )
        sup_profile = db.execute(
            select(SupplierVerificationProfile).where(
                SupplierVerificationProfile.supplier_id == supplier.supplier_id
            )
        ).scalar_one_or_none()
        if sup_profile and sup_profile.verification_status == SupplierVerificationStatus.SUSPENDED:
            raise BadRequestException(
                f"Supplier '{supplier.supplier_id}' is SUSPENDED and cannot receive purchase orders."
            )

        today = date.today()
        calculated_lines = []
        total_amount = Decimal("0.00")

        for line_req in req.lines:
            offer = db.execute(
                select(SupplierOffer).where(SupplierOffer.offer_id == str(line_req.offer_id))
            ).scalar_one_or_none()
            if not offer:
                raise NotFoundException(f"Supplier offer '{line_req.offer_id}' not found")

            if offer.supplier_id != supplier.supplier_id:
                raise BadRequestException(
                    f"Offer '{offer.offer_id}' belongs to supplier '{offer.supplier_id}', not '{supplier.supplier_id}'"
                )

            # Validate offer validity window
            if offer.valid_from and offer.valid_from > today:
                raise BadRequestException(
                    f"Offer '{offer.offer_id}' is not yet valid (valid from {offer.valid_from.isoformat()})"
                )
            if offer.valid_until and offer.valid_until < today:
                raise BadRequestException(
                    f"Offer '{offer.offer_id}' has expired on {offer.valid_until.isoformat()}"
                )

            # Validate MOQ and capacity
            if line_req.ordered_qty < offer.moq:
                raise BadRequestException(
                    f"Ordered quantity {line_req.ordered_qty} is below MOQ {offer.moq} for offer '{offer.offer_id}'"
                )
            if line_req.ordered_qty > offer.max_capacity:
                raise BadRequestException(
                    f"Ordered quantity {line_req.ordered_qty} exceeds available capacity {offer.max_capacity} for offer '{offer.offer_id}'"
                )

            # Authoritative unit cost from database
            unit_cost = offer.unit_cost_inr
            line_total = line_req.ordered_qty * unit_cost
            total_amount += line_total
            calculated_lines.append((line_req, offer, unit_cost, line_total))

        # Validate budget if specified
        budget = None
        if req.budget_id:
            budget = db.execute(
                select(ProcurementBudget)
                .where(ProcurementBudget.id == req.budget_id)
                .with_for_update()
            ).scalar_one_or_none()
            if not budget:
                raise NotFoundException(f"Procurement budget {req.budget_id} not found")
            if budget.status != BudgetStatus.ACTIVE:
                raise BadRequestException(
                    f"Cannot allocate from budget '{budget.budget_code}' in status '{budget.status.value}'. Must be ACTIVE."
                )

            available_budget = budget.total_amount_inr - budget.spent_amount_inr - budget.reserved_amount_inr
            if available_budget < total_amount:
                raise BadRequestException(
                    f"Insufficient available budget. Requested INR {total_amount:,.2f}, available INR {available_budget:,.2f}"
                )

        po_num = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{supplier.supplier_id}-{uuid.uuid4().hex[:4].upper()}"

        from backend.app.services.policy_service import PolicyService
        po_policy_ctx = {
            "supplier_id": supplier.supplier_id,
            "budget_id": req.budget_id,
            "total_amount_inr": float(total_amount),
            "lines_count": len(calculated_lines),
            "supplier_tier": sup_profile.tier.value if sup_profile else "TIER_3_STANDARD",
        }
        PolicyService.enforce_workflow_policies(
            db=db,
            scope=PolicyScope.PURCHASE_ORDER_CREATE,
            entity_type="purchase_orders",
            entity_id=po_num,
            context=po_policy_ctx,
            user_id=user_id,
        )
        PolicyService.enforce_workflow_policies(
            db=db,
            scope=PolicyScope.PURCHASE_ORDER_SUBMIT,
            entity_type="purchase_orders",
            entity_id=po_num,
            context=po_policy_ctx,
            user_id=user_id,
        )

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

        for line_req, offer, unit_cost, line_total in calculated_lines:
            rec_id = line_req.recommendation_id
            if rec_id:
                rec = db.execute(
                    select(ProcurementRecommendation).where(ProcurementRecommendation.id == rec_id)
                ).scalar_one_or_none()
                if not rec:
                    raise NotFoundException(f"Recommendation {rec_id} not found")
            else:
                # Handled for manual PO line where schema requires non-null recommendation_id
                # Schema change recommendation documented in remediation report for future approval
                run_id = f"MANUAL-{uuid.uuid4().hex[:8].upper()}"
                run = OptimizationRun(
                    run_id=run_id,
                    cutoff_date=today,
                    solver_status=SolverStatus.OPTIMAL,
                    total_budget_inr=total_amount,
                    triggered_by_user_id=user_id,
                )
                db.add(run)
                db.flush()

                rec = ProcurementRecommendation(
                    run_id=run_id,
                    offer_id=offer.offer_id,
                    supplier_id=supplier.supplier_id,
                    dest_id=offer.dest_id,
                    inventory_category=offer.inventory_category,
                    unit_type=offer.unit_type,
                    recommended_qty=line_req.ordered_qty,
                    unit_cost_inr=unit_cost,
                    total_spend_inr=line_total,
                    expected_unit_contribution_inr=max(Decimal("0.00"), offer.list_price_inr - unit_cost),
                    expected_total_contribution_inr=max(Decimal("0.00"), (offer.list_price_inr - unit_cost) * line_req.ordered_qty),
                    sell_through_rate=0.85,
                    moq_applied=offer.moq,
                    capacity_available=offer.max_capacity,
                    rationale="Auto-generated recommendation for manual PO line (schema non-null recommendation_id constraint)",
                    approval_status=ApprovalStatus.APPROVED,
                )
                db.add(rec)
                db.flush()
                rec_id = rec.id

            line = PurchaseOrderLine(
                po_number=po_num,
                recommendation_id=rec_id,
                offer_id=offer.offer_id,
                ordered_qty=line_req.ordered_qty,
                unit_cost_inr=unit_cost,
                line_total_inr=line_total,
            )
            db.add(line)

        # Ledger reservation if budget attached
        if budget:
            prev_avail = budget.total_amount_inr - budget.spent_amount_inr - budget.reserved_amount_inr
            new_avail = prev_avail - total_amount
            budget.reserved_amount_inr += total_amount
            ledger = BudgetLedgerEntry(
                budget_id=budget.id,
                transaction_type=BudgetTransactionType.RESERVE,
                amount_inr=total_amount,
                previous_balance_inr=prev_avail,
                new_balance_inr=new_avail,
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

        # Trigger business notification for PO creation
        NotificationService.notify_sync(
            event_type=EventTypes.PROCUREMENT_PO_CREATED,
            title="Purchase Order Created",
            message=f"Purchase Order {po.po_number} for INR {po.total_committed_spend_inr:,.2f} has been created.",
            recipient_ids=[user_id],
            roles=[RoleNames.PROCUREMENT_MANAGER, RoleNames.FINANCE_USER],
            category=NotificationCategory.PROCUREMENT.value,
            severity="INFO",
            entity_type="purchase_order",
            entity_id=po.po_number,
            source_module="procurement",
            actor_id=user_id,
            db=db,
        )

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
        # Hierarchical lock ordering to prevent deadlocks: ProcurementBudget -> PurchaseOrder
        po_brief = db.execute(
            select(PurchaseOrder.budget_id).where(PurchaseOrder.po_number == po_number)
        ).first()
        if not po_brief:
            raise NotFoundException(f"Purchase order '{po_number}' not found")

        budget = None
        if po_brief[0]:
            budget = db.execute(
                select(ProcurementBudget)
                .where(ProcurementBudget.id == po_brief[0])
                .with_for_update()
            ).scalar_one_or_none()

        po = db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.po_number == po_number)
            .with_for_update()
        ).scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Purchase order '{po_number}' not found")
        if po.status != POStatus.SUBMITTED:
            raise BadRequestException(f"Cannot confirm PO in status '{po.status.value}'. Must be SUBMITTED.")

        po.status = POStatus.CONFIRMED
        if req.notes:
            po.notes = f"{po.notes or ''}\n[Confirmed]: {req.notes}".strip()

        # Update budget ledger from reservation to commitment if budget present
        if budget:
            avail = budget.total_amount_inr - budget.spent_amount_inr - budget.reserved_amount_inr
            budget.reserved_amount_inr -= po.total_committed_spend_inr
            budget.spent_amount_inr += po.total_committed_spend_inr
            ledger = BudgetLedgerEntry(
                budget_id=budget.id,
                transaction_type=BudgetTransactionType.COMMIT,
                amount_inr=po.total_committed_spend_inr,
                previous_balance_inr=avail,
                new_balance_inr=avail,
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

        # Trigger business notification for PO confirmation
        NotificationService.notify_sync(
            event_type=EventTypes.PROCUREMENT_PO_APPROVED,
            title="Purchase Order Confirmed",
            message=f"Purchase Order {po.po_number} has been confirmed.",
            recipient_ids=[user_id],
            roles=[RoleNames.PROCUREMENT_MANAGER, RoleNames.FINANCE_USER],
            category=NotificationCategory.PROCUREMENT.value,
            severity="SUCCESS",
            entity_type="purchase_order",
            entity_id=po.po_number,
            source_module="procurement",
            actor_id=user_id,
            db=db,
        )

        return po

    @staticmethod
    def cancel_purchase_order(
        db: Session,
        po_number: str,
        req: PurchaseOrderCancelRequest,
        user_id: int,
    ) -> PurchaseOrder:
        # Hierarchical lock ordering: ProcurementBudget -> PurchaseOrder
        po_brief = db.execute(
            select(PurchaseOrder.budget_id).where(PurchaseOrder.po_number == po_number)
        ).first()
        if not po_brief:
            raise NotFoundException(f"Purchase order '{po_number}' not found")

        budget = None
        if po_brief[0]:
            budget = db.execute(
                select(ProcurementBudget)
                .where(ProcurementBudget.id == po_brief[0])
                .with_for_update()
            ).scalar_one_or_none()

        po = db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.po_number == po_number)
            .with_for_update()
        ).scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Purchase order '{po_number}' not found")
        if po.status in (POStatus.COMPLETED, POStatus.CANCELLED):
            raise BadRequestException(f"Cannot cancel PO in status '{po.status.value}'")

        # Release or refund budget allocation
        if budget:
            avail = budget.total_amount_inr - budget.spent_amount_inr - budget.reserved_amount_inr
            if po.status == POStatus.SUBMITTED:
                new_avail = avail + po.total_committed_spend_inr
                budget.reserved_amount_inr -= po.total_committed_spend_inr
                ledger = BudgetLedgerEntry(
                    budget_id=budget.id,
                    transaction_type=BudgetTransactionType.RELEASE,
                    amount_inr=po.total_committed_spend_inr,
                    previous_balance_inr=avail,
                    new_balance_inr=new_avail,
                    po_number=po_number,
                    created_by_user_id=user_id,
                    description=f"Released reservation for cancelled PO {po_number}: {req.reason}",
                )
                db.add(ledger)
            elif po.status == POStatus.CONFIRMED:
                new_avail = avail + po.total_committed_spend_inr
                budget.spent_amount_inr -= po.total_committed_spend_inr
                ledger = BudgetLedgerEntry(
                    budget_id=budget.id,
                    transaction_type=BudgetTransactionType.REFUND,
                    amount_inr=po.total_committed_spend_inr,
                    previous_balance_inr=avail,
                    new_balance_inr=new_avail,
                    po_number=po_number,
                    created_by_user_id=user_id,
                    description=f"Refunded commitment for cancelled confirmed PO {po_number}: {req.reason}",
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

        # Trigger business notification for PO cancellation
        NotificationService.notify_sync(
            event_type=EventTypes.PROCUREMENT_PO_REJECTED,
            title="Purchase Order Cancelled",
            message=f"Purchase Order {po.po_number} has been cancelled: {req.reason}.",
            recipient_ids=[user_id],
            roles=[RoleNames.PROCUREMENT_MANAGER],
            category=NotificationCategory.PROCUREMENT.value,
            severity="WARNING",
            entity_type="purchase_order",
            entity_id=po.po_number,
            source_module="procurement",
            actor_id=user_id,
            db=db,
        )

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
        # Hierarchical row locking across processes: PurchaseOrder -> PurchaseOrderLine -> PurchaseOrderFulfillment
        po = db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.po_number == po_number)
            .with_for_update()
        ).scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Purchase order '{po_number}' not found")
        if po.status == POStatus.CANCELLED:
            raise BadRequestException(f"Cannot fulfill purchase order in status '{po.status.value}'")

        line = db.execute(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.id == line_id,
                PurchaseOrderLine.po_number == po_number,
            ).with_for_update()
        ).scalar_one_or_none()
        if not line:
            raise NotFoundException(f"Line {line_id} not found on PO '{po_number}'")

        # Validate against over-delivery using row-level locking
        prior_delivered = db.execute(
            select(func.coalesce(func.sum(PurchaseOrderFulfillment.delivered_qty), 0))
            .where(PurchaseOrderFulfillment.po_line_id == line.id)
        ).scalar_one()

        if prior_delivered + req.delivered_qty > line.ordered_qty:
            raise BadRequestException(
                f"Over-delivery rejected. Line ordered quantity: {line.ordered_qty}, already delivered: {prior_delivered}, attempted: {req.delivered_qty}."
            )

        actual_cost = req.actual_unit_cost_inr or line.unit_cost_inr
        total_cost = req.delivered_qty * actual_cost

        new_total_delivered = prior_delivered + req.delivered_qty
        is_line_complete = (new_total_delivered >= line.ordered_qty)

        ful = PurchaseOrderFulfillment(
            po_line_id=line.id,
            delivered_qty=req.delivered_qty,
            delivered_at=req.delivered_at or datetime.utcnow(),
            actual_unit_cost_inr=actual_cost,
            actual_total_cost_inr=total_cost,
            fulfilled_units=req.delivered_qty,
            status=FulfillmentStatus.DELIVERED if is_line_complete else FulfillmentStatus.PARTIALLY_DELIVERED,
            notes=req.notes,
        )
        db.add(ful)
        db.flush()

        # Check if all lines for the purchase order are now completely fulfilled
        all_lines = db.execute(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_number == po_number).with_for_update()
        ).scalars().all()

        all_complete = True
        for l in all_lines:
            tot_deliv = db.execute(
                select(func.coalesce(func.sum(PurchaseOrderFulfillment.delivered_qty), 0))
                .where(PurchaseOrderFulfillment.po_line_id == l.id)
            ).scalar_one()
            if tot_deliv < l.ordered_qty:
                all_complete = False
                break

        if all_complete:
            po.status = POStatus.COMPLETED
            po.notes = f"{po.notes or ''}\n[Fulfillment Completed]: All lines fully delivered.".strip()
        elif po.status != POStatus.CONFIRMED:
            po.status = POStatus.CONFIRMED

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
        # Hierarchical lock ordering: PurchaseOrder -> PurchaseOrderLine -> PurchaseOrderFulfillment
        ful_query = db.execute(
            select(PurchaseOrderFulfillment.po_line_id).where(PurchaseOrderFulfillment.id == fulfillment_id)
        ).first()
        if not ful_query:
            raise NotFoundException(f"Fulfillment {fulfillment_id} not found")

        line_id = ful_query[0]
        line_brief = db.execute(
            select(PurchaseOrderLine.po_number).where(PurchaseOrderLine.id == line_id)
        ).first()
        if not line_brief:
            raise NotFoundException(f"Line {line_id} associated with fulfillment not found")

        po_number = line_brief[0]
        po = db.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number).with_for_update()
        ).scalar_one_or_none()
        if not po:
            raise NotFoundException(f"Purchase order '{po_number}' not found")

        line = db.execute(
            select(PurchaseOrderLine).where(PurchaseOrderLine.id == line_id).with_for_update()
        ).scalar_one_or_none()
        if not line:
            raise NotFoundException(f"Line {line_id} associated with fulfillment not found")

        ful = db.execute(
            select(PurchaseOrderFulfillment)
            .where(PurchaseOrderFulfillment.id == fulfillment_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not ful:
            raise NotFoundException(f"Fulfillment {fulfillment_id} not found")

        update_data = req.model_dump(exclude_unset=True)

        # Validate against over-delivery if quantity changed
        if "delivered_qty" in update_data:
            new_qty = update_data["delivered_qty"]
            other_delivered = db.execute(
                select(func.coalesce(func.sum(PurchaseOrderFulfillment.delivered_qty), 0))
                .where(
                    PurchaseOrderFulfillment.po_line_id == line.id,
                    PurchaseOrderFulfillment.id != fulfillment_id,
                )
            ).scalar_one()
            if other_delivered + new_qty > line.ordered_qty:
                raise BadRequestException(
                    f"Over-delivery rejected. Line ordered quantity: {line.ordered_qty}, already delivered by other records: {other_delivered}, updated: {new_qty}."
                )

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
            select(PurchaseOrderFulfillment)
            .where(PurchaseOrderFulfillment.id == fulfillment_id)
            .with_for_update()
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
