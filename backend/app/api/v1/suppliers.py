from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import SupplierType, User, UserRole
from backend.app.schemas.auth import AuthMessageResponse
from backend.app.schemas.supplier import (
    SupplierContactCreateRequest,
    SupplierContactResponse,
    SupplierContactUpdateRequest,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierPerformanceSnapshotResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from backend.app.schemas.supplier_offer import SupplierOfferResponse
from backend.app.services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["4. Suppliers & Contacts"])
contacts_router = APIRouter(prefix="/supplier-contacts", tags=["4. Suppliers & Contacts"])


# --- Suppliers Endpoints ---

@router.get("", response_model=SupplierListResponse)
def list_suppliers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    type: Optional[SupplierType] = None,
    active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List suppliers with filtering by type, active status, and pagination."""
    items, total = SupplierService.list_suppliers(
        db, supplier_type=type, is_active=active, page=page, page_size=page_size
    )
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new supplier profile (Admin only)."""
    sup = SupplierService.create_supplier(db, payload, user_id=current_admin.id)
    return SupplierResponse.model_validate(sup)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier_detail(
    supplier_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get supplier details."""
    sup = SupplierService.get_supplier(db, supplier_id)
    return SupplierResponse.model_validate(sup)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: str,
    payload: SupplierUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update supplier caps, salvage, fulfillment rate, lead time (Admin only)."""
    sup = SupplierService.update_supplier(db, supplier_id, payload, user_id=current_admin.id)
    return SupplierResponse.model_validate(sup)


@router.delete("/{supplier_id}", response_model=AuthMessageResponse)
def delete_supplier(
    supplier_id: str,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Soft-disable supplier profile (Admin only, Tier 2)."""
    sup = SupplierService.delete_supplier(db, supplier_id, user_id=current_admin.id)
    return AuthMessageResponse(message=f"Supplier {sup.supplier_id} soft-disabled successfully.", status="INACTIVE", is_active=False)


@router.get("/{supplier_id}/performance-snapshots", response_model=list[SupplierPerformanceSnapshotResponse])
def get_supplier_performance(
    supplier_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get time-series performance KPIs for a supplier."""
    snapshots = SupplierService.get_performance_snapshots(db, supplier_id)
    return [SupplierPerformanceSnapshotResponse.model_validate(s) for s in snapshots]


@router.get("/{supplier_id}/offers", response_model=list[SupplierOfferResponse])
def get_supplier_offers(
    supplier_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get active inventory procurement offers for a supplier."""
    offers = SupplierService.get_active_offers(db, supplier_id)
    return [SupplierOfferResponse.model_validate(o) for o in offers]


@router.get("/{supplier_id}/purchase-orders")
def get_supplier_purchase_orders(
    supplier_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get purchase order history for a supplier."""
    orders = SupplierService.get_purchase_orders(db, supplier_id)
    return [
        {
            "po_number": o.po_number,
            "supplier_id": o.supplier_id,
            "status": o.status.value,
            "total_committed_spend_inr": o.total_committed_spend_inr,
            "currency": o.currency,
            "ordered_at": o.ordered_at,
        }
        for o in orders
    ]


@router.get("/{supplier_id}/contacts", response_model=list[SupplierContactResponse])
def list_supplier_contacts(
    supplier_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """List all contacts for a supplier."""
    contacts = SupplierService.list_contacts(db, supplier_id)
    return [SupplierContactResponse.model_validate(c) for c in contacts]


@router.post("/{supplier_id}/contacts", response_model=SupplierContactResponse, status_code=status.HTTP_201_CREATED)
def add_supplier_contact(
    supplier_id: str,
    payload: SupplierContactCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Add a new contact to a supplier (Admin only)."""
    contact = SupplierService.add_contact(db, supplier_id, payload, user_id=current_admin.id)
    return SupplierContactResponse.model_validate(contact)


# --- Supplier Contacts Standalone Endpoints ---

@contacts_router.patch("/{id}", response_model=SupplierContactResponse)
def update_supplier_contact(
    id: int,
    payload: SupplierContactUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update supplier contact details (Admin only)."""
    contact = SupplierService.update_contact(db, id, payload, user_id=current_admin.id)
    return SupplierContactResponse.model_validate(contact)


@contacts_router.delete("/{id}", response_model=AuthMessageResponse)
def delete_supplier_contact(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete supplier contact (Admin only, Tier 2)."""
    SupplierService.delete_contact(db, id, user_id=current_admin.id)
    return AuthMessageResponse(message=f"Contact {id} deleted successfully.")


@contacts_router.post("/{id}/set-primary", response_model=SupplierContactResponse)
def set_primary_supplier_contact(
    id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Reassign primary flag to this contact (Admin only, Tier 2)."""
    contact = SupplierService.set_primary_contact(db, id, user_id=current_admin.id)
    return SupplierContactResponse.model_validate(contact)
