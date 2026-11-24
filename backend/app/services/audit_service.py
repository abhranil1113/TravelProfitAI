from __future__ import annotations

from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    NotFoundException,
)
from backend.app.models.schema import AuditLog


class AuditService:

    @staticmethod
    def list_audit_logs(
        db: Session,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[AuditLog], int]:
        stmt = select(AuditLog)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(AuditLog.occurred_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(db.execute(stmt).scalars().all())
        return items, total

    @staticmethod
    def get_audit_log(db: Session, log_id: int) -> AuditLog:
        log = db.execute(
            select(AuditLog).where(AuditLog.id == log_id)
        ).scalar_one_or_none()
        if not log:
            raise NotFoundException(f"Audit log entry {log_id} not found")
        return log
