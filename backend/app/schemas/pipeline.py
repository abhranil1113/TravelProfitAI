from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import DataQualitySeverity, PipelineStatus


class PipelineBatchTriggerRequest(BaseModel):
    dataset_name: str = Field(..., min_length=2, max_length=64)
    source_uri: str = Field(..., min_length=2, max_length=512)
    batch_date: Optional[date] = None


class DataQualityReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    check_name: str
    severity: DataQualitySeverity
    passed: bool
    violated_rows: int
    total_rows: int
    details_json: Optional[Dict[str, Any]] = None
    created_at: datetime


class IngestionBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_uid: str
    dataset_name: str
    source_uri: str
    batch_date: date
    status: PipelineStatus
    rows_ingested: int
    rows_rejected: int
    rows_duplicates_removed: int
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    processed_parquet_path: Optional[str] = None
    celery_task_id: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class IngestionBatchListResponse(BaseModel):
    items: List[IngestionBatchResponse]
    total: int
    page: int
    page_size: int


class QualitySummaryItem(BaseModel):
    severity: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    pass_rate_pct: float


class QualitySummaryResponse(BaseModel):
    overall_passed: bool
    total_checks_evaluated: int
    by_severity: List[QualitySummaryItem]
