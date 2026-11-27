from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import POStatus, User, UserRole
from backend.app.schemas.procurement import (
    FulfillmentCreateRequest,
    FulfillmentDisputeRequest,
    FulfillmentListResponse,
    FulfillmentResponse,
    FulfillmentUpdateRequest,
    PurchaseOrderCancelRequest,
    PurchaseOrderConfirmRequest,
    PurchaseOrderCreateRequest,
    PurchaseOrderLineResponse,
    PurchaseOrderListResponse,
    PurchaseOrderResponse,
)
from backend.app.services.procurement_service import ProcurementService

router = APIRouter(prefix="/purchase-orders", tags=["15. Purchase Orders & Fulfillment"])
fulfillments_router = APIRouter(prefix="/purchase-order-fulfillments", tags=["15. Purchase Orders & Fulfillment"])


@router.get(
    "",
    response_model=PurchaseOrderListResponse,
)
def list_purchase_orders(
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: Optional[str] = None,
    po_status: Optional[POStatus] = Query(None, alias="status"),
    budget_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """133. List purchase orders with filtering and status breakdown."""
    items, total = ProcurementService.list_purchase_orders(
        db, supplier_id=supplier_id, po_status=po_status, budget_id=budget_id, page=page, page_size=page_size
    )
    return PurchaseOrderListResponse(
        items=[PurchaseOrderResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    req: PurchaseOrderCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """134. Manually create a purchase order with item lines."""
    po = ProcurementService.create_purchase_order(db, req, current_user.id)
    return PurchaseOrderResponse.model_validate(po)


@router.get(
    "/{po_number}",
    response_model=PurchaseOrderResponse,
)
def get_purchase_order(
    po_number: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """135. Get detailed purchase order with lines and fulfillment status."""
    po = ProcurementService.get_purchase_order(db, po_number)
    lines = ProcurementService.list_lines(db, po_number)
    res = PurchaseOrderResponse.model_validate(po)
    res.lines = [PurchaseOrderLineResponse.model_validate(line) for line in lines]
    return res


@router.post(
    "/{po_number}/confirm",
    response_model=PurchaseOrderResponse,
)
def confirm_purchase_order(
    po_number: str,
    req: PurchaseOrderConfirmRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """136. Confirm purchase order acknowledgment by supplier."""
    po = ProcurementService.confirm_purchase_order(db, po_number, req, current_user.id)
    return PurchaseOrderResponse.model_validate(po)


@router.post(
    "/{po_number}/cancel",
    response_model=PurchaseOrderResponse,
)
def cancel_purchase_order(
    po_number: str,
    req: PurchaseOrderCancelRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """137. Cancel purchase order and release allocated financial reservations."""
    po = ProcurementService.cancel_purchase_order(db, po_number, req, current_user.id)
    return PurchaseOrderResponse.model_validate(po)


@router.get(
    "/{po_number}/lines",
    response_model=List[PurchaseOrderLineResponse],
)
def list_purchase_order_lines(
    po_number: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """138. List all inventory item lines belonging to a purchase order."""
    lines = ProcurementService.list_lines(db, po_number)
    return [PurchaseOrderLineResponse.model_validate(line) for line in lines]


@router.get(
    "/{po_number}/export",
)
def export_purchase_order(
    po_number: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    export_format: str = Query("json", alias="format"),
):
    """139. Export purchase order document in JSON or CSV format."""
    content = ProcurementService.export_purchase_order(db, po_number, export_format=export_format)
    media_type = "text/csv" if export_format.lower() == "csv" else "application/json"
    ext = "csv" if export_format.lower() == "csv" else "json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{po_number}.{ext}"'},
    )


@router.get(
    "/{po_number}/fulfillments",
    response_model=List[FulfillmentResponse],
)
def list_po_fulfillments(
    po_number: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """140. List all fulfillment delivery batches recorded for a purchase order."""
    items = ProcurementService.list_fulfillments(db, po_number)
    return [FulfillmentResponse.model_validate(i) for i in items]


@router.post(
    "/{po_number}/lines/{line_id}/fulfillments",
    response_model=FulfillmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_line_fulfillment(
    po_number: str,
    line_id: int,
    req: FulfillmentCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """141. Record delivery or fulfillment receipt for an individual PO line."""
    ful = ProcurementService.record_fulfillment(db, po_number, line_id, req, current_user.id)
    return FulfillmentResponse.model_validate(ful)


# --- Fulfillments direct operations (142, 143) ---

@fulfillments_router.patch(
    "/{id}",
    response_model=FulfillmentResponse,
)
def update_fulfillment(
    id: int,
    req: FulfillmentUpdateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """142. Update fulfillment delivery record with actual unit cost, spoilage, or salvage metrics."""
    ful = ProcurementService.update_fulfillment(db, id, req, current_user.id)
    return FulfillmentResponse.model_validate(ful)


@fulfillments_router.post(
    "/{id}/dispute",
    response_model=FulfillmentResponse,
)
def dispute_fulfillment(
    id: int,
    req: FulfillmentDisputeRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """143. Open a dispute on a delivered fulfillment batch."""
    ful = ProcurementService.dispute_fulfillment(db, id, req, current_user.id)
    return FulfillmentResponse.model_validate(ful)
