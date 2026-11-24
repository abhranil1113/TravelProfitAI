from __future__ import annotations

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
            query = query.filter(InventoryItem.category == category)
        if dest_id:
            query = query.filter(InventoryItem.dest_id == dest_id.upper())
        if is_active is not None:
            query = query.filter(InventoryItem.is_active == is_active)

        total = query.count()
        items = query.order_by(InventoryItem.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def create_inventory_item(db: Session, payload: InventoryItemCreateRequest, user_id: int) -> InventoryItem:
        inv_id = payload.inventory_id.strip()
        if db.query(InventoryItem).filter(InventoryItem.inventory_id == inv_id).first():
            raise ConflictError(f"Inventory item with ID '{inv_id}' already exists.")

        item = InventoryItem(
            inventory_id=inv_id,
            category=payload.category,
            unit_type=payload.unit_type,
            dest_id=payload.dest_id.upper(),
            origin_dest_id=payload.origin_dest_id.upper() if payload.origin_dest_id else None,
            name=payload.name.strip(),
            reference_code=payload.reference_code,
            star_rating=payload.star_rating,
            total_capacity=payload.total_capacity,
            is_active=payload.is_active,
        )
        db.add(item)
        db.add(AuditLog(
            user_id=user_id,
            action="INVENTORY_ITEM_CREATED",
            entity_type="inventory_items",
            entity_id=inv_id,
            details_json={"name": item.name, "category": item.category.value},
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
        ).order_by(InventorySnapshot.snapshot_date.desc()).first()
        return item, latest_snapshot

    @staticmethod
    def update_inventory_item(
        db: Session, inventory_id: str, payload: InventoryItemUpdateRequest, user_id: int
    ) -> InventoryItem:
        item, _ = InventoryService.get_inventory_item(db, inventory_id)
        updates = {}

        if payload.name is not None:
            item.name = payload.name.strip()
            updates["name"] = item.name
        if payload.reference_code is not None:
            item.reference_code = payload.reference_code
            updates["reference_code"] = item.reference_code
        if payload.star_rating is not None:
            item.star_rating = payload.star_rating
            updates["star_rating"] = item.star_rating
        if payload.total_capacity is not None:
            item.total_capacity = payload.total_capacity
            updates["total_capacity"] = item.total_capacity
        if payload.is_active is not None:
            item.is_active = payload.is_active
            updates["is_active"] = item.is_active

        db.add(AuditLog(
            user_id=user_id,
            action="INVENTORY_ITEM_UPDATED",
            entity_type="inventory_items",
            entity_id=inventory_id,
            details_json=updates,
        ))
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_snapshots(db: Session, inventory_id: str, limit: int = 30) -> list[InventorySnapshot]:
        InventoryService.get_inventory_item(db, inventory_id)
        return db.query(InventorySnapshot).filter(
            InventorySnapshot.inventory_id == inventory_id
        ).order_by(InventorySnapshot.snapshot_date.desc()).limit(limit).all()

    @staticmethod
    def get_offers_for_item(db: Session, inventory_id: str) -> list[SupplierOffer]:
        InventoryService.get_inventory_item(db, inventory_id)
        return db.query(SupplierOffer).filter(
            SupplierOffer.inventory_id == inventory_id
        ).order_by(SupplierOffer.travel_date.asc()).all()

    @staticmethod
    def create_snapshot(db: Session, payload: InventorySnapshotCreateRequest) -> InventorySnapshot:
        snapshot = InventorySnapshot(
            inventory_id=payload.inventory_id,
            snapshot_date=payload.snapshot_date,
            available_units=payload.available_units,
            depletion_velocity=payload.depletion_velocity,
            avg_selling_price_inr=payload.avg_selling_price_inr,
            historical_cancellation_rate=payload.historical_cancellation_rate,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @staticmethod
    def bulk_create_snapshots(db: Session, snapshots_data: list[InventorySnapshotCreateRequest]) -> int:
        records = [
            InventorySnapshot(
                inventory_id=p.inventory_id,
                snapshot_date=p.snapshot_date,
                available_units=p.available_units,
                depletion_velocity=p.depletion_velocity,
                avg_selling_price_inr=p.avg_selling_price_inr,
                historical_cancellation_rate=p.historical_cancellation_rate,
            )
            for p in snapshots_data
        ]
        db.bulk_save_objects(records)
        db.commit()
        return len(records)
