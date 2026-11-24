from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.exceptions import ConflictError, EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    CustomerSearchEvent,
    Destination,
    DestinationDailyMetrics,
    InventoryCategory,
)
from backend.app.schemas.destination import (
    DestinationCreateRequest,
    DestinationUpdateRequest,
    SearchVelocityResponse,
)


class DestinationService:
    @staticmethod
    def list_destinations(
        db: Session,
        is_active: Optional[bool] = None,
        country: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Destination], int]:
        query = db.query(Destination)
        if is_active is not None:
            query = query.filter(Destination.is_active == is_active)
        if country:
            query = query.filter(Destination.country.ilike(f"%{country.strip()}%"))
        if search:
            s = f"%{search.strip().lower()}%"
            query = query.filter(or_(
                Destination.dest_id.ilike(s),
                Destination.name.ilike(s),
                Destination.city.ilike(s),
                Destination.airport_code.ilike(s),
            ))

        total = query.count()
        destinations = query.order_by(Destination.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return destinations, total

    @staticmethod
    def create_destination(db: Session, payload: DestinationCreateRequest, user_id: int) -> Destination:
        dest_id = payload.dest_id.upper().strip()
        if db.query(Destination).filter(Destination.dest_id == dest_id).first():
            raise ConflictError(f"Destination with ID '{dest_id}' already exists.")

        dest = Destination(
            dest_id=dest_id,
            name=payload.name.strip(),
            city=payload.city.strip(),
            country=payload.country.strip(),
            airport_code=payload.airport_code.upper().strip() if payload.airport_code else None,
            search_volume_ceiling=payload.search_volume_ceiling,
            is_active=payload.is_active,
        )
        db.add(dest)
        db.add(AuditLog(
            user_id=user_id,
            action="DESTINATION_CREATED",
            entity_type="destinations",
            entity_id=dest_id,
            details_json={"name": dest.name, "country": dest.country},
        ))
        db.commit()
        db.refresh(dest)
        return dest

    @staticmethod
    def get_destination(db: Session, dest_id: str) -> Destination:
        dest = db.query(Destination).filter(Destination.dest_id == dest_id.upper()).first()
        if not dest:
            raise EntityNotFoundError("Destination", dest_id)
        return dest

    @staticmethod
    def update_destination(db: Session, dest_id: str, payload: DestinationUpdateRequest, user_id: int) -> Destination:
        dest = DestinationService.get_destination(db, dest_id)
        updates = {}

        if payload.name is not None:
            dest.name = payload.name.strip()
            updates["name"] = dest.name
        if payload.city is not None:
            dest.city = payload.city.strip()
            updates["city"] = dest.city
        if payload.country is not None:
            dest.country = payload.country.strip()
            updates["country"] = dest.country
        if payload.airport_code is not None:
            dest.airport_code = payload.airport_code.upper().strip()
            updates["airport_code"] = dest.airport_code
        if payload.search_volume_ceiling is not None:
            dest.search_volume_ceiling = payload.search_volume_ceiling
            updates["search_volume_ceiling"] = dest.search_volume_ceiling
        if payload.is_active is not None:
            dest.is_active = payload.is_active
            updates["is_active"] = dest.is_active

        db.add(AuditLog(
            user_id=user_id,
            action="DESTINATION_UPDATED",
            entity_type="destinations",
            entity_id=dest_id,
            details_json=updates,
        ))
        db.commit()
        db.refresh(dest)
        return dest

    @staticmethod
    def delete_destination(db: Session, dest_id: str, user_id: int) -> Destination:
        dest = DestinationService.get_destination(db, dest_id)
        dest.is_active = False
        db.add(AuditLog(
            user_id=user_id,
            action="DESTINATION_DEACTIVATED",
            entity_type="destinations",
            entity_id=dest_id,
        ))
        db.commit()
        db.refresh(dest)
        return dest

    @staticmethod
    def get_daily_metrics(
        db: Session,
        dest_id: str,
        category: Optional[InventoryCategory] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DestinationDailyMetrics]:
        DestinationService.get_destination(db, dest_id)
        query = db.query(DestinationDailyMetrics).filter(DestinationDailyMetrics.dest_id == dest_id.upper())
        if category:
            query = query.filter(DestinationDailyMetrics.inventory_category == category)
        if start_date:
            query = query.filter(DestinationDailyMetrics.metric_date >= start_date)
        if end_date:
            query = query.filter(DestinationDailyMetrics.metric_date <= end_date)

        return query.order_by(DestinationDailyMetrics.metric_date.desc()).all()

    @staticmethod
    def get_search_velocity(db: Session, dest_id: str) -> SearchVelocityResponse:
        dest = DestinationService.get_destination(db, dest_id)
        r7 = dest.rolling_7d_searches
        r30 = dest.rolling_30d_searches
        ceiling = dest.search_volume_ceiling

        avg_daily_7d = r7 / 7.0 if r7 > 0 else 0.0
        avg_daily_30d = r30 / 30.0 if r30 > 0 else 0.0
        growth_pct = ((avg_daily_7d - avg_daily_30d) / avg_daily_30d * 100.0) if avg_daily_30d > 0 else 0.0
        ceiling_util = (r30 / ceiling * 100.0) if ceiling > 0 else 0.0

        return SearchVelocityResponse(
            dest_id=dest.dest_id,
            rolling_7d_searches=r7,
            rolling_30d_searches=r30,
            velocity_growth_pct=round(growth_pct, 2),
            search_volume_ceiling=ceiling,
            ceiling_utilization_pct=round(ceiling_util, 2),
        )
