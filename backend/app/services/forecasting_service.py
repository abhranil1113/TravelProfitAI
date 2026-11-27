from __future__ import annotations

import logging
import uuid
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.app.core.exceptions import EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    Destination,
    DestinationDailyMetrics,
    DestinationDemandForecast,
    DestinationInventoryForecast,
    InventoryCategory,
    InventorySnapshot,
    InventoryItem,
    CustomerSearchEvent,
    MLModel,
    MLModelType,
    OfferPrediction,
    OfferStatus,
    SupplierOffer,
    UnitType,
)
from backend.app.schemas.forecast import (
    ChartDataPoint,
    DemandChartResponse,
    ForecastMaterializeRequest,
    ForecastMaterializeResponse,
    PredictionGenerateRequest,
    PredictionGenerateResponse,
)
from optimization.config import OptimizationConfig
from optimization.predictions.flight_price import FlightPriceService
from optimization.predictions.hotel_cancellation import HotelCancellationService
from optimization.predictions.model_registry import ModelRegistry
from optimization.predictions.demand_forecasting import DemandForecastingService
from optimization.predictions.inventory_forecasting import InventoryForecastingService

logger = logging.getLogger(__name__)


def _champion_metadata(db: Session, model_type: MLModelType) -> Optional[Dict[str, Any]]:
    model = db.query(MLModel).filter(
        MLModel.model_type == model_type,
        MLModel.is_champion == True,
    ).first()
    if not model:
        return None
    return {
        "name": f"{model.algorithm}:{model.model_type.value}",
        "version": model.version,
        "algorithm": model.algorithm,
        "artifact_dir": model.artifact_dir,
        "feature_schema_version": model.feature_schema_version,
        "framework_version": model.framework_version,
    }


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
        as_of = payload.as_of_date or date.today()
        batch_id = f"pred_batch_{as_of.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        # Query real supplier offers from the database
        offer_query = db.query(SupplierOffer).filter(SupplierOffer.status == OfferStatus.ACTIVE)
        if payload.offer_ids:
            offer_query = offer_query.filter(SupplierOffer.offer_id.in_([str(oid) for oid in payload.offer_ids]))
        if payload.destination_ids:
            offer_query = offer_query.filter(SupplierOffer.dest_id.in_([str(did).upper() for did in payload.destination_ids]))

        active_offers = offer_query.all()

        registry = ModelRegistry(db=db)
        opt_config = OptimizationConfig(run_id=batch_id, optimization_timestamp=as_of.isoformat())
        flight_service: Optional[FlightPriceService] = None
        hotel_service: Optional[HotelCancellationService] = None

        # Existing predictions cache for upsert handling
        existing_preds = {
            p.offer_id: p
            for p in db.query(OfferPrediction).filter(OfferPrediction.as_of_date == as_of).all()
        }

        persisted_count = 0
        now = datetime.now(timezone.utc)
        unavailable_count = 0

        for offer in active_offers:
            oid = str(offer.offer_id)
            if not payload.force_recompute and oid in existing_preds:
                persisted_count += 1
                continue

            inv_cat = offer.inventory_category
            if inv_cat == InventoryCategory.HOTEL:
                hotel_metadata = _champion_metadata(db, MLModelType.HOTEL_CANCELLATION)
                if hotel_metadata is None:
                    p_cancel = None
                else:
                    if hotel_service is None:
                        hotel_service = HotelCancellationService(registry, opt_config)
                    offer_dict = {
                        "offer_id": oid,
                        "destination_id": str(offer.dest_id),
                        "purchase_cost": float(offer.unit_cost_inr),
                        "selling_price": float(offer.list_price_inr),
                        "travel_date": str(offer.travel_date),
                    }
                    p_cancel = hotel_service.predict_cohort_cancellation_probability(offer_dict)
                mkt_price = offer.list_price_inr
                theta = opt_config.financial.hotel_base_sell_through
                demand_units = None
                model_metadata = hotel_metadata
            else:  # FLIGHT
                flight_metadata = _champion_metadata(db, MLModelType.FLIGHT_PRICE)
                if flight_metadata is None:
                    pred_ceiling = None
                else:
                    if flight_service is None:
                        flight_service = FlightPriceService(registry, opt_config)
                    offer_dict = {
                        "offer_id": oid,
                        "origin_id": str(offer.origin_dest_id),
                        "destination_id": str(offer.dest_id),
                        "purchase_cost": float(offer.unit_cost_inr),
                        "selling_price": float(offer.list_price_inr),
                        "travel_date": str(offer.travel_date),
                    }
                    if offer.origin_dest_id is None:
                        pred_ceiling = None
                    else:
                        pred_ceiling = flight_service.predict_market_ceiling_price(offer_dict)
                mkt_price = Decimal(str(round(pred_ceiling, 2))) if pred_ceiling is not None else offer.list_price_inr
                p_cancel = None
                theta = opt_config.financial.flight_base_sell_through
                demand_units = None
                model_metadata = flight_metadata

            if model_metadata is None:
                unavailable_count += 1
                continue

            model_version = f"{model_metadata['name']}:{model_metadata['version']}"

            if oid in existing_preds:
                rec = existing_preds[oid]
                rec.predicted_cancellation_prob = p_cancel
                rec.predicted_market_price_inr = mkt_price
                rec.predicted_sell_through_theta = theta
                rec.predicted_demand_units = demand_units
                rec.prediction_timestamp = now
                rec.model_version = model_version
                rec.expected_unit_contribution_inr = Decimal("0.00")
                rec.break_even_sell_through = theta
                rec.model_versions_json = {model_metadata["name"]: model_metadata["version"]}
            else:
                new_pred = OfferPrediction(
                    offer_id=oid,
                    as_of_date=as_of,
                    prediction_timestamp=now,
                    model_version=model_version,
                    predicted_cancellation_prob=p_cancel,
                    predicted_market_price_inr=mkt_price,
                    predicted_sell_through_theta=theta,
                    predicted_demand_units=demand_units,
                    expected_unit_contribution_inr=Decimal("0.00"),
                    break_even_sell_through=theta,
                    model_versions_json={model_metadata["name"]: model_metadata["version"]},
                )
                db.add(new_pred)
                existing_preds[oid] = new_pred

            persisted_count += 1

        db.add(AuditLog(
            user_id=user_id,
            action="OFFER_PREDICTIONS_BATCH_PROCESSED",
            entity_type="offer_predictions",
            entity_id=batch_id,
            new_value_json={
                "as_of_date": str(as_of),
                "persisted_predictions_count": persisted_count,
                "force_recompute": payload.force_recompute,
            },
        ))
        db.commit()

        status = "COMPLETED"
        if unavailable_count > 0:
            status = "PARTIAL" if persisted_count > 0 else "INSUFFICIENT_DATA"
        return PredictionGenerateResponse(
            batch_task_id=batch_id,
            as_of_date=as_of,
            target_offers_count=persisted_count,
            status=status,
            message=(
                f"Evaluated and persisted {persisted_count} offer predictions for as_of_date={as_of}; "
                f"{unavailable_count} offers lacked a usable champion model or required features."
                if unavailable_count
                else f"Evaluated and persisted {persisted_count} offer predictions for as_of_date={as_of}."
            ),
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
        as_of = payload.as_of_date or date.today()

        # Resolve destination records
        dest_query = db.query(Destination)
        if payload.dest_ids:
            dest_query = dest_query.filter(Destination.dest_id.in_([d.upper() for d in payload.dest_ids]))
        destinations = dest_query.all()
        dest_count = len(destinations)

        if dest_count == 0:
            return ForecastMaterializeResponse(
                task_id=task_id,
                destinations_queued=0,
                horizon_days=payload.horizon_days,
                status="COMPLETED",
            )

        horizon_days = max(1, min(90, payload.horizon_days))
        categories = [
            (InventoryCategory.HOTEL, UnitType.ROOM_NIGHT),
            (InventoryCategory.FLIGHT, UnitType.SEAT),
        ]

        total_demand_rows = 0
        total_inv_rows = 0

        search_rows = db.query(CustomerSearchEvent).filter(
            CustomerSearchEvent.search_date <= as_of,
        ).all()
        search_df = pd.DataFrame([
            {
                "search_id": s.search_id,
                "search_date": s.search_date,
                "destination_id": s.dest_id,
                "inventory_type": s.inventory_category.value,
                "travellers_count": s.travellers_count,
                "search_price": float(s.search_price) if s.search_price is not None else 0.0,
            }
            for s in search_rows
        ])

        for dest in destinations:
            did = dest.dest_id

            # Retrieve recent metrics for historical baseline
            recent_metrics = db.query(DestinationDailyMetrics).filter(
                DestinationDailyMetrics.dest_id == did,
                DestinationDailyMetrics.metric_date <= as_of,
            ).order_by(DestinationDailyMetrics.metric_date.desc()).limit(14).all()

            if not recent_metrics:
                logger.warning("No recent daily metrics found for destination %s prior to %s. Skipping baseline materialization.", did, as_of)
            demand_registry = ModelRegistry(db=db)
            demand_model = _champion_metadata(db, MLModelType.DEMAND_FORECASTING)

            # Step in weekly horizon increments
            horizon_steps = list(range(1, horizon_days + 1, 7))
            if horizon_days not in horizon_steps:
                horizon_steps.append(horizon_days)

            for step in horizon_steps:
                fc_date = as_of + timedelta(days=step)

                for cat, u_type in categories:
                    multiplier = 1.0 + 0.02 * (step % 5)
                    pred_units = None
                    pred_search = None
                    if demand_model is not None:
                        try:
                            demand_service = DemandForecastingService(
                                demand_registry,
                                OptimizationConfig(run_id=task_id, optimization_timestamp=as_of.isoformat()),
                                search_df,
                            )
                            predicted = demand_service.predict_future_search_volume(did, cat.value)
                            if predicted is not None:
                                pred_units = int(round(max(0.0, predicted)))
                                pred_search = int(round(max(0.0, predicted)))
                        except Exception as exc:
                            logger.warning("Demand model unavailable for %s/%s: %s", did, cat.value, exc)

                    if pred_units is None:
                        continue
                    conf_lower = max(0.0, float(pred_units * 0.8))
                    conf_upper = float(pred_units * 1.25)

                    # Upsert demand forecast
                    existing_dfc = db.query(DestinationDemandForecast).filter(
                        DestinationDemandForecast.dest_id == did,
                        DestinationDemandForecast.inventory_category == cat,
                        DestinationDemandForecast.forecast_date == fc_date,
                        DestinationDemandForecast.as_of_date == as_of,
                    ).first()

                    if existing_dfc:
                        existing_dfc.predicted_demand_units = pred_units
                        existing_dfc.predicted_search_volume = pred_search
                        existing_dfc.confidence_lower = conf_lower
                        existing_dfc.confidence_upper = conf_upper
                        existing_dfc.model_version = f"{demand_model['name']}:{demand_model['version']}"
                    else:
                        db.add(DestinationDemandForecast(
                            dest_id=did,
                            inventory_category=cat,
                            unit_type=u_type,
                            forecast_date=fc_date,
                            as_of_date=as_of,
                            predicted_demand_units=pred_units,
                            predicted_search_volume=pred_search,
                            confidence_lower=conf_lower,
                            confidence_upper=conf_upper,
                            demand_multiplier=round(multiplier, 2),
                            model_version=f"{demand_model['name']}:{demand_model['version']}",
                        ))
                    total_demand_rows += 1

                    # Inventory availability comes only from the latest authoritative snapshot.
                    inventory_items = db.query(InventoryItem).filter(
                        InventoryItem.dest_id == did,
                        InventoryItem.inventory_category == cat,
                        InventoryItem.is_active == True,
                    ).all()
                    pred_avail = 0
                    depletion_velocity = 0.0
                    inventory_id = None
                    snapshot_found = False
                    inventory_model = _champion_metadata(db, MLModelType.INVENTORY_FORECASTING)
                    for inv in inventory_items:
                        snapshot = db.query(InventorySnapshot).filter(
                            InventorySnapshot.inventory_id == inv.inventory_id,
                            InventorySnapshot.snapshot_at <= datetime.combine(as_of, datetime.min.time()).replace(tzinfo=timezone.utc),
                        ).order_by(InventorySnapshot.snapshot_at.desc()).first()
                        if snapshot is None:
                            continue
                        snapshot_found = True
                        inventory_id = inv.inventory_id
                        tot = snapshot.total_units
                        avail = snapshot.available_units
                        booked = snapshot.booked_units
                        pred_avail += avail
                        depletion_velocity += max(0.0, float(booked) / 7.0)
                        if inventory_model is not None:
                            try:
                                inv_service = InventoryForecastingService(
                                    demand_registry,
                                    OptimizationConfig(run_id=task_id, optimization_timestamp=as_of.isoformat()),
                                )
                                predicted_avail = inv_service.predict_future_available_quantity({
                                    "inventory_id": inv.inventory_id,
                                    "inventory_type": cat.value,
                                    "supplier_id": snapshot.supplier_id or "UNKNOWN",
                                    "destination_id": did,
                                    "unit_type": u_type.value,
                                    "travel_date": snapshot.travel_date.isoformat(),
                                    "snapshot_date": as_of.isoformat(),
                                    "total_capacity": tot,
                                    "available_quantity": avail,
                                    "booked_quantity": booked,
                                })
                                if predicted_avail is not None:
                                    pred_avail = max(0, int(round(predicted_avail)))
                            except Exception as exc:
                                logger.warning("Inventory model unavailable for %s: %s", inv.inventory_id, exc)
                    if not snapshot_found:
                        continue

                    existing_ifc = db.query(DestinationInventoryForecast).filter(
                        DestinationInventoryForecast.dest_id == did,
                        DestinationInventoryForecast.inventory_category == cat,
                        DestinationInventoryForecast.forecast_date == fc_date,
                        DestinationInventoryForecast.as_of_date == as_of,
                    ).first()

                    if existing_ifc:
                        existing_ifc.predicted_available_units = pred_avail
                        existing_ifc.predicted_depletion_velocity = depletion_velocity
                        existing_ifc.confidence_lower = conf_lower
                        existing_ifc.confidence_upper = conf_upper
                        existing_ifc.inventory_id = inventory_id
                        existing_ifc.model_version = (
                            f"{inventory_model['name']}:{inventory_model['version']}"
                            if inventory_model is not None
                            else "INSUFFICIENT_DATA"
                        )
                    else:
                        db.add(DestinationInventoryForecast(
                            dest_id=did,
                            inventory_category=cat,
                            unit_type=u_type,
                            forecast_date=fc_date,
                            as_of_date=as_of,
                            predicted_available_units=pred_avail,
                            predicted_depletion_velocity=depletion_velocity,
                            confidence_lower=conf_lower,
                            confidence_upper=conf_upper,
                            model_version=(
                                f"{inventory_model['name']}:{inventory_model['version']}"
                                if inventory_model is not None
                                else "INSUFFICIENT_DATA"
                            ),
                        ))
                    total_inv_rows += 1

        db.add(AuditLog(
            user_id=user_id,
            action="FORECASTS_MATERIALIZATION_COMPLETED",
            entity_type="destination_demand_forecasts",
            entity_id=task_id,
            new_value_json={
                "horizon_days": horizon_days,
                "destinations_count": dest_count,
                "demand_forecast_rows_written": total_demand_rows,
                "inventory_forecast_rows_written": total_inv_rows,
            },
        ))
        db.commit()

        return ForecastMaterializeResponse(
            task_id=task_id,
            destinations_queued=dest_count,
            horizon_days=horizon_days,
            status=(
                "COMPLETED" if (total_demand_rows + total_inv_rows) > 0
                else "INSUFFICIENT_DATA"
            ),
        )
