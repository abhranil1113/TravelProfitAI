from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from backend.app.models.schema import (
    AuditLog,
    Report,
    ReportSchedule,
    ReportStatus,
)
from backend.app.schemas.report import (
    ReportCreateRequest,
    ReportScheduleCreateRequest,
    ReportScheduleUpdateRequest,
)


class ReportService:

    @staticmethod
    def list_reports(
        db: Session,
        report_type: Optional[str] = None,
        report_status: Optional[ReportStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Report], int]:
        stmt = select(Report)
        if report_type:
            stmt = stmt.where(Report.report_type == report_type)
        if report_status:
            stmt = stmt.where(Report.status == report_status)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def create_report(
        db: Session,
        req: ReportCreateRequest,
        user_id: int,
    ) -> Report:
        rep_id = f"rep_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.utcnow()

        report = Report(
            report_id=rep_id,
            title=req.title,
            description=req.description,
            report_type=req.report_type,
            report_format=req.report_format.upper(),
            status=ReportStatus.COMPLETED,
            run_id=req.run_id,
            comparison_group_id=req.comparison_group_id,
            parameters_json=req.parameters,
            artifact_path=f"reports/{rep_id}.{req.report_format.lower()}",
            size_bytes=16384,
            generated_by_user_id=user_id,
            generation_started_at=now,
            generation_completed_at=now,
        )
        db.add(report)
        db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE_REPORT",
            entity_type="REPORT",
            entity_id=rep_id,
            new_value_json={"title": req.title, "report_type": req.report_type},
        )
        db.add(audit)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def get_report(db: Session, report_id: str) -> Report:
        report = db.execute(
            select(Report).where(Report.report_id == report_id)
        ).scalar_one_or_none()
        if not report:
            raise NotFoundException(f"Report '{report_id}' not found")
        return report

    @staticmethod
    def download_report(db: Session, report_id: str) -> tuple[str, str, str]:
        report = ReportService.get_report(db, report_id)
        fmt = (report.report_format or "PDF").upper()

        if fmt == "JSON":
            content = json.dumps({
                "report_id": report.report_id,
                "title": report.title,
                "report_type": report.report_type,
                "status": report.status.value,
                "generated_at": report.generation_completed_at.isoformat() if report.generation_completed_at else None,
                "parameters": report.parameters_json,
            }, indent=2)
            mime = "application/json"
            ext = "json"
        elif fmt == "CSV":
            content = "report_id,title,report_type,status\n"
            content += f'"{report.report_id}","{report.title}","{report.report_type}","{report.status.value}"\n'
            mime = "text/csv"
            ext = "csv"
        else:
            content = f"%PDF-1.4\n% TBO InventoryIQ Executive Summary: {report.title}\n%%EOF"
            mime = "application/pdf"
            ext = "pdf"

        return content, mime, f"{report.report_id}.{ext}"

    @staticmethod
    def regenerate_report(db: Session, report_id: str, user_id: int) -> Report:
        report = ReportService.get_report(db, report_id)
        now = datetime.utcnow()
        report.generation_started_at = now
        report.generation_completed_at = now
        report.status = ReportStatus.COMPLETED

        audit = AuditLog(
            user_id=user_id,
            action="REGENERATE_REPORT",
            entity_type="REPORT",
            entity_id=report_id,
            new_value_json={"status": ReportStatus.COMPLETED.value},
        )
        db.add(audit)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def delete_report(db: Session, report_id: str, user_id: int) -> None:
        report = ReportService.get_report(db, report_id)
        db.delete(report)
        audit = AuditLog(
            user_id=user_id,
            action="DELETE_REPORT",
            entity_type="REPORT",
            entity_id=report_id,
            new_value_json={"title": report.title},
        )
        db.add(audit)
        db.commit()

    # --- Report Schedules ---

    @staticmethod
    def list_schedules(db: Session) -> List[ReportSchedule]:
        stmt = select(ReportSchedule).order_by(ReportSchedule.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_schedule(
        db: Session,
        req: ReportScheduleCreateRequest,
        user_id: int,
    ) -> ReportSchedule:
        sched = ReportSchedule(
            report_type=req.report_type,
            report_format=req.report_format.upper(),
            cron_expression=req.cron_expression,
            parameters_json=req.parameters,
            is_enabled=req.is_enabled,
            created_by_user_id=user_id,
        )
        db.add(sched)
        db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE_REPORT_SCHEDULE",
            entity_type="REPORT_SCHEDULE",
            entity_id=str(sched.id),
            new_value_json={"report_type": req.report_type, "cron": req.cron_expression},
        )
        db.add(audit)
        db.commit()
        db.refresh(sched)
        return sched

    @staticmethod
    def update_schedule(
        db: Session,
        schedule_id: int,
        req: ReportScheduleUpdateRequest,
        user_id: int,
    ) -> ReportSchedule:
        sched = db.execute(
            select(ReportSchedule).where(ReportSchedule.id == schedule_id)
        ).scalar_one_or_none()
        if not sched:
            raise NotFoundException(f"Schedule {schedule_id} not found")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(sched, field, value)

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE_REPORT_SCHEDULE",
            entity_type="REPORT_SCHEDULE",
            entity_id=str(schedule_id),
            new_value_json=update_data,
        )
        db.add(audit)
        db.commit()
        db.refresh(sched)
        return sched

    @staticmethod
    def enable_schedule(db: Session, schedule_id: int, user_id: int) -> ReportSchedule:
        sched = db.execute(
            select(ReportSchedule).where(ReportSchedule.id == schedule_id)
        ).scalar_one_or_none()
        if not sched:
            raise NotFoundException(f"Schedule {schedule_id} not found")

        sched.is_enabled = not sched.is_enabled
        audit = AuditLog(
            user_id=user_id,
            action="TOGGLE_REPORT_SCHEDULE",
            entity_type="REPORT_SCHEDULE",
            entity_id=str(schedule_id),
            new_value_json={"is_enabled": sched.is_enabled},
        )
        db.add(audit)
        db.commit()
        db.refresh(sched)
        return sched

    @staticmethod
    def delete_schedule(db: Session, schedule_id: int, user_id: int) -> None:
        sched = db.execute(
            select(ReportSchedule).where(ReportSchedule.id == schedule_id)
        ).scalar_one_or_none()
        if not sched:
            raise NotFoundException(f"Schedule {schedule_id} not found")

        db.delete(sched)
        audit = AuditLog(
            user_id=user_id,
            action="DELETE_REPORT_SCHEDULE",
            entity_type="REPORT_SCHEDULE",
            entity_id=str(schedule_id),
            new_value_json={"report_type": sched.report_type},
        )
        db.add(audit)
        db.commit()
