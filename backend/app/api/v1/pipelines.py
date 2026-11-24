from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_current_user, get_db, require_roles
from backend.app.models.schema import PipelineStatus, User, UserRole
from backend.app.schemas.pipeline import (
    DataQualityReportResponse,
    IngestionBatchListResponse,
    IngestionBatchResponse,
    PipelineBatchTriggerRequest,
    QualitySummaryResponse,
)
from backend.app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipelines", tags=["8. Data Pipeline & Quality"])


# NOTE: Defined BEFORE /{batch_uid} so static path is not captured by param!
@router.get("/quality-summary", response_model=QualitySummaryResponse)
def get_pipeline_quality_summary(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Aggregated data quality pass/fail metrics by severity across batches (Tier 2)."""
    return PipelineService.get_quality_summary(db)


@router.get("/batches", response_model=IngestionBatchListResponse)
def list_pipeline_batches(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    dataset: Optional[str] = None,
    status: Optional[PipelineStatus] = None,
    batch_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List data ingestion batches with filtering and pagination (Tier 2)."""
    items, total = PipelineService.list_batches(
        db, dataset_name=dataset, status=status, batch_date=batch_date, page=page, page_size=page_size
    )
    return IngestionBatchListResponse(
        items=[IngestionBatchResponse.model_validate(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/batches", response_model=IngestionBatchResponse, status_code=status.HTTP_201_CREATED)
def trigger_pipeline_batch(
    payload: PipelineBatchTriggerRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Trigger data ingestion batch pipeline asynchronously (Admin only, Tier 2)."""
    batch = PipelineService.trigger_batch(db, payload, user_id=current_admin.id)
    return IngestionBatchResponse.model_validate(batch)


@router.get("/batches/{batch_uid}", response_model=IngestionBatchResponse)
def get_pipeline_batch_detail(
    batch_uid: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get ingestion batch details and row processing rollups (Tier 2)."""
    batch = PipelineService.get_batch(db, batch_uid)
    return IngestionBatchResponse.model_validate(batch)


@router.get("/batches/{batch_uid}/quality-reports", response_model=list[DataQualityReportResponse])
def get_batch_quality_reports(
    batch_uid: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get per-check data quality validation results for a batch (Tier 2)."""
    reports = PipelineService.get_quality_reports(db, batch_uid)
    return [DataQualityReportResponse.model_validate(r) for r in reports]


@router.post("/batches/{batch_uid}/retry", response_model=IngestionBatchResponse)
def retry_pipeline_batch(
    batch_uid: str,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Retry failed data ingestion batch (Admin only, Tier 2)."""
    batch = PipelineService.retry_batch(db, batch_uid, user_id=current_admin.id)
    return IngestionBatchResponse.model_validate(batch)
