from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.exceptions import EntityNotFoundError
from backend.app.models.schema import (
    AuditLog,
    ExchangeRate,
    MarketSegmentBaseline,
    MarketSignal,
)
from backend.app.schemas.reference_data import (
    ExchangeRateCreateRequest,
    MarketSegmentBaselineUpsertRequest,
    MarketSignalCreateRequest,
    MarketSignalUpdateRequest,
)


class ReferenceDataService:
    # --- Market Signals (55-58) ---
    @staticmethod
    def list_market_signals(
        db: Session,
        dest_id: Optional[str] = None,
        signal_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MarketSignal], int]:
        query = db.query(MarketSignal)
        if dest_id:
            query = query.filter(MarketSignal.dest_id == dest_id.upper())
        if signal_type:
            query = query.filter(MarketSignal.signal_type.ilike(f"%{signal_type.strip()}%"))
        if start_date:
            query = query.filter(MarketSignal.end_date >= start_date)
        if end_date:
            query = query.filter(MarketSignal.start_date <= end_date)

        total = query.count()
        signals = query.order_by(MarketSignal.start_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return signals, total

    @staticmethod
    def create_market_signal(db: Session, payload: MarketSignalCreateRequest, user_id: int) -> MarketSignal:
        signal = MarketSignal(
            dest_id=payload.dest_id.upper(),
            signal_type=payload.signal_type.strip(),
            start_date=payload.start_date,
            end_date=payload.end_date,
            severity=payload.severity.upper(),
            demand_impact_multiplier=payload.demand_impact_multiplier,
            description=payload.description,
        )
        db.add(signal)
        db.add(AuditLog(
            user_id=user_id,
            action="MARKET_SIGNAL_CREATED",
            entity_type="market_signals",
            entity_id=payload.dest_id.upper(),
            details_json={"signal_type": signal.signal_type, "multiplier": signal.demand_impact_multiplier},
        ))
        db.commit()
        db.refresh(signal)
        return signal

    @staticmethod
    def update_market_signal(db: Session, signal_id: int, payload: MarketSignalUpdateRequest, user_id: int) -> MarketSignal:
        signal = db.query(MarketSignal).filter(MarketSignal.id == signal_id).first()
        if not signal:
            raise EntityNotFoundError("MarketSignal", signal_id)

        if payload.signal_type is not None:
            signal.signal_type = payload.signal_type.strip()
        if payload.start_date is not None:
            signal.start_date = payload.start_date
        if payload.end_date is not None:
            signal.end_date = payload.end_date
        if payload.severity is not None:
            signal.severity = payload.severity.upper()
        if payload.demand_impact_multiplier is not None:
            signal.demand_impact_multiplier = payload.demand_impact_multiplier
        if payload.description is not None:
            signal.description = payload.description

        db.add(AuditLog(
            user_id=user_id,
            action="MARKET_SIGNAL_UPDATED",
            entity_type="market_signals",
            entity_id=str(signal_id),
        ))
        db.commit()
        db.refresh(signal)
        return signal

    @staticmethod
    def delete_market_signal(db: Session, signal_id: int, user_id: int) -> None:
        signal = db.query(MarketSignal).filter(MarketSignal.id == signal_id).first()
        if not signal:
            raise EntityNotFoundError("MarketSignal", signal_id)
        db.add(AuditLog(
            user_id=user_id,
            action="MARKET_SIGNAL_DELETED",
            entity_type="market_signals",
            entity_id=str(signal_id),
        ))
        db.delete(signal)
        db.commit()

    # --- Exchange Rates (59-61) ---
    @staticmethod
    def list_exchange_rates(
        db: Session,
        currency_pair: Optional[str] = None,
        as_of_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExchangeRate], int]:
        query = db.query(ExchangeRate)
        if currency_pair:
            query = query.filter(ExchangeRate.currency_pair == currency_pair.upper())
        if as_of_date:
            query = query.filter(ExchangeRate.as_of_date == as_of_date)

        total = query.count()
        rates = query.order_by(ExchangeRate.as_of_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return rates, total

    @staticmethod
    def create_exchange_rate(db: Session, payload: ExchangeRateCreateRequest) -> ExchangeRate:
        rate = ExchangeRate(
            currency_pair=payload.currency_pair.upper(),
            as_of_date=payload.as_of_date,
            rate=payload.rate,
            source=payload.source,
        )
        db.add(rate)
        db.commit()
        db.refresh(rate)
        return rate

    @staticmethod
    def get_latest_rates(db: Session) -> list[ExchangeRate]:
        pairs = db.query(ExchangeRate.currency_pair).distinct().all()
        latest_rates = []
        for (p,) in pairs:
            r = db.query(ExchangeRate).filter(
                ExchangeRate.currency_pair == p
            ).order_by(ExchangeRate.as_of_date.desc()).first()
            if r:
                latest_rates.append(r)
        return latest_rates

    # --- Market Segment Baselines (62-63) ---
    @staticmethod
    def list_segment_baselines(db: Session) -> list[MarketSegmentBaseline]:
        return db.query(MarketSegmentBaseline).order_by(MarketSegmentBaseline.segment_name.asc()).all()

    @staticmethod
    def upsert_segment_baseline(
        db: Session, segment_name: str, payload: MarketSegmentBaselineUpsertRequest, user_id: int
    ) -> MarketSegmentBaseline:
        seg = db.query(MarketSegmentBaseline).filter(
            MarketSegmentBaseline.segment_name == segment_name.strip()
        ).first()

        if not seg:
            seg = MarketSegmentBaseline(
                segment_name=segment_name.strip(),
                baseline_adr_inr=payload.baseline_adr_inr,
                baseline_cancellation_rate=payload.baseline_cancellation_rate,
                baseline_lead_time_days=payload.baseline_lead_time_days,
                notes=payload.notes,
            )
            db.add(seg)
        else:
            if payload.baseline_adr_inr is not None:
                seg.baseline_adr_inr = payload.baseline_adr_inr
            if payload.baseline_cancellation_rate is not None:
                seg.baseline_cancellation_rate = payload.baseline_cancellation_rate
            if payload.baseline_lead_time_days is not None:
                seg.baseline_lead_time_days = payload.baseline_lead_time_days
            if payload.notes is not None:
                seg.notes = payload.notes

        db.add(AuditLog(
            user_id=user_id,
            action="MARKET_SEGMENT_BASELINE_UPSERTED",
            entity_type="market_segment_baselines",
            entity_id=segment_name,
        ))
        db.commit()
        db.refresh(seg)
        return seg
