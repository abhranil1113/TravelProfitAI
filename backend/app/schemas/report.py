from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import ReportStatus


class ReportCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=128)
    description: Optional[str] = None
    report_type: str = Field("EXECUTIVE_SUMMARY", max_length=64)
    report_format: str = Field("PDF", max_length=16)
    run_id: Optional[str] = None
    comparison_group_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    title: str
    description: Optional[str] = None
    report_type: str
    report_format: str
    status: ReportStatus
    run_id: Optional[str] = None
    comparison_group_id: Optional[str] = None
    parameters_json: Optional[Dict[str, Any]] = None
    artifact_path: Optional[str] = None
    size_bytes: Optional[int] = None
    generated_by_user_id: Optional[int] = None
    generation_started_at: Optional[datetime] = None
    generation_completed_at: Optional[datetime] = None
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int
    page: int
    page_size: int


class ReportScheduleCreateRequest(BaseModel):
    report_type: str = Field(..., min_length=2, max_length=64)
    report_format: str = Field("PDF", max_length=16)
    cron_expression: str = Field("0 8 * * 1", max_length=64)
    parameters: Optional[Dict[str, Any]] = None
    is_enabled: bool = True


class ReportScheduleUpdateRequest(BaseModel):
    cron_expression: Optional[str] = Field(None, max_length=64)
    parameters: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None


class ReportScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_type: str
    report_format: str
    cron_expression: str
    parameters_json: Optional[Dict[str, Any]] = None
    is_enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ReportScheduleListResponse(BaseModel):
    items: List[ReportScheduleResponse]
    total: int
