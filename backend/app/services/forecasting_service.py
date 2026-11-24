from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.exceptions import EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    Destination,
    DestinationDailyMetrics,
    DestinationDemandForecast,
    DestinationInventoryForecast,
    InventoryCategory,
    OfferPrediction,
)
from backend.app.schemas.forecast import (
    ChartDataPoint,
    DemandChartResponse,
    ForecastMaterializeRequest,
    ForecastMaterializeResponse,
    PredictionGenerateRequest,
    PredictionGenerateResponse,
)


class ForecastingService:
    @staticmethod
    def list_offer_predictions(
        db: Session,
        as_of_date: Optional[date] = None,
        run_id: Optional[str] = None,
        offer_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[OfferPrediction], int]:
        query = db.query(OfferPrediction)
        if as_of_date:
            query = query.filter(OfferPrediction.as_of_date == as_of_date)
        if run_id:
            query = query.filter(OfferPrediction.run_id == run_id)
        if offer_id:
            query = query.filter(OfferPrediction.offer_id == offer_id)

        total = query.count()
        preds = query.order_by(OfferPrediction.as_of_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return preds, total

    @staticmethod
    def generate_predictions(
        db: Session, payload: PredictionGenerateRequest, user_id: int
    ) -> PredictionGenerateResponse:
        task_id = f"pred-task-{uuid.uuid4().hex[:8]}"
        as_of = payload.as_of_date or date.today()

        db.add(AuditLog(
            user_id=user_id,
            action="OFFER_PREDICTIONS_BATCH_DISPATCHED",
            entity_type="offer_predictions",
            entity_id=task_id,
            new_value_json={"as_of_date": str(as_of), "force_recompute": payload.force_recompute},
        ))
        db.commit()

        return PredictionGenerateResponse(
            batch_task_id=task_id,
            as_of_date=as_of,
            target_offers_count=len(payload.offer_ids) if payload.offer_ids else 100,
            status="QUEUED",
            message="Batch offer predictions queued for asynchronous processing.",
        )

    @staticmethod
    def list_demand_forecasts(
        db: Session,
        dest_id: Optional[str] = None,
        category: Optional[InventoryCategory] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DestinationDemandForecast], int]:
        query = db.query(DestinationDemandForecast)
        if dest_id:
            query = query.filter(DestinationDemandForecast.dest_id == dest_id.upper())
        if category:
            query = query.filter(DestinationDemandForecast.inventory_category == category)
        if start_date:
            query = query.filter(DestinationDemandForecast.forecast_date >= start_date)
        if end_date:
            query = query.filter(DestinationDemandForecast.forecast_date <= end_date)

        total = query.count()
        forecasts = query.order_by(DestinationDemandForecast.forecast_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return forecasts, total

    @staticmethod
    def list_inventory_forecasts(
        db: Session,
        dest_id: Optional[str] = None,
        category: Optional[InventoryCategory] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DestinationInventoryForecast], int]:
        query = db.query(DestinationInventoryForecast)
        if dest_id:
            query = query.filter(DestinationInventoryForecast.dest_id == dest_id.upper())
        if category:
            query = query.filter(DestinationInventoryForecast.inventory_category == category)
        if start_date:
            query = query.filter(DestinationInventoryForecast.forecast_date >= start_date)
        if end_date:
            query = query.filter(DestinationInventoryForecast.forecast_date <= end_date)

        total = query.count()
        forecasts = query.order_by(DestinationInventoryForecast.forecast_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return forecasts, total

    @staticmethod
    def get_demand_chart(db: Session, dest_id: str) -> DemandChartResponse:
        did = dest_id.upper()
        dest = db.query(Destination).filter(Destination.dest_id == did).first()
        if not dest:
            raise EntityNotFoundError("Destination", did)

        today = date.today()
        # Historical 14 days
        hist_start = today - timedelta(days=14)
        hist = db.query(DestinationDailyMetrics).filter(
            DestinationDailyMetrics.dest_id == did,
            DestinationDailyMetrics.metric_date >= hist_start,
            DestinationDailyMetrics.metric_date <= today,
        ).order_by(DestinationDailyMetrics.metric_date.asc()).all()

        # Forecasts next 14 days
        fc_end = today + timedelta(days=14)
        forecasts = db.query(DestinationDemandForecast).filter(
            DestinationDemandForecast.dest_id == did,
            DestinationDemandForecast.forecast_date > today,
            DestinationDemandForecast.forecast_date <= fc_end,
        ).order_by(DestinationDemandForecast.forecast_date.asc()).all()

        chart_points = []
        for h in hist:
            chart_points.append(ChartDataPoint(
                date=h.metric_date,
                actual_searches=h.search_count,
                actual_bookings=h.booking_count,
            ))

        model_version = "persist_baseline_v1"
        for f in forecasts:
            model_version = f.model_version
            chart_points.append(ChartDataPoint(
                date=f.forecast_date,
                predicted_demand=f.predicted_demand_units,
                confidence_lower=f.confidence_lower,
                confidence_upper=f.confidence_upper,
            ))

        return DemandChartResponse(
            dest_id=did,
            time_series=chart_points,
            model_version=model_version,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def materialize_forecasts(
        db: Session, payload: ForecastMaterializeRequest, user_id: int
    ) -> ForecastMaterializeResponse:
        task_id = f"fc-mat-{uuid.uuid4().hex[:8]}"
        dest_count = len(payload.dest_ids) if payload.dest_ids else db.query(Destination).count()

        db.add(AuditLog(
            user_id=user_id,
            action="FORECASTS_MATERIALIZATION_DISPATCHED",
            entity_type="destination_demand_forecasts",
            entity_id=task_id,
            new_value_json={"horizon_days": payload.horizon_days, "destinations_count": dest_count},
        ))
        db.commit()

        return ForecastMaterializeResponse(
            task_id=task_id,
            destinations_queued=dest_count,
            horizon_days=payload.horizon_days,
            status="QUEUED",
        )
