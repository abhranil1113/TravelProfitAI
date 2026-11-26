from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import pandas as pd
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

logger = logging.getLogger(__name__)


class PipelineService:
    @staticmethod
    def _execute_batch_cleaning(batch: IngestionBatch, db: Session) -> None:
        """
        Executes real data cleaning on the dataset specified by the ingestion batch,
        updating accurate counts and processed parquet paths.
        """
        try:
            src = batch.source_uri.strip()
            ds_name = batch.dataset_name.strip().lower()
            resolved_path = None

            if os.path.exists(src):
                resolved_path = src
            else:
                candidates = [
                    f"data/raw/{ds_name}.csv",
                    f"data/raw/{ds_name}.parquet",
                    f"data/processed/{ds_name}.parquet",
                    f"data/processed/{ds_name}.csv",
                ]
                for c in candidates:
                    if os.path.exists(c):
                        resolved_path = c
                        break

            if not resolved_path:
                batch.status = PipelineStatus.FAILED
                batch.error_message = f"Source dataset file not found at '{src}' or candidate paths."
                batch.processing_completed_at = datetime.now(timezone.utc)
                return

            # Read dataset
            if resolved_path.endswith(".parquet"):
                raw_df = pd.read_parquet(resolved_path)
            else:
                raw_df = pd.read_csv(resolved_path)

            from data_pipeline.cleaning.clean_market_signals import clean_market_signals
            from data_pipeline.cleaning.clean_inventory import clean_inventory_availability
            from data_pipeline.cleaning.clean_supplier_offers import clean_supplier_offers
            from data_pipeline.cleaning.clean_search_events import clean_search_events
            from data_pipeline.cleaning.clean_flight_prices import clean_flight_prices
            from data_pipeline.cleaning.clean_hotel_bookings import clean_hotel_bookings
            from data_pipeline.cleaning.clean_flights import clean_airlines, clean_airports, clean_flights

            cleaning_map = {
                "market_seasonal_signals": clean_market_signals,
                "market_signals": clean_market_signals,
                "inventory_availability": clean_inventory_availability,
                "supplier_offers": clean_supplier_offers,
                "customer_search_events": clean_search_events,
                "search_events": clean_search_events,
                "flight_prices": clean_flight_prices,
                "hotel_bookings": clean_hotel_bookings,
                "airlines": clean_airlines,
                "airports": clean_airports,
                "flights": clean_flights,
            }

            cleaner = cleaning_map.get(ds_name)
            if cleaner:
                clean_df, meta = cleaner(raw_df)
                dups = meta.get("duplicates_dropped", 0) if isinstance(meta, dict) else 0
            else:
                clean_df = raw_df.drop_duplicates()
                dups = len(raw_df) - len(clean_df)
                meta = {}

            out_dir = Path("data/processed")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_parquet = out_dir / f"{ds_name}.parquet"
            clean_df.to_parquet(out_parquet, index=False)

            batch.rows_ingested = len(clean_df)
            batch.rows_rejected = max(0, len(raw_df) - len(clean_df))
            batch.rows_duplicates_removed = dups
            batch.processed_parquet_path = str(out_parquet)
            batch.status = PipelineStatus.COMPLETED
            batch.error_message = None
            batch.processing_completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error("Batch processing failed for %s: %s", batch.batch_uid, e, exc_info=True)
            batch.status = PipelineStatus.FAILED
            batch.error_message = f"Ingestion batch processing failed: {str(e)}"
            batch.processing_completed_at = datetime.now(timezone.utc)

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
        pipeline_task = f"in_process_{batch_uid.lower()}"

        batch = IngestionBatch(
            batch_uid=batch_uid,
            dataset_name=payload.dataset_name.strip(),
            source_uri=payload.source_uri.strip(),
            batch_date=payload.batch_date or date.today(),
            status=PipelineStatus.RUNNING,
            celery_task_id=pipeline_task,
            triggered_by_user_id=user_id,
            processing_started_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        db.flush()

        # Execute data cleaning execution path
        PipelineService._execute_batch_cleaning(batch, db)

        db.add(AuditLog(
            user_id=user_id,
            action="DATA_INGESTION_BATCH_TRIGGERED",
            entity_type="ingestion_batches",
            entity_id=batch_uid,
            new_value_json={
                "dataset": batch.dataset_name,
                "status": batch.status.value,
                "rows_ingested": batch.rows_ingested,
                "rows_rejected": batch.rows_rejected,
                "processed_parquet_path": batch.processed_parquet_path,
            },
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

        PipelineService._execute_batch_cleaning(batch, db)

        db.add(AuditLog(
            user_id=user_id,
            action="DATA_INGESTION_BATCH_RETRIED",
            entity_type="ingestion_batches",
            entity_id=batch_uid,
            new_value_json={
                "retry_count": batch.retry_count,
                "status": batch.status.value,
                "rows_ingested": batch.rows_ingested,
            },
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
