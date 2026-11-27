from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
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
from optimization.predictions.inventory_forecasting import InventoryForecastingService

logger = logging.getLogger(__name__)


def _model_provenance(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    if not metadata:
        return None
    name = metadata.get("_registry_model_name")
    version = metadata.get("_registry_model_version")
    if not name or not version:
        return None
    return f"{name}:{version}"


def _as_utc(value: datetime) -> datetime:
    """Treat database-naive timestamps as UTC and normalize aware values to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _snapshot_is_valid(snapshot: InventorySnapshot) -> bool:
    return (
        snapshot.total_units >= 0
        and snapshot.available_units >= 0
        and snapshot.booked_units >= 0
        and snapshot.available_units + snapshot.booked_units == snapshot.total_units
    )


def _snapshot_velocity(
    current: InventorySnapshot,
    previous: Optional[InventorySnapshot],
) -> tuple[float, float, float, float]:
    if previous is None:
        return 0.0, 0.0, 0.0, 0.0
    if not _snapshot_is_valid(previous) or previous.total_units != current.total_units:
        raise ValueError("Snapshots have inconsistent capacity or quantities.")

    elapsed_days = (
        (_as_utc(current.snapshot_at) - _as_utc(previous.snapshot_at)).total_seconds()
        / 86400.0
    )
    elapsed_days = round(max(0.0, elapsed_days), 1)
    change_booked = round(float(current.booked_units - previous.booked_units), 1)
    change_available = round(float(current.available_units - previous.available_units), 1)
    if elapsed_days <= 0:
        return 0.0, change_booked, change_available, 0.0

    depletion_velocity = (
        round(-change_available / elapsed_days, 2) if change_available < 0 else 0.0
    )
    return elapsed_days, change_booked, change_available, depletion_velocity


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
                try:
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
                    model_metadata = hotel_service.metadata
                except Exception as exc:
                    logger.warning("Hotel cancellation inference failed for %s: %s", oid, exc)
                    p_cancel = None
                    model_metadata = None
                if p_cancel is None:
                    unavailable_count += 1
                    continue
                mkt_price = offer.list_price_inr
                theta = opt_config.financial.hotel_base_sell_through
                demand_units = None
            else:  # FLIGHT
                if offer.origin_dest_id is None:
                    pred_ceiling = None
                    model_metadata = None
                else:
                    try:
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
                        pred_ceiling = flight_service.predict_market_ceiling_price(offer_dict)
                        model_metadata = flight_service.metadata
                    except Exception as exc:
                        logger.warning("Flight price inference failed for %s: %s", oid, exc)
                        pred_ceiling = None
                        model_metadata = None
                if pred_ceiling is None:
                    unavailable_count += 1
                    continue
                mkt_price = Decimal(str(round(pred_ceiling, 2)))
                p_cancel = None
                theta = opt_config.financial.flight_base_sell_through
                demand_units = None

            model_version = _model_provenance(model_metadata)
            if model_version is None:
                unavailable_count += 1
                continue

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
                rec.model_versions_json = {
                    str(model_metadata["_registry_model_name"]):
                    str(model_metadata["_registry_model_version"])
                }
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
                    model_versions_json={
                        str(model_metadata["_registry_model_name"]):
                        str(model_metadata["_registry_model_version"])
                    },
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

        model_version = "INSUFFICIENT_DATA"
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
        from modeling.registry.task_registry import TaskRegistry

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
                status="INSUFFICIENT_DATA",
            )

        horizon_days = max(1, min(90, payload.horizon_days))
        categories = [
            (InventoryCategory.HOTEL, UnitType.ROOM_NIGHT),
            (InventoryCategory.FLIGHT, UnitType.SEAT),
        ]
        forecast_dates = [
            as_of + timedelta(days=step) for step in range(1, horizon_days + 1)
        ]
        as_of_start = datetime.combine(as_of, time.min, tzinfo=timezone.utc)
        as_of_end = as_of_start + timedelta(days=1)

        total_demand_rows = 0
        total_inv_rows = 0
        successful_demand_predictions = 0
        failed_demand_predictions = (
            dest_count * len(forecast_dates) * len(categories)
        )
        successful_inventory_predictions = 0
        failed_inventory_predictions = 0
        inventory_service: Optional[InventoryForecastingService] = None
        inventory_model_unavailable = False
        inventory_target_horizon = TaskRegistry().get(
            "inventory_forecasting"
        ).forecast_horizon
        demand_unavailable_reason = (
            "No validated booking-demand model is configured; search-volume "
            "predictions are not booking-demand predictions."
        )
        logger.warning("Booking-demand forecasts unavailable: %s", demand_unavailable_reason)

        for dest in destinations:
            did = dest.dest_id
            for cat, u_type in categories:
                inventory_items = db.query(InventoryItem).filter(
                    InventoryItem.dest_id == did,
                    InventoryItem.inventory_category == cat,
                    InventoryItem.unit_type == u_type,
                    InventoryItem.is_active.is_(True),
                ).all()
                if not inventory_items:
                    continue

                grouped_predictions: Dict[
                    tuple[Optional[str], date],
                    Dict[str, Any],
                ] = {}
                for inv in inventory_items:
                    snapshots = db.query(InventorySnapshot).filter(
                        InventorySnapshot.inventory_id == inv.inventory_id,
                        InventorySnapshot.travel_date > as_of,
                        InventorySnapshot.snapshot_at >= as_of_start,
                        InventorySnapshot.snapshot_at < as_of_end,
                    ).order_by(InventorySnapshot.snapshot_at.desc()).all()

                    latest_by_travel_date: Dict[date, InventorySnapshot] = {}
                    for snapshot in snapshots:
                        latest_by_travel_date.setdefault(snapshot.travel_date, snapshot)
                    if not latest_by_travel_date:
                        failed_inventory_predictions += horizon_days
                        continue

                    for snapshot in latest_by_travel_date.values():
                        previous = db.query(InventorySnapshot).filter(
                            InventorySnapshot.inventory_id == inv.inventory_id,
                            InventorySnapshot.travel_date == snapshot.travel_date,
                            InventorySnapshot.snapshot_at < snapshot.snapshot_at,
                        ).order_by(InventorySnapshot.snapshot_at.desc()).first()
                        try:
                            if not _snapshot_is_valid(snapshot):
                                raise ValueError("Current snapshot violates capacity conservation.")
                            if previous is None:
                                raise ValueError("A prior snapshot is required to establish the next-snapshot horizon.")
                            if not _snapshot_is_valid(previous):
                                raise ValueError("Previous snapshot violates capacity conservation.")

                            current_day = _as_utc(snapshot.snapshot_at).date()
                            previous_day = _as_utc(previous.snapshot_at).date()
                            if (current_day - previous_day).days != 1:
                                raise ValueError("Observed snapshots do not establish a one-day forecast cadence.")
                            if inventory_target_horizon != 1:
                                raise ValueError(
                                    "The inventory model's configured snapshot horizon is not supported by this materializer."
                                )

                            if inventory_service is None and not inventory_model_unavailable:
                                inventory_service = InventoryForecastingService(
                                    ModelRegistry(db=db),
                                    OptimizationConfig(
                                        run_id=task_id,
                                        optimization_timestamp=as_of.isoformat(),
                                    ),
                                )
                                if inventory_service.metadata.get("target_column") != "future_available_quantity":
                                    inventory_model_unavailable = True
                                    raise ValueError(
                                        "Inventory artifact does not declare the expected future-availability target."
                                    )
                                if _model_provenance(inventory_service.metadata) is None:
                                    inventory_model_unavailable = True
                                    raise ValueError(
                                        "Inventory artifact has no registered model provenance."
                                    )
                            if inventory_model_unavailable:
                                raise ValueError("Inventory model or artifact is unavailable.")
                            if inventory_service is None:
                                raise ValueError("Inventory model did not initialize.")

                            elapsed_days, change_booked, change_available, depletion_velocity = (
                                _snapshot_velocity(snapshot, previous)
                            )
                            days_to_travel = (
                                snapshot.travel_date - current_day
                            ).days
                            origin_id = inv.origin_dest_id
                            if cat == InventoryCategory.FLIGHT and origin_id is None:
                                raise ValueError("Flight inventory is missing its origin destination.")
                            model_origin_id = (
                                origin_id if cat == InventoryCategory.FLIGHT else "None"
                            )

                            predicted_avail = inventory_service.predict_future_available_quantity(
                                {
                                    "inventory_id": inv.inventory_id,
                                    "inventory_type": cat.value,
                                    "supplier_id": snapshot.supplier_id or "None",
                                    "origin_id": model_origin_id,
                                    "destination_id": did,
                                    "unit_type": u_type.value,
                                    "travel_date": snapshot.travel_date.isoformat(),
                                    "snapshot_date": current_day.isoformat(),
                                    "days_to_travel": float(days_to_travel),
                                    "total_capacity": snapshot.total_units,
                                    "available_quantity": snapshot.available_units,
                                    "booked_quantity": snapshot.booked_units,
                                    "days_since_prev_snapshot": elapsed_days,
                                    "change_in_booked_quantity": change_booked,
                                    "change_in_available_quantity": change_available,
                                    "booking_velocity_units_per_day": (
                                        round(change_booked / elapsed_days, 2)
                                        if elapsed_days > 0
                                        else 0.0
                                    ),
                                    "inventory_depletion_velocity": depletion_velocity,
                                },
                                raise_on_error=True,
                            )
                            model_version = _model_provenance(inventory_service.metadata)
                            if predicted_avail is None or model_version is None:
                                raise ValueError("Inventory inference or model provenance is unavailable.")
                        except Exception as exc:
                            logger.warning(
                                "Inventory inference unavailable for %s/%s: %s",
                                inv.inventory_id,
                                snapshot.travel_date,
                                exc,
                            )
                            if inventory_service is None:
                                inventory_model_unavailable = True
                            failed_inventory_predictions += horizon_days
                            continue

                        aggregate_key = (inv.origin_dest_id, as_of + timedelta(days=1))
                        aggregate = grouped_predictions.setdefault(
                            aggregate_key,
                            {"available_units": 0, "depletion_velocity": 0.0, "model_version": model_version},
                        )
                        if aggregate["model_version"] != model_version:
                            logger.error(
                                "Refusing to aggregate forecasts from different model versions for %s/%s.",
                                did,
                                cat.value,
                            )
                            failed_inventory_predictions += 1
                            continue
                        aggregate["available_units"] += max(0, int(round(predicted_avail)))
                        aggregate["depletion_velocity"] += depletion_velocity
                        successful_inventory_predictions += 1
                        if horizon_days > 1:
                            failed_inventory_predictions += horizon_days - 1

                for (origin_id, fc_date), aggregate in grouped_predictions.items():
                    existing_ifc = db.query(DestinationInventoryForecast).filter(
                        DestinationInventoryForecast.dest_id == did,
                        DestinationInventoryForecast.inventory_category == cat,
                        DestinationInventoryForecast.unit_type == u_type,
                        DestinationInventoryForecast.origin_dest_id == origin_id,
                        DestinationInventoryForecast.forecast_date == fc_date,
                        DestinationInventoryForecast.as_of_date == as_of,
                    ).first()

                    if existing_ifc:
                        existing_ifc.predicted_available_units = aggregate["available_units"]
                        existing_ifc.predicted_depletion_velocity = aggregate["depletion_velocity"]
                        existing_ifc.confidence_lower = None
                        existing_ifc.confidence_upper = None
                        existing_ifc.inventory_id = None
                        existing_ifc.model_version = aggregate["model_version"]
                    else:
                        db.add(DestinationInventoryForecast(
                            dest_id=did,
                            inventory_category=cat,
                            unit_type=u_type,
                            origin_dest_id=origin_id,
                            forecast_date=fc_date,
                            as_of_date=as_of,
                            predicted_available_units=aggregate["available_units"],
                            predicted_depletion_velocity=aggregate["depletion_velocity"],
                            confidence_lower=None,
                            confidence_upper=None,
                            model_version=aggregate["model_version"],
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
                "successful_demand_predictions": successful_demand_predictions,
                "failed_demand_predictions": failed_demand_predictions,
                "successful_inventory_predictions": successful_inventory_predictions,
                "failed_inventory_predictions": failed_inventory_predictions,
                "inventory_snapshot_horizon": inventory_target_horizon,
                "booking_demand_unavailable_reason": demand_unavailable_reason,
            },
        ))
        db.commit()

        successful_predictions = (
            successful_demand_predictions + successful_inventory_predictions
        )
        failed_predictions = failed_demand_predictions + failed_inventory_predictions
        if successful_predictions == 0:
            materialization_status = "INSUFFICIENT_DATA"
        elif failed_predictions > 0:
            materialization_status = "PARTIAL"
        else:
            materialization_status = "COMPLETED"

        return ForecastMaterializeResponse(
            task_id=task_id,
            destinations_queued=dest_count,
            horizon_days=horizon_days,
            status=materialization_status,
        )
