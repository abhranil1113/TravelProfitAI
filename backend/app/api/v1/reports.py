from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import ReportStatus, User, UserRole
from backend.app.schemas.report import (
    ReportCreateRequest,
    ReportListResponse,
    ReportResponse,
    ReportScheduleCreateRequest,
    ReportScheduleListResponse,
    ReportScheduleResponse,
    ReportScheduleUpdateRequest,
)
from backend.app.services.report_service import ReportService

reports_router = APIRouter(prefix="/reports", tags=["16. Reports & Schedules"])
report_schedules_router = APIRouter(prefix="/report-schedules", tags=["16. Reports & Schedules"])


# --- Reports (144-149) ---

@reports_router.get(
    "",
    response_model=ReportListResponse,
)
def list_reports(
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    report_type: Optional[str] = None,
    report_status: Optional[ReportStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """144. List generated and pending reports with status and type filters."""
    items, total = ReportService.list_reports(db, report_type=report_type, report_status=report_status, page=page, page_size=page_size)
    return ReportListResponse(
        items=[ReportResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@reports_router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    req: ReportCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """145. Generate an on-demand report artifact."""
    report = ReportService.create_report(db, req, current_user.id)
    return ReportResponse.model_validate(report)


@reports_router.get(
    "/{report_id}",
    response_model=ReportResponse,
)
def get_report(
    report_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """146. Get metadata and status of a specific generated report."""
    return ReportService.get_report(db, report_id)


@reports_router.get(
    "/{report_id}/download",
)
def download_report(
    report_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """147. Download the rendered report document."""
    content, media_type, filename = ReportService.download_report(db, report_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.post(
    "/{report_id}/regenerate",
    response_model=ReportResponse,
)
def regenerate_report(
    report_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """148. Trigger regeneration of an existing report."""
    report = ReportService.regenerate_report(db, report_id, current_user.id)
    return ReportResponse.model_validate(report)


@reports_router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_report(
    report_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """149. Delete report record and associated storage artifact."""
    ReportService.delete_report(db, report_id, current_user.id)
    return None


# --- Report Schedules (150-154) ---

@report_schedules_router.get(
    "",
    response_model=ReportScheduleListResponse,
)
def list_report_schedules(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """150. List all automated report generation schedules."""
    items = ReportService.list_schedules(db)
    return ReportScheduleListResponse(
        items=[ReportScheduleResponse.model_validate(i) for i in items],
        total=len(items),
    )


@report_schedules_router.post(
    "",
    response_model=ReportScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report_schedule(
    req: ReportScheduleCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """151. Create a cron-based automated report schedule."""
    sched = ReportService.create_schedule(db, req, current_user.id)
    return ReportScheduleResponse.model_validate(sched)


@report_schedules_router.patch(
    "/{id}",
    response_model=ReportScheduleResponse,
)
def update_report_schedule(
    id: int,
    req: ReportScheduleUpdateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """152. Update parameters or cron expression of report schedule."""
    sched = ReportService.update_schedule(db, id, req, current_user.id)
    return ReportScheduleResponse.model_validate(sched)


@report_schedules_router.post(
    "/{id}/enable",
    response_model=ReportScheduleResponse,
)
def toggle_report_schedule_enable(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """153. Enable or disable automated report schedule execution."""
    sched = ReportService.enable_schedule(db, id, current_user.id)
    return ReportScheduleResponse.model_validate(sched)


@report_schedules_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_report_schedule(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """154. Delete a scheduled report definition."""
    ReportService.delete_schedule(db, id, current_user.id)
    return None
