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
            query = query.filter(MarketSignal.signal_date >= start_date)
        if end_date:
            query = query.filter(MarketSignal.signal_date <= end_date)

        total = query.count()
        signals = query.order_by(MarketSignal.signal_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return signals, total

    @staticmethod
    def create_market_signal(db: Session, payload: MarketSignalCreateRequest, user_id: int) -> MarketSignal:
        sig_date = payload.signal_date or payload.start_date or date.today()
        ev_name = payload.event_name or payload.headline or payload.description or f"{payload.signal_type} Event"
        multiplier = payload.demand_multiplier or payload.signal_value or payload.demand_impact_multiplier or 1.0

        signal = MarketSignal(
            dest_id=payload.dest_id.upper(),
            signal_date=sig_date,
            signal_type=payload.signal_type.strip(),
            event_name=ev_name[:120],
            demand_multiplier=float(multiplier),
            is_peak_season=payload.is_peak_season or (payload.severity == "HIGH"),
        )
        db.add(signal)
        db.add(AuditLog(
            user_id=user_id,
            action="MARKET_SIGNAL_CREATED",
            entity_type="market_signals",
            entity_id=payload.dest_id.upper(),
            new_value_json={"signal_type": signal.signal_type, "multiplier": signal.demand_multiplier},
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
        if payload.demand_multiplier is not None:
            signal.demand_multiplier = payload.demand_multiplier
        elif payload.demand_impact_multiplier is not None:
            signal.demand_multiplier = payload.demand_impact_multiplier
        elif payload.signal_value is not None:
            signal.demand_multiplier = payload.signal_value
        if payload.event_name is not None:
            signal.event_name = payload.event_name[:120]
        elif payload.headline is not None:
            signal.event_name = payload.headline[:120]
        elif payload.description is not None:
            signal.event_name = payload.description[:120]
        if payload.signal_date is not None:
            signal.signal_date = payload.signal_date
        elif payload.start_date is not None:
            signal.signal_date = payload.start_date

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
            parts = currency_pair.upper().split("/")
            if len(parts) == 2:
                query = query.filter(ExchangeRate.from_currency == parts[0], ExchangeRate.to_currency == parts[1])
            else:
                query = query.filter(ExchangeRate.from_currency == currency_pair.upper())
        if as_of_date:
            query = query.filter(ExchangeRate.as_of_date == as_of_date)

        total = query.count()
        rates = query.order_by(ExchangeRate.as_of_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return rates, total

    @staticmethod
    def create_exchange_rate(db: Session, payload: ExchangeRateCreateRequest) -> ExchangeRate:
        pair = (payload.currency_pair or "").upper()
        parts = pair.split("/") if "/" in pair else [pair, "INR"]
        from_curr = payload.source_currency.upper() if payload.source_currency else (parts[0] if len(parts) > 0 and parts[0] else "USD")
        to_curr = payload.target_currency.upper() if payload.target_currency else (parts[1] if len(parts) > 1 and parts[1] else "INR")
        rate = ExchangeRate(
            from_currency=from_curr,
            to_currency=to_curr,
            as_of_date=payload.as_of_date or payload.rate_date or date.today(),
            rate=payload.rate,
            source=payload.source or "MANUAL",
        )
        db.add(rate)
        db.commit()
        db.refresh(rate)
        return rate

    @staticmethod
    def get_latest_rates(db: Session) -> list[ExchangeRate]:
        pairs = db.query(ExchangeRate.from_currency, ExchangeRate.to_currency).distinct().all()
        latest_rates = []
        for (f_curr, t_curr) in pairs:
            r = db.query(ExchangeRate).filter(
                ExchangeRate.from_currency == f_curr,
                ExchangeRate.to_currency == t_curr,
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
                baseline_adr_inr=payload.baseline_adr_inr or Decimal("5000.00"),
                baseline_cancellation_rate=payload.baseline_cancellation_rate or 0.15,
                baseline_lead_time_days=payload.baseline_lead_time_days or 14.0,
                booking_count_sample=100,
                as_of_date=date.today(),
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
