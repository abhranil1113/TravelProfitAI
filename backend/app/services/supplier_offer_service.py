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
            query = query.filter(SupplierOffer.unit_cost_inr >= min_price)
        if max_price is not None:
            query = query.filter(SupplierOffer.unit_cost_inr <= max_price)

        total = query.count()
        offers = query.order_by(SupplierOffer.travel_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return offers, total

    @staticmethod
    def create_offer(db: Session, payload: SupplierOfferCreateRequest, user_id: int) -> SupplierOffer:
        offer_id = payload.offer_id.strip()
        if db.query(SupplierOffer).filter(SupplierOffer.offer_id == offer_id).first():
            raise ConflictError(f"Supplier offer with ID '{offer_id}' already exists.")

        from datetime import timedelta
        val_from = payload.valid_from.date() if isinstance(payload.valid_from, datetime) else (payload.valid_from or date.today())
        val_until = payload.valid_until.date() if isinstance(payload.valid_until, datetime) else (payload.valid_until or (date.today() + timedelta(days=30)))
        if val_until < val_from:
            from backend.app.core.exceptions import BadRequestException
            raise BadRequestException(f"valid_from ({val_from.isoformat()}) cannot be after valid_until ({val_until.isoformat()})")
        trav_date = payload.travel_date or val_until
        if trav_date < val_from:
            from backend.app.core.exceptions import BadRequestException
            raise BadRequestException(f"travel_date ({trav_date.isoformat()}) cannot be earlier than valid_from ({val_from.isoformat()})")

        inv_id = payload.inventory_id.strip() if payload.inventory_id else None
        dest_code = payload.dest_id.upper() if payload.dest_id else "BLR"
        from backend.app.models.schema import Destination, InventoryItem
        if inv_id:
            inv = db.query(InventoryItem).filter(InventoryItem.inventory_id == inv_id).first()
            if inv:
                dest_code = inv.dest_id

        # Verify destination exists or fallback
        if not db.query(Destination).filter(Destination.dest_id == dest_code).first():
            existing_dest = db.query(Destination).first()
            if existing_dest:
                dest_code = existing_dest.dest_id
            else:
                new_dest = Destination(
                    dest_id=dest_code,
                    name=dest_code,
                    city=dest_code,
                    country="India",
                    airport_code=dest_code[:3],
                )
                db.add(new_dest)
                db.flush()

        list_price = payload.original_cost if payload.original_cost and payload.original_cost > payload.cost_per_unit_inr else payload.cost_per_unit_inr

        offer = SupplierOffer(
            offer_id=offer_id,
            supplier_id=payload.supplier_id.upper(),
            inventory_id=inv_id,
            dest_id=dest_code,
            origin_dest_id=payload.origin_dest_id.upper() if payload.origin_dest_id else None,
            inventory_category=payload.inventory_category,
            unit_type=payload.unit_type,
            unit_cost_inr=payload.cost_per_unit_inr,
            list_price_inr=list_price,
            currency_code=payload.currency,
            original_unit_cost=payload.original_cost,
            moq=payload.moq,
            max_capacity=payload.available_qty,
            valid_from=val_from,
            valid_until=val_until,
            travel_date=trav_date,
            status=payload.status,
            customer_refund_rate_rc=payload.refund_penalty_pct if payload.refundable else 0.0,
        )
        db.add(offer)
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_OFFER_CREATED",
            entity_type="supplier_offers",
            entity_id=offer_id,
            new_value_json={
                "supplier_id": offer.supplier_id,
                "cost_inr": str(offer.unit_cost_inr),
                "qty": offer.max_capacity,
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
        ).order_by(InventorySnapshot.snapshot_at.desc()).first()

        return offer, latest_prediction, latest_snapshot

    @staticmethod
    def update_offer(db: Session, offer_id: str, payload: SupplierOfferUpdateRequest, user_id: int) -> SupplierOffer:
        offer, _, _ = SupplierOfferService.get_offer_detail(db, offer_id)
        updates = {}

        if payload.available_qty is not None:
            offer.max_capacity = payload.available_qty
            updates["max_capacity"] = offer.max_capacity
        if payload.moq is not None:
            offer.moq = payload.moq
            updates["moq"] = offer.moq
        if payload.cost_per_unit_inr is not None:
            offer.unit_cost_inr = payload.cost_per_unit_inr
            if offer.list_price_inr < offer.unit_cost_inr:
                offer.list_price_inr = offer.unit_cost_inr
            updates["cost_per_unit_inr"] = str(offer.unit_cost_inr)
        if payload.valid_until is not None:
            offer.valid_until = payload.valid_until.date() if isinstance(payload.valid_until, datetime) else payload.valid_until
            updates["valid_until"] = offer.valid_until.isoformat()
        if payload.status is not None:
            offer.status = payload.status
            updates["status"] = offer.status.value

        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_OFFER_UPDATED",
            entity_type="supplier_offers",
            entity_id=offer_id,
            new_value_json=updates,
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
                with db.begin_nested():
                    offer_id = row["offer_id"].strip()
                    existing = db.query(SupplierOffer).filter(SupplierOffer.offer_id == offer_id).first()
                    if not existing:
                        v_until = datetime.fromisoformat(row["valid_until"].strip()).date() if "T" in row["valid_until"] else datetime.strptime(row["valid_until"].strip(), "%Y-%m-%d").date()
                        t_date = datetime.strptime(row["travel_date"].strip(), "%Y-%m-%d").date()
                        if t_date < v_until:
                            raise ValueError(f"travel_date {t_date.isoformat()} cannot precede valid_until {v_until.isoformat()}")
                        new_offer = SupplierOffer(
                            offer_id=offer_id,
                            supplier_id=row["supplier_id"].strip().upper(),
                            inventory_id=row["inventory_id"].strip(),
                            dest_id=row["dest_id"].strip().upper(),
                            origin_dest_id=row.get("origin_dest_id", "").strip().upper() or None,
                            inventory_category=InventoryCategory(row["inventory_category"].strip().upper()),
                            unit_type=UnitType(row["unit_type"].strip().upper()),
                            max_capacity=int(row["available_qty"]),
                            moq=int(row.get("moq", 1)),
                            unit_cost_inr=Decimal(row["cost_per_unit_inr"]),
                            list_price_inr=Decimal(row["cost_per_unit_inr"]) * Decimal("1.20"),
                            currency_code=row.get("currency", "INR").strip().upper(),
                            valid_from=date.today(),
                            valid_until=v_until,
                            travel_date=t_date,
                            status=OfferStatus.ACTIVE,
                        )
                        db.add(new_offer)
                    else:
                        existing.max_capacity = int(row["available_qty"])
                        existing.unit_cost_inr = Decimal(row["cost_per_unit_inr"])
                        existing.list_price_inr = Decimal(row["cost_per_unit_inr"]) * Decimal("1.20")
                    db.flush()
                rows_imported += 1
            except Exception as exc:
                rows_failed += 1
                logger.warning("CSV bulk import row %d rejected: %s", rows_received, exc)

        if rows_imported == 0 and rows_failed > 0:
            batch.status = PipelineStatus.FAILED
        elif rows_failed > 0:
            batch.status = PipelineStatus.PARTIAL
        else:
            batch.status = PipelineStatus.SUCCESS
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
    def bulk_import_json(db: Session, offers_data: list, user_id: int) -> BulkImportResponse:
        batch_uid = f"BATCH-OFFERS-{uuid.uuid4().hex[:10].upper()}"
        imported = 0
        for item in offers_data:
            req = SupplierOfferCreateRequest.model_validate(item)
            SupplierOfferService.create_offer(db, req, user_id=user_id)
            imported += 1
        return BulkImportResponse(
            batch_uid=batch_uid,
            rows_received=len(offers_data),
            rows_valid=imported,
            rows_imported=imported,
            rows_failed=0,
            status="SUCCESS",
            imported_count=imported,
        )

    @staticmethod
    def get_predictions(db: Session, offer_id: str) -> list[OfferPrediction]:
        SupplierOfferService.get_offer_detail(db, offer_id)
        return db.query(OfferPrediction).filter(
            OfferPrediction.offer_id == offer_id
        ).order_by(OfferPrediction.as_of_date.desc()).all()
