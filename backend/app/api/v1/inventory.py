from __future__ import annotations

from typing import Annotated, Optional, Union
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import InventoryCategory, User, UserRole
from backend.app.schemas.auth import AuthMessageResponse
from backend.app.schemas.inventory import (
    BulkInventorySnapshotRequest,
    InventoryItemCreateRequest,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemUpdateRequest,
    InventorySnapshotCreateRequest,
    InventorySnapshotResponse,
)
from backend.app.schemas.supplier_offer import SupplierOfferResponse
from backend.app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory-items", tags=["5. Inventory Items & Snapshots"])
snapshots_router = APIRouter(prefix="/inventory-snapshots", tags=["5. Inventory Items & Snapshots"])


@router.get("", response_model=InventoryItemListResponse)
def list_inventory_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    category: Optional[InventoryCategory] = None,
    dest: Optional[str] = None,
    active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List inventory items with category, destination, active filters and pagination."""
    items, total = InventoryService.list_inventory_items(
        db, category=category, dest_id=dest, is_active=active, page=page, page_size=page_size
    )
    result = []
    for item in items:
        resp = InventoryItemResponse.model_validate(item)
        result.append(resp)
    return InventoryItemListResponse(items=result, total=total, page=page, page_size=page_size)


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryItemCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create new inventory item (Admin only, Tier 2)."""
    item = InventoryService.create_inventory_item(db, payload, user_id=current_admin.id)
    return InventoryItemResponse.model_validate(item)


@router.get("/{inventory_id}", response_model=InventoryItemResponse)
def get_inventory_item_detail(
    inventory_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get inventory item detail with latest inventory snapshot."""
    item, snapshot = InventoryService.get_inventory_item(db, inventory_id)
    resp = InventoryItemResponse.model_validate(item)
    if snapshot:
        resp.latest_snapshot = InventorySnapshotResponse.model_validate(snapshot)
    return resp


@router.patch("/{inventory_id}", response_model=InventoryItemResponse)
def update_inventory_item(
    inventory_id: str,
    payload: InventoryItemUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update inventory item properties (Admin only, Tier 2)."""
    item = InventoryService.update_inventory_item(db, inventory_id, payload, user_id=current_admin.id)
    return InventoryItemResponse.model_validate(item)


@router.get("/{inventory_id}/snapshots", response_model=list[InventorySnapshotResponse])
def get_inventory_snapshots(
    inventory_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(30, ge=1, le=100),
):
    """Get time-series inventory snapshots for item."""
    snapshots = InventoryService.get_snapshots(db, inventory_id, limit=limit)
    return [InventorySnapshotResponse.model_validate(s) for s in snapshots]


@router.get("/{inventory_id}/offers", response_model=list[SupplierOfferResponse])
def get_item_supplier_offers(
    inventory_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get all supplier offers for inventory item."""
    offers = InventoryService.get_offers_for_item(db, inventory_id)
    return [SupplierOfferResponse.model_validate(o) for o in offers]


# --- Snapshots Standalone Ingestion Endpoints ---

@snapshots_router.post("/bulk", response_model=AuthMessageResponse, status_code=status.HTTP_201_CREATED)
def bulk_upsert_snapshots(
    payload: Union[BulkInventorySnapshotRequest, list[InventorySnapshotCreateRequest]],
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Bulk upsert inventory snapshots (Worker/Admin only, Tier 2)."""
    snapshots_list = payload.snapshots if isinstance(payload, BulkInventorySnapshotRequest) else payload
    count = InventoryService.bulk_create_snapshots(db, snapshots_list)
    return AuthMessageResponse(message=f"Successfully ingested {count} inventory snapshots.")


@snapshots_router.post("", response_model=InventorySnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    payload: InventorySnapshotCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Ingest single inventory snapshot (Worker/Admin only, Tier 2)."""
    snap = InventoryService.create_snapshot(db, payload)
    return InventorySnapshotResponse.model_validate(snap)
