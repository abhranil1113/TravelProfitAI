from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import AppBaseException
from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import InventoryCategory, OfferStatus, User, UserRole
from backend.app.schemas.inventory import InventorySnapshotResponse
from backend.app.schemas.supplier_offer import (
    BulkImportResponse,
    OfferPredictionBriefResponse,
    SupplierOfferCreateRequest,
    SupplierOfferListResponse,
    SupplierOfferResponse,
    SupplierOfferUpdateRequest,
)
from backend.app.services.supplier_offer_service import SupplierOfferService

router = APIRouter(prefix="/supplier-offers", tags=["6. Supplier Offers"])


@router.get("", response_model=SupplierOfferListResponse)
def list_supplier_offers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    supplier: Optional[str] = None,
    dest: Optional[str] = None,
    category: Optional[InventoryCategory] = None,
    status: Optional[OfferStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List supplier offers with rich multi-criteria filters."""
    items, total = SupplierOfferService.list_offers(
        db,
        supplier_id=supplier,
        dest_id=dest,
        category=category,
        status=status,
        start_travel_date=start_date,
        end_travel_date=end_date,
        min_price=min_price,
        max_price=max_price,
        page=page,
        page_size=page_size,
    )
    result = [SupplierOfferResponse.model_validate(o) for o in items]
    return SupplierOfferListResponse(items=result, total=total, page=page, page_size=page_size)


@router.post("", response_model=SupplierOfferResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_offer(
    payload: SupplierOfferCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new supplier offer (Admin only)."""
    offer = SupplierOfferService.create_offer(db, payload, user_id=current_admin.id)
    return SupplierOfferResponse.model_validate(offer)


# NOTE: Defined BEFORE /{offer_id} so static path is not captured by param!
@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_offers(
    file: UploadFile = File(...),
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """CSV upload for asynchronous / bulk offer creation & updates (Tier 2)."""
    if not file.filename.endswith(".csv"):
        raise AppBaseException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are accepted for bulk offer import.",
            error_code="INVALID_FILE_TYPE",
        )
    content = await file.read()
    csv_text = content.decode("utf-8")
    return SupplierOfferService.bulk_import_csv(db, csv_text, user_id=current_admin.id)


@router.get("/{offer_id}", response_model=SupplierOfferResponse)
def get_supplier_offer_detail(
    offer_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get offer details with latest ML prediction and inventory snapshot."""
    offer, pred, snap = SupplierOfferService.get_offer_detail(db, offer_id)
    resp = SupplierOfferResponse.model_validate(offer)
    if pred:
        resp.latest_prediction = OfferPredictionBriefResponse.model_validate(pred)
    if snap:
        resp.latest_snapshot = InventorySnapshotResponse.model_validate(snap)
    return resp


@router.patch("/{offer_id}", response_model=SupplierOfferResponse)
def update_supplier_offer(
    offer_id: str,
    payload: SupplierOfferUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update supplier offer terms, MOQ, capacity, pricing (Admin only)."""
    offer = SupplierOfferService.update_offer(db, offer_id, payload, user_id=current_admin.id)
    return SupplierOfferResponse.model_validate(offer)


@router.post("/{offer_id}/expire", response_model=SupplierOfferResponse)
def expire_supplier_offer(
    offer_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Manually expire a supplier offer."""
    offer = SupplierOfferService.expire_offer(db, offer_id, user_id=current_user.id)
    return SupplierOfferResponse.model_validate(offer)


@router.get("/{offer_id}/predictions", response_model=list[OfferPredictionBriefResponse])
def get_supplier_offer_predictions(
    offer_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get historical ML predictions for this offer."""
    preds = SupplierOfferService.get_predictions(db, offer_id)
    return [OfferPredictionBriefResponse.model_validate(p) for p in preds]
