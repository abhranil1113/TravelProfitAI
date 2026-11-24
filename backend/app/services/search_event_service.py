from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.schema import (
    CustomerSearchEvent,
    Destination,
    InventoryCategory,
)
from backend.app.schemas.search_event import (
    BulkSearchEventIngestResponse,
    CustomerSearchEventCreateRequest,
    FunnelAnalyticsResponse,
    FunnelStepMetric,
    VelocityAggregateMetric,
    VelocityAnalyticsResponse,
)


class SearchEventService:
    @staticmethod
    def list_search_events(
        db: Session,
        dest_id: Optional[str] = None,
        category: Optional[InventoryCategory] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CustomerSearchEvent], int]:
        query = db.query(CustomerSearchEvent)
        if dest_id:
            query = query.filter(CustomerSearchEvent.dest_id == dest_id.upper())
        if category:
            query = query.filter(CustomerSearchEvent.inventory_category == category)
        if start_date:
            query = query.filter(CustomerSearchEvent.search_date >= start_date)
        if end_date:
            query = query.filter(CustomerSearchEvent.search_date <= end_date)

        total = query.count()
        events = query.order_by(CustomerSearchEvent.search_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return events, total

    @staticmethod
    def get_funnel_analytics(
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        dest_id: Optional[str] = None,
        category: Optional[InventoryCategory] = None,
    ) -> FunnelAnalyticsResponse:
        query = db.query(CustomerSearchEvent)
        if dest_id:
            query = query.filter(CustomerSearchEvent.dest_id == dest_id.upper())
        if category:
            query = query.filter(CustomerSearchEvent.inventory_category == category)
        if start_date:
            query = query.filter(CustomerSearchEvent.search_date >= start_date)
        if end_date:
            query = query.filter(CustomerSearchEvent.search_date <= end_date)

        total_searches = query.count()
        total_clicks = query.filter(CustomerSearchEvent.clicked == True).count()
        total_bookings = query.filter(CustomerSearchEvent.booking_completed == True).count()

        ctr = (total_clicks / total_searches * 100.0) if total_searches > 0 else 0.0
        click_to_book = (total_bookings / total_clicks * 100.0) if total_clicks > 0 else 0.0
        overall_conversion = (total_bookings / total_searches * 100.0) if total_searches > 0 else 0.0

        steps = [
            FunnelStepMetric(
                step="1. Search Impressions",
                count=total_searches,
                conversion_from_previous_pct=100.0,
                conversion_from_search_pct=100.0,
            ),
            FunnelStepMetric(
                step="2. Offer Click-throughs",
                count=total_clicks,
                conversion_from_previous_pct=round(ctr, 2),
                conversion_from_search_pct=round(ctr, 2),
            ),
            FunnelStepMetric(
                step="3. Bookings Completed",
                count=total_bookings,
                conversion_from_previous_pct=round(click_to_book, 2),
                conversion_from_search_pct=round(overall_conversion, 2),
            ),
        ]

        return FunnelAnalyticsResponse(
            total_searches=total_searches,
            total_clicks=total_clicks,
            total_bookings=total_bookings,
            search_to_click_ctr_pct=round(ctr, 2),
            click_to_book_conversion_pct=round(click_to_book, 2),
            overall_funnel_conversion_pct=round(overall_conversion, 2),
            funnel_steps=steps,
        )

    @staticmethod
    def get_velocity_analytics(db: Session) -> VelocityAnalyticsResponse:
        dests = db.query(Destination).filter(Destination.is_active == True).all()
        aggregates = []

        for d in dests:
            r7 = d.rolling_7d_searches
            r30 = d.rolling_30d_searches
            avg_7d = r7 / 7.0 if r7 > 0 else 0.0
            avg_30d = r30 / 30.0 if r30 > 0 else 0.0
            growth = ((avg_7d - avg_30d) / avg_30d * 100.0) if avg_30d > 0 else 0.0

            aggregates.append(VelocityAggregateMetric(
                dest_id=d.dest_id,
                destination_name=d.name,
                searches_7d=r7,
                searches_30d=r30,
                velocity_growth_pct=round(growth, 2),
                category="DESTINATION_AGGREGATE",
            ))

        return VelocityAnalyticsResponse(
            aggregates=aggregates,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def bulk_ingest_search_events(
        db: Session, events_data: list[CustomerSearchEventCreateRequest]
    ) -> BulkSearchEventIngestResponse:
        records = [
            CustomerSearchEvent(
                search_id=e.search_id,
                search_date=e.search_date,
                travel_date=e.travel_date,
                dest_id=e.dest_id.upper(),
                origin_dest_id=e.origin_dest_id.upper() if e.origin_dest_id else None,
                inventory_category=e.inventory_category,
                travellers_count=e.travellers_count,
                rooms_count=e.rooms_count,
                search_price=e.search_price,
                currency_code=e.currency_code,
                clicked=e.clicked,
                booking_completed=e.booking_completed,
                user_session_id=e.user_session_id,
                conversion_value_inr=e.conversion_value_inr,
            )
            for e in events_data
        ]
        db.bulk_save_objects(records)
        db.commit()
        return BulkSearchEventIngestResponse(
            received_count=len(events_data),
            ingested_count=len(records),
            inserted_count=len(records),
            rejected_count=0,
            status="SUCCESS",
        )
