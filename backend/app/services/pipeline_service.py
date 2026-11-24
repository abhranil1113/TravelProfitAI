from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.exceptions import EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    DataQualityReport,
    DataQualitySeverity,
    IngestionBatch,
    PipelineStatus,
)
from backend.app.schemas.pipeline import (
    PipelineBatchTriggerRequest,
    QualitySummaryItem,
    QualitySummaryResponse,
)


class PipelineService:
    @staticmethod
    def list_batches(
        db: Session,
        dataset_name: Optional[str] = None,
        status: Optional[PipelineStatus] = None,
        batch_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[IngestionBatch], int]:
        query = db.query(IngestionBatch)
        if dataset_name:
            query = query.filter(IngestionBatch.dataset_name.ilike(f"%{dataset_name.strip()}%"))
        if status:
            query = query.filter(IngestionBatch.status == status)
        if batch_date:
            query = query.filter(IngestionBatch.batch_date == batch_date)

        total = query.count()
        batches = query.order_by(IngestionBatch.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return batches, total

    @staticmethod
    def trigger_batch(db: Session, payload: PipelineBatchTriggerRequest, user_id: int) -> IngestionBatch:
        batch_uid = f"BATCH-{uuid.uuid4().hex[:10].upper()}"
        celery_task = f"task-{uuid.uuid4().hex[:8]}"

        batch = IngestionBatch(
            batch_uid=batch_uid,
            dataset_name=payload.dataset_name.strip(),
            source_uri=payload.source_uri.strip(),
            batch_date=payload.batch_date or date.today(),
            status=PipelineStatus.RUNNING,
            celery_task_id=celery_task,
            triggered_by_user_id=user_id,
            processing_started_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        db.add(AuditLog(
            user_id=user_id,
            action="DATA_INGESTION_BATCH_TRIGGERED",
            entity_type="ingestion_batches",
            entity_id=batch_uid,
            details_json={"dataset": batch.dataset_name, "celery_task_id": celery_task},
        ))
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def get_batch(db: Session, batch_uid: str) -> IngestionBatch:
        batch = db.query(IngestionBatch).filter(IngestionBatch.batch_uid == batch_uid).first()
        if not batch:
            raise EntityNotFoundError("IngestionBatch", batch_uid)
        return batch

    @staticmethod
    def get_quality_reports(db: Session, batch_uid: str) -> list[DataQualityReport]:
        batch = PipelineService.get_batch(db, batch_uid)
        return db.query(DataQualityReport).filter(
            DataQualityReport.batch_id == batch.id
        ).order_by(DataQualityReport.id.asc()).all()

    @staticmethod
    def retry_batch(db: Session, batch_uid: str, user_id: int) -> IngestionBatch:
        batch = PipelineService.get_batch(db, batch_uid)
        batch.retry_count += 1
        batch.status = PipelineStatus.RUNNING
        batch.error_message = None
        batch.processing_started_at = datetime.now(timezone.utc)
        batch.processing_completed_at = None
        batch.celery_task_id = f"task-retry-{uuid.uuid4().hex[:8]}"

        db.add(AuditLog(
            user_id=user_id,
            action="DATA_INGESTION_BATCH_RETRIED",
            entity_type="ingestion_batches",
            entity_id=batch_uid,
            details_json={"retry_count": batch.retry_count},
        ))
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def get_quality_summary(db: Session) -> QualitySummaryResponse:
        severities = [s.value for s in DataQualitySeverity]
        summary_items = []
        overall_total = 0
        overall_failed = 0

        for sev in severities:
            total = db.query(DataQualityReport).filter(DataQualityReport.severity == sev).count()
            passed = db.query(DataQualityReport).filter(
                DataQualityReport.severity == sev,
                DataQualityReport.passed == True,
            ).count()
            failed = total - passed
            pass_rate = (passed / total * 100.0) if total > 0 else 100.0

            overall_total += total
            overall_failed += failed

            summary_items.append(QualitySummaryItem(
                severity=sev,
                total_checks=total,
                passed_checks=passed,
                failed_checks=failed,
                pass_rate_pct=round(pass_rate, 2),
            ))

        return QualitySummaryResponse(
            overall_passed=(overall_failed == 0),
            total_checks_evaluated=overall_total,
            by_severity=summary_items,
        )
