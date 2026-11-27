from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import (
    ApprovalStatus,
    InventoryCategory,
    User,
    UserRole,
)
from backend.app.schemas.recommendation import (
    BulkRecommendationDecisionRequest,
    BulkRecommendationDecisionResponse,
    RecommendationDecisionRequest,
    RecommendationListResponse,
    RecommendationResponse,
    RejectionListResponse,
    RejectionResponse,
    RejectionSummaryResponse,
)
from backend.app.services.recommendation_service import RecommendationService

recommendations_router = APIRouter(prefix="/recommendations", tags=["14. Recommendations & Rejections"])
run_recommendations_router = APIRouter(prefix="/optimization-runs", tags=["14. Recommendations & Rejections"])


# --- Global Recommendations (178, 125, 126, 127) ---

@recommendations_router.get(
    "",
    response_model=RecommendationListResponse,
)
def list_global_recommendations(
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: Optional[str] = None,
    dest_id: Optional[str] = None,
    category: Optional[InventoryCategory] = None,
    approval_status: Optional[ApprovalStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """178. Global list of procurement recommendations across all optimization runs."""
    items, total = RecommendationService.list_recommendations(
        db,
        run_id=None,
        supplier_id=supplier_id,
        dest_id=dest_id,
        category=category,
        approval_status=approval_status,
        page=page,
        page_size=page_size,
    )
    return RecommendationListResponse(
        items=[RecommendationResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@recommendations_router.get(
    "/{id}",
    response_model=RecommendationResponse,
)
def get_recommendation_detail(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """125. Get detailed single procurement recommendation."""
    return RecommendationService.get_recommendation(db, id)


@recommendations_router.post(
    "/{id}/approve",
    response_model=RecommendationResponse,
)
def approve_recommendation(
    id: int,
    req: RecommendationDecisionRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """126. Approve individual procurement recommendation."""
    return RecommendationService.approve_recommendation(db, id, req.decision_notes, current_user.id)


@recommendations_router.post(
    "/{id}/reject",
    response_model=RecommendationResponse,
)
def reject_recommendation(
    id: int,
    req: RecommendationDecisionRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """127. Reject individual procurement recommendation."""
    return RecommendationService.reject_recommendation(db, id, req.decision_notes, current_user.id)


# --- Run-Scoped Recommendations & Rejections (124, 128-132) ---

@run_recommendations_router.get(
    "/{run_id}/recommendations",
    response_model=RecommendationListResponse,
)
def list_run_recommendations(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    category: Optional[InventoryCategory] = None,
    approval_status: Optional[ApprovalStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """124. List recommended procurement allocations for a specific optimization run."""
    items, total = RecommendationService.list_recommendations(
        db,
        run_id=run_id,
        category=category,
        approval_status=approval_status,
        page=page,
        page_size=page_size,
    )
    return RecommendationListResponse(
        items=[RecommendationResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@run_recommendations_router.post(
    "/{run_id}/recommendations/bulk-approve",
    response_model=BulkRecommendationDecisionResponse,
)
def bulk_approve_recommendations(
    run_id: str,
    req: BulkRecommendationDecisionRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """128. Bulk approve multiple procurement recommendations within a run."""
    return RecommendationService.bulk_approve(db, run_id, req.recommendation_ids, req.decision_notes, current_user.id)


@run_recommendations_router.post(
    "/{run_id}/recommendations/bulk-reject",
    response_model=BulkRecommendationDecisionResponse,
)
def bulk_reject_recommendations(
    run_id: str,
    req: BulkRecommendationDecisionRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """129. Bulk reject multiple procurement recommendations within a run."""
    return RecommendationService.bulk_reject(db, run_id, req.recommendation_ids, req.decision_notes, current_user.id)


@run_recommendations_router.get(
    "/{run_id}/recommendations/export",
)
def export_run_recommendations(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    export_format: str = Query("csv", alias="format"),
):
    """130. Export run recommendations to CSV or JSON format."""
    content = RecommendationService.export_recommendations(db, run_id, export_format=export_format)
    media_type = "application/json" if export_format.lower() == "json" else "text/csv"
    ext = "json" if export_format.lower() == "json" else "csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="recommendations_{run_id}.{ext}"'},
    )


@run_recommendations_router.get(
    "/{run_id}/rejections",
    response_model=RejectionListResponse,
)
def list_run_rejections(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """131. List rejected candidate opportunities with explanation reason codes."""
    items, total = RecommendationService.list_rejections(db, run_id, page=page, page_size=page_size)
    return RejectionListResponse(
        items=[RejectionResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@run_recommendations_router.get(
    "/{run_id}/rejections/summary",
    response_model=RejectionSummaryResponse,
)
def get_run_rejection_summary(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """132. Aggregate summary of rejection reasons and lost opportunity value."""
    return RecommendationService.get_rejection_summary(db, run_id)
