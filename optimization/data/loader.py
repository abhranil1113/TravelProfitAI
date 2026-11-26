"""
optimization/data/loader.py

Safe, point-in-time data loading service for Phase 5 procurement optimization.
Supports both database-backed loading from PostgreSQL and offline Parquet fallback.
"""

import os
import logging
from typing import Dict, Any, Optional
import pandas as pd
from optimization.exceptions import OptimizationError

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Loads operational tables required for optimization from live DB or Parquet."""

    DEFAULT_PATHS = {
        "supplier_offers": "data/processed/supplier_offers/cleaned_supplier_offers.parquet",
        "inventory_availability": "data/processed/inventory/cleaned_inventory_availability.parquet",
        "customer_searches": "data/processed/searches/cleaned_customer_search_events.parquet",
        "market_signals": "data/processed/market_signals/cleaned_market_seasonal_signals.parquet",
    }

    def __init__(
        self,
        base_dir: Optional[str] = None,
        custom_paths: Optional[Dict[str, str]] = None,
        db: Optional[Any] = None,
    ):
        self.base_dir = base_dir or "."
        self.paths = dict(self.DEFAULT_PATHS)
        if custom_paths:
            self.paths.update(custom_paths)
        self.db = db

    def _resolve_path(self, relative_path: str) -> str:
        return os.path.join(self.base_dir, relative_path)

    def load_supplier_offers(self) -> pd.DataFrame:
        """Loads active supplier offers from PostgreSQL if db provided, else Parquet."""
        if self.db is not None:
            try:
                from backend.app.models.schema import SupplierOffer, OfferStatus
                offers = self.db.query(SupplierOffer).filter(
                    SupplierOffer.status == OfferStatus.ACTIVE
                ).all()
                if offers:
                    rows = []
                    for o in offers:
                        is_ref = bool(o.supplier_refund_cancelled_r_c > 0)
                        rows.append({
                            "offer_id": str(o.offer_id),
                            "supplier_id": str(o.supplier_id),
                            "inventory_type": str(o.inventory_category.value if hasattr(o.inventory_category, "value") else o.inventory_category),
                            "inventory_id": str(o.inventory_id) if o.inventory_id else f"INV_{o.offer_id}",
                            "origin_id": str(o.origin_dest_id) if o.origin_dest_id else None,
                            "destination_id": str(o.dest_id),
                            "travel_date": str(o.travel_date),
                            "purchase_cost": float(o.unit_cost_inr),
                            "selling_price": float(o.list_price_inr),
                            "available_quantity": int(o.max_capacity),
                            "minimum_purchase_qty": int(o.moq),
                            "refundable": is_ref,
                            "offer_valid_until": str(o.valid_until),
                            "currency": str(o.currency_code) if o.currency_code else "INR",
                        })
                    logger.info("Loaded %d active supplier offers directly from PostgreSQL.", len(rows))
                    return pd.DataFrame(rows)
            except Exception as e:
                logger.warning("Database supplier offer loading failed (%s). Falling back to Parquet.", e)

        path = self._resolve_path(self.paths["supplier_offers"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing supplier offers dataset at {path}")
        return pd.read_parquet(path)

    def load_inventory_availability(self) -> pd.DataFrame:
        """Loads inventory availability from PostgreSQL snapshots if db provided, else Parquet."""
        if self.db is not None:
            try:
                from sqlalchemy.orm import joinedload
                from backend.app.models.schema import InventorySnapshot
                snaps = self.db.query(InventorySnapshot).options(joinedload(InventorySnapshot.inventory_item)).all()
                if snaps:
                    rows = []
                    for s in snaps:
                        dest = str(s.inventory_item.dest_id) if s.inventory_item else None
                        orig = str(s.inventory_item.origin_dest_id) if (s.inventory_item and s.inventory_item.origin_dest_id) else None
                        unit_type = str(s.inventory_item.unit_type.value if hasattr(s.inventory_item.unit_type, "value") else s.inventory_item.unit_type) if s.inventory_item else ("ROOM_NIGHT" if str(s.inventory_category.value if hasattr(s.inventory_category, "value") else s.inventory_category) == "HOTEL" else "SEAT")
                        snap_date = s.snapshot_at.date() if hasattr(s.snapshot_at, "date") else str(s.snapshot_at)
                        rows.append({
                            "snapshot_id": str(s.id),
                            "inventory_id": str(s.inventory_id),
                            "inventory_type": str(s.inventory_category.value if hasattr(s.inventory_category, "value") else s.inventory_category),
                            "supplier_id": str(s.supplier_id) if s.supplier_id else None,
                            "origin_id": orig,
                            "destination_id": dest,
                            "travel_date": str(s.travel_date),
                            "snapshot_date": str(snap_date),
                            "total_capacity": int(s.total_units),
                            "booked_quantity": int(s.booked_units),
                            "available_quantity": int(s.available_units),
                            "sold_out": bool(s.available_units <= 0),
                            "unit_type": unit_type,
                        })
                    logger.info("Loaded %d inventory snapshot records directly from PostgreSQL.", len(rows))
                    return pd.DataFrame(rows)
            except Exception as e:
                logger.warning("Database inventory snapshot loading failed (%s). Falling back to Parquet.", e)

        path = self._resolve_path(self.paths["inventory_availability"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing inventory availability dataset at {path}")
        return pd.read_parquet(path)

    def load_customer_searches(self) -> pd.DataFrame:
        """Loads customer searches from PostgreSQL if db provided, else Parquet."""
        if self.db is not None:
            try:
                from backend.app.models.schema import CustomerSearchEvent
                searches = (
                    self.db.query(CustomerSearchEvent)
                    .order_by(CustomerSearchEvent.search_date.desc(), CustomerSearchEvent.search_id.asc())
                    .limit(10000)
                    .all()
                )
                if searches:
                    rows = []
                    for s in searches:
                        inv_cat = str(s.inventory_category.value if hasattr(s.inventory_category, "value") else s.inventory_category)
                        price = float(s.search_price) if s.search_price is not None else 5000.0
                        rooms = int(s.rooms_count) if s.rooms_count is not None else (int(s.travellers_count) if inv_cat == "HOTEL" else None)
                        rows.append({
                            "search_id": str(s.search_id),
                            "user_id": str(s.user_session_id) if s.user_session_id else None,
                            "search_date": str(s.search_date),
                            "travel_date": str(s.travel_date) if s.travel_date else str(s.search_date),
                            "destination_id": str(s.dest_id),
                            "origin_id": str(s.origin_dest_id) if s.origin_dest_id else None,
                            "inventory_type": inv_cat,
                            "travellers_count": int(s.travellers_count),
                            "rooms_count": rooms,
                            "search_price": price,
                            "clicked": bool(s.clicked),
                            "booking_completed": bool(s.booking_completed),
                            "currency": str(s.currency_code) if s.currency_code else "INR",
                        })
                    logger.info("Loaded %d customer search events directly from PostgreSQL.", len(rows))
                    return pd.DataFrame(rows)
            except Exception as e:
                logger.warning("Database customer searches loading failed (%s). Falling back to Parquet.", e)

        path = self._resolve_path(self.paths["customer_searches"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing customer search events dataset at {path}")
        return pd.read_parquet(path)

    def load_market_signals(self) -> pd.DataFrame:
        """Loads market signals from PostgreSQL if db provided, else Parquet."""
        if self.db is not None:
            try:
                from backend.app.models.schema import MarketSignal
                signals = self.db.query(MarketSignal).all()
                if signals:
                    rows = []
                    for m in signals:
                        sig_dt = m.signal_date
                        month = int(sig_dt.month) if hasattr(sig_dt, "month") else 1
                        mult = float(m.demand_multiplier) if m.demand_multiplier is not None else 1.0
                        is_holiday = bool("holiday" in m.signal_type.lower() or "holiday" in m.event_name.lower())
                        is_festival = bool("festival" in m.signal_type.lower() or "festival" in m.event_name.lower())
                        is_event = bool(m.event_name and m.event_name.strip() != "NONE")
                        rows.append({
                            "signal_id": str(m.id),
                            "destination_id": str(m.dest_id),
                            "travel_date": str(sig_dt),
                            "month": month,
                            "season_type": "PEAK" if m.is_peak_season else "NORMAL",
                            "holiday_indicator": is_holiday,
                            "festival_indicator": is_festival,
                            "event_indicator": is_event,
                            "temperature": 25.0,
                            "rainfall_mm": 0.0,
                            "demand_index": mult,
                        })
                    logger.info("Loaded %d market signal records directly from PostgreSQL.", len(rows))
                    return pd.DataFrame(rows)
            except Exception as e:
                logger.warning("Database market signals loading failed (%s). Falling back to Parquet.", e)

        path = self._resolve_path(self.paths["market_signals"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing market seasonal signals dataset at {path}")
        return pd.read_parquet(path)

