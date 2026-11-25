from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.exceptions import ConflictError, EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    InventoryCategory,
    InventoryItem,
    InventorySnapshot,
    SupplierOffer,
)
from backend.app.schemas.inventory import (
    InventoryItemCreateRequest,
    InventoryItemUpdateRequest,
    InventorySnapshotCreateRequest,
)


class InventoryService:
    @staticmethod
    def list_inventory_items(
        db: Session,
        category: Optional[InventoryCategory] = None,
        dest_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InventoryItem], int]:
        query = db.query(InventoryItem)
        if category:
            query = query.filter(InventoryItem.inventory_category == category)
        if dest_id:
            query = query.filter(InventoryItem.dest_id == dest_id.upper())
        if is_active is not None:
            query = query.filter(InventoryItem.is_active == is_active)

        total = query.count()
        items = query.order_by(InventoryItem.inventory_id.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def create_inventory_item(db: Session, payload: InventoryItemCreateRequest, user_id: int) -> InventoryItem:
        inv_id = payload.inventory_id.strip()
        if db.query(InventoryItem).filter(InventoryItem.inventory_id == inv_id).first():
            raise ConflictError(f"Inventory item with ID '{inv_id}' already exists.")

        item = InventoryItem(
            inventory_id=inv_id,
            inventory_category=payload.category,
            unit_type=payload.unit_type,
            dest_id=payload.dest_id.upper(),
            origin_dest_id=payload.origin_dest_id.upper() if payload.origin_dest_id else None,
            external_reference=(payload.name or payload.reference_code or inv_id)[:64],
            is_active=payload.is_active,
        )
        db.add(item)
        db.add(AuditLog(
            user_id=user_id,
            action="INVENTORY_ITEM_CREATED",
            entity_type="inventory_items",
            entity_id=inv_id,
            new_value_json={"category": payload.category.value},
        ))
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_inventory_item(db: Session, inventory_id: str) -> tuple[InventoryItem, Optional[InventorySnapshot]]:
        item = db.query(InventoryItem).filter(InventoryItem.inventory_id == inventory_id).first()
        if not item:
            raise EntityNotFoundError("InventoryItem", inventory_id)
        latest_snapshot = db.query(InventorySnapshot).filter(
            InventorySnapshot.inventory_id == inventory_id
        ).order_by(InventorySnapshot.snapshot_at.desc()).first()
        return item, latest_snapshot

    @staticmethod
    def update_inventory_item(
        db: Session, inventory_id: str, payload: InventoryItemUpdateRequest, user_id: int
    ) -> InventoryItem:
        item, _ = InventoryService.get_inventory_item(db, inventory_id)
        updates = {}

        if payload.name is not None:
            item.external_reference = payload.name.strip()[:64]
            updates["name"] = payload.name.strip()
        if payload.reference_code is not None:
            item.external_reference = payload.reference_code[:64]
            updates["reference_code"] = item.external_reference
        if payload.is_active is not None:
            item.is_active = payload.is_active
            updates["is_active"] = item.is_active

        db.add(AuditLog(
            user_id=user_id,
            action="INVENTORY_ITEM_UPDATED",
            entity_type="inventory_items",
            entity_id=inventory_id,
            new_value_json=updates,
        ))
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_snapshots(db: Session, inventory_id: str, limit: int = 30) -> list[InventorySnapshot]:
        InventoryService.get_inventory_item(db, inventory_id)
        return db.query(InventorySnapshot).filter(
            InventorySnapshot.inventory_id == inventory_id
        ).order_by(InventorySnapshot.snapshot_at.desc()).limit(limit).all()

    @staticmethod
    def get_offers_for_item(db: Session, inventory_id: str) -> list[SupplierOffer]:
        InventoryService.get_inventory_item(db, inventory_id)
        return db.query(SupplierOffer).filter(
            SupplierOffer.inventory_id == inventory_id
        ).order_by(SupplierOffer.travel_date.asc()).all()

    @staticmethod
    def create_snapshot(db: Session, payload: InventorySnapshotCreateRequest) -> InventorySnapshot:
        from backend.app.core.exceptions import BadRequestException
        item = db.query(InventoryItem).filter(InventoryItem.inventory_id == payload.inventory_id).first()
        if not item:
            raise EntityNotFoundError("InventoryItem", payload.inventory_id)
        if payload.available_units < 0:
            raise BadRequestException(f"available_units cannot be negative, got {payload.available_units}")

        cat = item.inventory_category
        snap_dt = datetime.combine(payload.snapshot_date, datetime.min.time()) if isinstance(payload.snapshot_date, date) and not isinstance(payload.snapshot_date, datetime) else (payload.snapshot_date or datetime.utcnow())
        trav_dt = payload.snapshot_date if isinstance(payload.snapshot_date, date) else date.today()
        tot_units = payload.available_units + (getattr(payload, "booked_units", 0) or 0)

        snapshot = InventorySnapshot(
            inventory_id=payload.inventory_id,
            inventory_category=cat,
            travel_date=trav_dt,
            snapshot_at=snap_dt,
            total_units=tot_units,
            available_units=payload.available_units,
            booked_units=getattr(payload, "booked_units", 0) or 0,
            depletion_velocity_per_day=payload.depletion_velocity,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @staticmethod
    def bulk_create_snapshots(db: Session, snapshots_data: list[InventorySnapshotCreateRequest]) -> int:
        from backend.app.core.exceptions import BadRequestException
        records = []
        for p in snapshots_data:
            item = db.query(InventoryItem).filter(InventoryItem.inventory_id == p.inventory_id).first()
            if not item:
                raise EntityNotFoundError("InventoryItem", p.inventory_id)
            if p.available_units < 0:
                raise BadRequestException(f"available_units cannot be negative, got {p.available_units}")

            cat = item.inventory_category
            snap_dt = datetime.combine(p.snapshot_date, datetime.min.time()) if isinstance(p.snapshot_date, date) and not isinstance(p.snapshot_date, datetime) else (p.snapshot_date or datetime.utcnow())
            trav_dt = p.snapshot_date if isinstance(p.snapshot_date, date) else date.today()
            tot_units = p.available_units + (getattr(p, "booked_units", 0) or 0)
            records.append(
                InventorySnapshot(
                    inventory_id=p.inventory_id,
                    inventory_category=cat,
                    travel_date=trav_dt,
                    snapshot_at=snap_dt,
                    total_units=tot_units,
                    available_units=p.available_units,
                    booked_units=getattr(p, "booked_units", 0) or 0,
                    depletion_velocity_per_day=p.depletion_velocity,
                )
            )
        db.bulk_save_objects(records)
        db.commit()
        return len(records)
