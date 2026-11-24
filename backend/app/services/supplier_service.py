from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.exceptions import ConflictError, EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    OfferStatus,
    PurchaseOrder,
    Supplier,
    SupplierContact,
    SupplierOffer,
    SupplierPerformanceSnapshot,
    SupplierType,
)
from backend.app.schemas.supplier import (
    SupplierContactCreateRequest,
    SupplierContactUpdateRequest,
    SupplierCreateRequest,
    SupplierUpdateRequest,
)


class SupplierService:
    @staticmethod
    def list_suppliers(
        db: Session,
        supplier_type: Optional[SupplierType] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Supplier], int]:
        query = db.query(Supplier)
        if supplier_type:
            query = query.filter(Supplier.supplier_type == supplier_type)
        if is_active is not None:
            query = query.filter(Supplier.is_active == is_active)

        total = query.count()
        suppliers = query.order_by(Supplier.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return suppliers, total

    @staticmethod
    def create_supplier(db: Session, payload: SupplierCreateRequest, user_id: int) -> Supplier:
        supplier_id = payload.supplier_id.upper().strip()
        if db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first():
            raise ConflictError(f"Supplier with ID '{supplier_id}' already exists.")

        supplier = Supplier(
            supplier_id=supplier_id,
            name=payload.name.strip(),
            supplier_type=payload.supplier_type,
            fulfillment_rate=payload.fulfillment_rate,
            avg_lead_time_days=payload.avg_lead_time_days,
            cancellation_lead_time_days=payload.cancellation_lead_time_days,
            flight_salvage_rate=payload.flight_salvage_rate,
            max_portfolio_share=payload.max_portfolio_share,
            is_active=payload.is_active,
        )
        db.add(supplier)
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_CREATED",
            entity_type="suppliers",
            entity_id=supplier_id,
            details_json={"name": supplier.name, "type": supplier.supplier_type.value},
        ))
        db.commit()
        db.refresh(supplier)
        return supplier

    @staticmethod
    def get_supplier(db: Session, supplier_id: str) -> Supplier:
        supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id.upper()).first()
        if not supplier:
            raise EntityNotFoundError("Supplier", supplier_id)
        return supplier

    @staticmethod
    def update_supplier(db: Session, supplier_id: str, payload: SupplierUpdateRequest, user_id: int) -> Supplier:
        supplier = SupplierService.get_supplier(db, supplier_id)
        updates = {}

        if payload.name is not None:
            supplier.name = payload.name.strip()
            updates["name"] = supplier.name
        if payload.supplier_type is not None:
            supplier.supplier_type = payload.supplier_type
            updates["supplier_type"] = supplier.supplier_type.value
        if payload.fulfillment_rate is not None:
            supplier.fulfillment_rate = payload.fulfillment_rate
            updates["fulfillment_rate"] = supplier.fulfillment_rate
        if payload.avg_lead_time_days is not None:
            supplier.avg_lead_time_days = payload.avg_lead_time_days
            updates["avg_lead_time_days"] = supplier.avg_lead_time_days
        if payload.cancellation_lead_time_days is not None:
            supplier.cancellation_lead_time_days = payload.cancellation_lead_time_days
            updates["cancellation_lead_time_days"] = supplier.cancellation_lead_time_days
        if payload.flight_salvage_rate is not None:
            supplier.flight_salvage_rate = payload.flight_salvage_rate
            updates["flight_salvage_rate"] = supplier.flight_salvage_rate
        if payload.max_portfolio_share is not None:
            supplier.max_portfolio_share = payload.max_portfolio_share
            updates["max_portfolio_share"] = supplier.max_portfolio_share
        if payload.is_active is not None:
            supplier.is_active = payload.is_active
            updates["is_active"] = supplier.is_active

        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_UPDATED",
            entity_type="suppliers",
            entity_id=supplier_id,
            details_json=updates,
        ))
        db.commit()
        db.refresh(supplier)
        return supplier

    @staticmethod
    def delete_supplier(db: Session, supplier_id: str, user_id: int) -> Supplier:
        supplier = SupplierService.get_supplier(db, supplier_id)
        supplier.is_active = False
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_DEACTIVATED",
            entity_type="suppliers",
            entity_id=supplier_id,
        ))
        db.commit()
        db.refresh(supplier)
        return supplier

    @staticmethod
    def get_performance_snapshots(db: Session, supplier_id: str) -> list[SupplierPerformanceSnapshot]:
        SupplierService.get_supplier(db, supplier_id)
        return db.query(SupplierPerformanceSnapshot).filter(
            SupplierPerformanceSnapshot.supplier_id == supplier_id.upper()
        ).order_by(SupplierPerformanceSnapshot.snapshot_date.desc()).all()

    @staticmethod
    def get_active_offers(db: Session, supplier_id: str) -> list[SupplierOffer]:
        SupplierService.get_supplier(db, supplier_id)
        return db.query(SupplierOffer).filter(
            SupplierOffer.supplier_id == supplier_id.upper(),
            SupplierOffer.status == OfferStatus.ACTIVE,
        ).order_by(SupplierOffer.travel_date.asc()).all()

    @staticmethod
    def get_purchase_orders(db: Session, supplier_id: str) -> list[PurchaseOrder]:
        SupplierService.get_supplier(db, supplier_id)
        return db.query(PurchaseOrder).filter(
            PurchaseOrder.supplier_id == supplier_id.upper()
        ).order_by(PurchaseOrder.ordered_at.desc()).all()

    @staticmethod
    def list_contacts(db: Session, supplier_id: str) -> list[SupplierContact]:
        SupplierService.get_supplier(db, supplier_id)
        return db.query(SupplierContact).filter(
            SupplierContact.supplier_id == supplier_id.upper()
        ).order_by(SupplierContact.is_primary.desc(), SupplierContact.name.asc()).all()

    @staticmethod
    def add_contact(db: Session, supplier_id: str, payload: SupplierContactCreateRequest, user_id: int) -> SupplierContact:
        SupplierService.get_supplier(db, supplier_id)
        sid = supplier_id.upper()

        if payload.is_primary:
            # Enforce at most one primary contact
            db.query(SupplierContact).filter(
                SupplierContact.supplier_id == sid,
                SupplierContact.is_primary == True,
            ).update({"is_primary": False})

        contact = SupplierContact(
            supplier_id=sid,
            name=payload.name.strip(),
            contact_role=payload.contact_role,
            email=payload.email,
            phone=payload.phone,
            is_primary=payload.is_primary,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    @staticmethod
    def update_contact(db: Session, contact_id: int, payload: SupplierContactUpdateRequest, user_id: int) -> SupplierContact:
        contact = db.query(SupplierContact).filter(SupplierContact.id == contact_id).first()
        if not contact:
            raise EntityNotFoundError("SupplierContact", contact_id)

        if payload.is_primary is True:
            db.query(SupplierContact).filter(
                SupplierContact.supplier_id == contact.supplier_id,
                SupplierContact.id != contact_id,
                SupplierContact.is_primary == True,
            ).update({"is_primary": False})

        if payload.name is not None:
            contact.name = payload.name.strip()
        if payload.contact_role is not None:
            contact.contact_role = payload.contact_role
        if payload.email is not None:
            contact.email = payload.email
        if payload.phone is not None:
            contact.phone = payload.phone
        if payload.is_primary is not None:
            contact.is_primary = payload.is_primary

        db.commit()
        db.refresh(contact)
        return contact

    @staticmethod
    def delete_contact(db: Session, contact_id: int, user_id: int) -> None:
        contact = db.query(SupplierContact).filter(SupplierContact.id == contact_id).first()
        if not contact:
            raise EntityNotFoundError("SupplierContact", contact_id)
        db.delete(contact)
        db.commit()

    @staticmethod
    def set_primary_contact(db: Session, contact_id: int, user_id: int) -> SupplierContact:
        contact = db.query(SupplierContact).filter(SupplierContact.id == contact_id).first()
        if not contact:
            raise EntityNotFoundError("SupplierContact", contact_id)

        # Unset all other contacts for this supplier
        db.query(SupplierContact).filter(
            SupplierContact.supplier_id == contact.supplier_id,
            SupplierContact.id != contact_id,
        ).update({"is_primary": False})

        contact.is_primary = True
        db.commit()
        db.refresh(contact)
        return contact
