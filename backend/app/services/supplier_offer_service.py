from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.exceptions import ConflictError, EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    IngestionBatch,
    InventoryCategory,
    InventorySnapshot,
    OfferPrediction,
    OfferStatus,
    PipelineStatus,
    SupplierOffer,
    UnitType,
)
from backend.app.schemas.supplier_offer import (
    BulkImportResponse,
    SupplierOfferCreateRequest,
    SupplierOfferUpdateRequest,
)


class SupplierOfferService:
    @staticmethod
    def list_offers(
        db: Session,
        supplier_id: Optional[str] = None,
        dest_id: Optional[str] = None,
        category: Optional[InventoryCategory] = None,
        status: Optional[OfferStatus] = None,
        start_travel_date: Optional[date] = None,
        end_travel_date: Optional[date] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SupplierOffer], int]:
        query = db.query(SupplierOffer)
        if supplier_id:
            query = query.filter(SupplierOffer.supplier_id == supplier_id.upper())
        if dest_id:
            query = query.filter(SupplierOffer.dest_id == dest_id.upper())
        if category:
            query = query.filter(SupplierOffer.inventory_category == category)
        if status:
            query = query.filter(SupplierOffer.status == status)
        if start_travel_date:
            query = query.filter(SupplierOffer.travel_date >= start_travel_date)
        if end_travel_date:
            query = query.filter(SupplierOffer.travel_date <= end_travel_date)
        if min_price is not None:
            query = query.filter(SupplierOffer.cost_per_unit_inr >= min_price)
        if max_price is not None:
            query = query.filter(SupplierOffer.cost_per_unit_inr <= max_price)

        total = query.count()
        offers = query.order_by(SupplierOffer.travel_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return offers, total

    @staticmethod
    def create_offer(db: Session, payload: SupplierOfferCreateRequest, user_id: int) -> SupplierOffer:
        offer_id = payload.offer_id.strip()
        if db.query(SupplierOffer).filter(SupplierOffer.offer_id == offer_id).first():
            raise ConflictError(f"Supplier offer with ID '{offer_id}' already exists.")

        offer = SupplierOffer(
            offer_id=offer_id,
            supplier_id=payload.supplier_id.upper(),
            inventory_id=payload.inventory_id.strip(),
            dest_id=payload.dest_id.upper(),
            origin_dest_id=payload.origin_dest_id.upper() if payload.origin_dest_id else None,
            inventory_category=payload.inventory_category,
            unit_type=payload.unit_type,
            available_qty=payload.available_qty,
            moq=payload.moq,
            cost_per_unit_inr=payload.cost_per_unit_inr,
            currency=payload.currency,
            original_cost=payload.original_cost,
            original_currency=payload.original_currency,
            travel_date=payload.travel_date,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            cancellation_deadline=payload.cancellation_deadline,
            refundable=payload.refundable,
            refund_penalty_pct=payload.refund_penalty_pct,
            status=payload.status,
        )
        db.add(offer)
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_OFFER_CREATED",
            entity_type="supplier_offers",
            entity_id=offer_id,
            details_json={
                "supplier_id": offer.supplier_id,
                "cost_inr": str(offer.cost_per_unit_inr),
                "qty": offer.available_qty,
            },
        ))
        db.commit()
        db.refresh(offer)
        return offer

    @staticmethod
    def get_offer_detail(db: Session, offer_id: str) -> tuple[SupplierOffer, Optional[OfferPrediction], Optional[InventorySnapshot]]:
        offer = db.query(SupplierOffer).filter(SupplierOffer.offer_id == offer_id).first()
        if not offer:
            raise EntityNotFoundError("SupplierOffer", offer_id)

        latest_prediction = db.query(OfferPrediction).filter(
            OfferPrediction.offer_id == offer_id
        ).order_by(OfferPrediction.as_of_date.desc()).first()

        latest_snapshot = db.query(InventorySnapshot).filter(
            InventorySnapshot.inventory_id == offer.inventory_id
        ).order_by(InventorySnapshot.snapshot_date.desc()).first()

        return offer, latest_prediction, latest_snapshot

    @staticmethod
    def update_offer(db: Session, offer_id: str, payload: SupplierOfferUpdateRequest, user_id: int) -> SupplierOffer:
        offer, _, _ = SupplierOfferService.get_offer_detail(db, offer_id)
        updates = {}

        if payload.available_qty is not None:
            offer.available_qty = payload.available_qty
            updates["available_qty"] = offer.available_qty
        if payload.moq is not None:
            offer.moq = payload.moq
            updates["moq"] = offer.moq
        if payload.cost_per_unit_inr is not None:
            offer.cost_per_unit_inr = payload.cost_per_unit_inr
            updates["cost_per_unit_inr"] = str(offer.cost_per_unit_inr)
        if payload.valid_until is not None:
            offer.valid_until = payload.valid_until
            updates["valid_until"] = offer.valid_until.isoformat()
        if payload.cancellation_deadline is not None:
            offer.cancellation_deadline = payload.cancellation_deadline
            updates["cancellation_deadline"] = offer.cancellation_deadline.isoformat()
        if payload.refundable is not None:
            offer.refundable = payload.refundable
            updates["refundable"] = offer.refundable
        if payload.refund_penalty_pct is not None:
            offer.refund_penalty_pct = payload.refund_penalty_pct
            updates["refund_penalty_pct"] = offer.refund_penalty_pct
        if payload.status is not None:
            offer.status = payload.status
            updates["status"] = offer.status.value

        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_OFFER_UPDATED",
            entity_type="supplier_offers",
            entity_id=offer_id,
            details_json=updates,
        ))
        db.commit()
        db.refresh(offer)
        return offer

    @staticmethod
    def expire_offer(db: Session, offer_id: str, user_id: int) -> SupplierOffer:
        offer, _, _ = SupplierOfferService.get_offer_detail(db, offer_id)
        offer.status = OfferStatus.EXPIRED
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_OFFER_EXPIRED",
            entity_type="supplier_offers",
            entity_id=offer_id,
        ))
        db.commit()
        db.refresh(offer)
        return offer

    @staticmethod
    def bulk_import_csv(db: Session, csv_content: str, user_id: int) -> BulkImportResponse:
        batch_uid = f"BATCH-OFFERS-{uuid.uuid4().hex[:10].upper()}"
        batch = IngestionBatch(
            batch_uid=batch_uid,
            dataset_name="supplier_offers_csv",
            source_uri="upload://supplier_offers.csv",
            batch_date=date.today(),
            status=PipelineStatus.RUNNING,
            triggered_by_user_id=user_id,
            processing_started_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        db.commit()

        f = io.StringIO(csv_content.strip())
        reader = csv.DictReader(f)
        rows_received = 0
        rows_imported = 0
        rows_failed = 0

        for row in reader:
            rows_received += 1
            try:
                offer_id = row["offer_id"].strip()
                existing = db.query(SupplierOffer).filter(SupplierOffer.offer_id == offer_id).first()
                if not existing:
                    new_offer = SupplierOffer(
                        offer_id=offer_id,
                        supplier_id=row["supplier_id"].strip().upper(),
                        inventory_id=row["inventory_id"].strip(),
                        dest_id=row["dest_id"].strip().upper(),
                        origin_dest_id=row.get("origin_dest_id", "").strip().upper() or None,
                        inventory_category=InventoryCategory(row["inventory_category"].strip().upper()),
                        unit_type=UnitType(row["unit_type"].strip().upper()),
                        available_qty=int(row["available_qty"]),
                        moq=int(row.get("moq", 1)),
                        cost_per_unit_inr=Decimal(row["cost_per_unit_inr"]),
                        currency=row.get("currency", "INR").strip().upper(),
                        travel_date=datetime.strptime(row["travel_date"].strip(), "%Y-%m-%d").date(),
                        valid_until=datetime.fromisoformat(row["valid_until"].strip()),
                        refundable=row.get("refundable", "false").lower() in ("true", "1", "yes"),
                        status=OfferStatus.ACTIVE,
                    )
                    db.add(new_offer)
                    rows_imported += 1
                else:
                    existing.available_qty = int(row["available_qty"])
                    existing.cost_per_unit_inr = Decimal(row["cost_per_unit_inr"])
                    rows_imported += 1
            except Exception:
                rows_failed += 1

        batch.status = PipelineStatus.SUCCESS if rows_failed == 0 else PipelineStatus.PARTIAL
        batch.rows_ingested = rows_imported
        batch.rows_rejected = rows_failed
        batch.processing_completed_at = datetime.now(timezone.utc)
        db.commit()

        return BulkImportResponse(
            batch_uid=batch_uid,
            rows_received=rows_received,
            rows_valid=rows_imported,
            rows_imported=rows_imported,
            rows_failed=rows_failed,
            status=batch.status.value,
        )

    @staticmethod
    def get_predictions(db: Session, offer_id: str) -> list[OfferPrediction]:
        SupplierOfferService.get_offer_detail(db, offer_id)
        return db.query(OfferPrediction).filter(
            OfferPrediction.offer_id == offer_id
        ).order_by(OfferPrediction.as_of_date.desc()).all()
