from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# =============================================================================
# BASE & MIXINS
# =============================================================================

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# =============================================================================
# DOMAIN ENUMS
# =============================================================================

# Split from the old combined InventoryType (Round 4). Deprecated: InventoryType.
class InventoryCategory(str, enum.Enum):
    HOTEL = "HOTEL"
    FLIGHT = "FLIGHT"


class UnitType(str, enum.Enum):
    ROOM_NIGHT = "ROOM_NIGHT"
    SEAT = "SEAT"


class SupplierType(str, enum.Enum):
    HOTEL = "HOTEL"
    FLIGHT = "FLIGHT"
    BOTH = "BOTH"


class OfferStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    EXHAUSTED = "EXHAUSTED"


class MLModelType(str, enum.Enum):
    HOTEL_CANCELLATION = "hotel_cancellation"
    FLIGHT_PRICE = "flight_price"
    DEMAND_FORECASTING = "demand_forecasting"
    INVENTORY_FORECASTING = "inventory_forecasting"
    SUPPLIER_LEAD_TIME = "supplier_lead_time_prediction"


class SolverBackend(str, enum.Enum):
    SCIP = "SCIP"
    CBC = "CBC"
    HIGHS = "HIGHS"
    SAT = "SAT"


class SolverStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    ERROR = "ERROR"


class RejectionReasonCode(str, enum.Enum):
    NEGATIVE_CONTRIBUTION = "NEGATIVE_CONTRIBUTION"
    MOQ_EXCEEDS_DEMAND = "MOQ_EXCEEDS_DEMAND"
    SUPPLIER_CAP_BINDING = "SUPPLIER_CAP_BINDING"
    MOQ_EXCEEDS_BUDGET = "MOQ_EXCEEDS_BUDGET"
    NOT_SELECTED_BY_OPTIMAL_ALLOCATION = "NOT_SELECTED_BY_OPTIMAL_ALLOCATION"
    EXPIRED_OFFER = "EXPIRED_OFFER"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ORDERED = "ORDERED"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    PROCUREMENT_MANAGER = "PROCUREMENT_MANAGER"
    ANALYST = "ANALYST"


class PipelineStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"


class DataQualitySeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TrainingStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class ConstraintType(str, enum.Enum):
    BUDGET = "BUDGET"
    SUPPLIER_CAP = "SUPPLIER_CAP"
    DESTINATION_CAP = "DESTINATION_CAP"
    CATEGORY_MIN = "CATEGORY_MIN"
    CATEGORY_MAX = "CATEGORY_MAX"
    RISK_CAP = "RISK_CAP"
    DEMAND_CEILING = "DEMAND_CEILING"
    MOQ_LINKING = "MOQ_LINKING"
    SUPPLIER_CAPACITY = "SUPPLIER_CAPACITY"


class FulfillmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    DELIVERED = "DELIVERED"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"


class POStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class NotificationType(str, enum.Enum):
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RECOMMENDATION_PENDING = "RECOMMENDATION_PENDING"
    RECOMMENDATION_APPROVED = "RECOMMENDATION_APPROVED"
    PO_OVERDUE = "PO_OVERDUE"
    SUPPLIER_PERFORMANCE_DROP = "SUPPLIER_PERFORMANCE_DROP"
    DATA_QUALITY_ALERT = "DATA_QUALITY_ALERT"
    MODEL_DRIFT = "MODEL_DRIFT"


class NotificationChannel(str, enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class OptimizationMode(str, enum.Enum):
    HOTEL_ONLY = "HOTEL_ONLY"
    FLIGHT_ONLY = "FLIGHT_ONLY"
    JOINT = "JOINT"


class BudgetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    EXHAUSTED = "EXHAUSTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class BudgetPeriodType(str, enum.Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"
    AD_HOC = "AD_HOC"


class BudgetScope(str, enum.Enum):
    GLOBAL = "GLOBAL"
    HOTEL_ONLY = "HOTEL_ONLY"
    FLIGHT_ONLY = "FLIGHT_ONLY"
    DESTINATION = "DESTINATION"


class BudgetTransactionType(str, enum.Enum):
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    COMMIT = "COMMIT"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


class ReportType(str, enum.Enum):
    DATA_QUALITY = "DATA_QUALITY"
    EDA_SUMMARY = "EDA_SUMMARY"
    MODEL_EVALUATION = "MODEL_EVALUATION"
    OPTIMIZATION_SUMMARY = "OPTIMIZATION_SUMMARY"
    SCENARIO_COMPARISON = "SCENARIO_COMPARISON"
    SENSITIVITY_ANALYSIS = "SENSITIVITY_ANALYSIS"
    DEMAND_INVENTORY_FORECAST = "DEMAND_INVENTORY_FORECAST"
    CANCELLATION_PRICE_ANALYSIS = "CANCELLATION_PRICE_ANALYSIS"
    PROCUREMENT_DECISIONS = "PROCUREMENT_DECISIONS"
    SUPPLIER_PERFORMANCE = "SUPPLIER_PERFORMANCE"
    PROFITABILITY_ANALYTICS = "PROFITABILITY_ANALYTICS"
    CUSTOM = "CUSTOM"


class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportFormat(str, enum.Enum):
    PDF = "PDF"
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"
    HTML = "HTML"


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


# =============================================================================
# SECTION 1: MASTER REFERENCE DATA
# =============================================================================

class Destination(Base, TimestampMixin):
    __tablename__ = "destinations"

    dest_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    airport_code: Mapped[str | None] = mapped_column(String(8), index=True)
    search_volume_ceiling: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rolling_7d_searches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rolling_30d_searches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="destination", foreign_keys="InventoryItem.dest_id"
    )
    inventory_origin_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="origin_destination", foreign_keys="InventoryItem.origin_dest_id"
    )
    offers: Mapped[list["SupplierOffer"]] = relationship(
        back_populates="destination", foreign_keys="SupplierOffer.dest_id"
    )
    origin_offers: Mapped[list["SupplierOffer"]] = relationship(
        back_populates="origin_destination", foreign_keys="SupplierOffer.origin_dest_id"
    )
    market_signals: Mapped[list["MarketSignal"]] = relationship(back_populates="destination")
    daily_metrics: Mapped[list["DestinationDailyMetrics"]] = relationship(back_populates="destination", foreign_keys="DestinationDailyMetrics.dest_id")
    search_events: Mapped[list["CustomerSearchEvent"]] = relationship(
        back_populates="destination", foreign_keys="CustomerSearchEvent.dest_id"
    )


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    supplier_type: Mapped[SupplierType] = mapped_column(SAEnum(SupplierType), nullable=False)
    fulfillment_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    avg_lead_time_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lead_time_variance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    default_salvage_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_spend_share_cap: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    offers: Mapped[list["SupplierOffer"]] = relationship(back_populates="supplier")
    performance_snapshots: Mapped[list["SupplierPerformanceSnapshot"]] = relationship(
        back_populates="supplier"
    )
    contacts: Mapped[list["SupplierContact"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")

    __table_args__ = (
        CheckConstraint("fulfillment_rate >= 0.0 AND fulfillment_rate <= 1.0", name="ck_supplier_fulfillment"),
        CheckConstraint("max_spend_share_cap > 0.0 AND max_spend_share_cap <= 1.0", name="ck_supplier_cap"),
        CheckConstraint("default_salvage_rate >= 0.0 AND default_salvage_rate <= 1.0", name="ck_supplier_salvage"),
    )


class SupplierContact(Base, TimestampMixin):
    __tablename__ = "supplier_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_role: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    supplier: Mapped[Supplier] = relationship(back_populates="contacts")

    __table_args__ = (
        Index("ix_supplier_contact_primary", "supplier_id", "is_primary"),
        Index("uq_supplier_primary_contact", "supplier_id", unique=True, postgresql_where=text("is_primary = true")),
    )


# --- Round 4: NEW canonical inventory identity ---

class InventoryItem(Base, TimestampMixin):
    """Underlying hotel/flight inventory identity used by Phase 5 candidate builder."""
    __tablename__ = "inventory_items"

    inventory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType), nullable=False)
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    origin_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    external_reference: Mapped[str | None] = mapped_column(String(128), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    destination: Mapped[Destination] = relationship(
        back_populates="inventory_items", foreign_keys=[dest_id]
    )
    origin_destination: Mapped[Destination | None] = relationship(
        back_populates="inventory_origin_items", foreign_keys=[origin_dest_id]
    )
    snapshots: Mapped[list["InventorySnapshot"]] = relationship(back_populates="inventory_item")
    offers: Mapped[list["SupplierOffer"]] = relationship(back_populates="inventory_item")

    __table_args__ = (
        CheckConstraint(
            "(inventory_category = 'HOTEL' AND unit_type = 'ROOM_NIGHT') OR "
            "(inventory_category = 'FLIGHT' AND unit_type = 'SEAT')",
            name="ck_inv_item_category_unit",
        ),
        CheckConstraint(
            "(inventory_category = 'HOTEL' AND origin_dest_id IS NULL) OR "
            "(inventory_category = 'FLIGHT')",
            name="ck_inv_item_origin_by_category",
        ),
    )


# --- Round 4: NEW raw search-event stream ---

class CustomerSearchEvent(Base, TimestampMixin):
    """Raw customer search events — supports demand forecasting & search-to-book analytics."""
    __tablename__ = "customer_search_events"

    search_id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        default=lambda: f"SRCH_{uuid.uuid4().hex[:12].upper()}",
    )
    search_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    origin_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="SET NULL"), index=True
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    travellers_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rooms_count: Mapped[int | None] = mapped_column(Integer)
    search_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency_code: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    clicked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    booking_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    conversion_value_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    destination: Mapped[Destination] = relationship(
        back_populates="search_events", foreign_keys=[dest_id]
    )

    __table_args__ = (
        CheckConstraint("travellers_count >= 1", name="ck_search_travellers_positive"),
        CheckConstraint("rooms_count IS NULL OR rooms_count >= 1", name="ck_search_rooms_positive"),
        CheckConstraint("search_price IS NULL OR search_price >= 0", name="ck_search_price_nonneg"),
        Index("ix_search_dest_cat_date", "dest_id", "inventory_category", "search_date"),
    )


class MarketSignal(Base, TimestampMixin):
    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    demand_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_peak_season: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    destination: Mapped[Destination] = relationship(back_populates="market_signals")

    __table_args__ = (
        UniqueConstraint("dest_id", "signal_date", "event_name", name="uq_market_signal"),
        CheckConstraint("demand_multiplier > 0", name="ck_signal_multiplier_positive"),
    )


class ExchangeRate(Base):
    """Historical FX — supports the €→₹ EUR/INR normalization done in hotel_economics.py."""
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    # Round 4: Numeric for precision
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # RBI, ECB, ...

    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "as_of_date", name="uq_fx_rate_date"),
        CheckConstraint("rate > 0", name="ck_fx_rate_positive"),
    )


class MarketSegmentBaseline(Base, TimestampMixin):
    """Baseline priors for Bayesian shrinkage (λ = 0.70) in hotel_cancellation model."""
    __tablename__ = "market_segment_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segment_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    baseline_cancellation_rate: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_adr_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    baseline_lead_time_days: Mapped[float] = mapped_column(Float, nullable=False)
    booking_count_sample: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint("baseline_cancellation_rate >= 0 AND baseline_cancellation_rate <= 1",
                        name="ck_segment_cancel_rate"),
        CheckConstraint("baseline_adr_inr >= 0", name="ck_segment_adr_nonneg"),
        CheckConstraint("baseline_lead_time_days >= 0", name="ck_segment_lead_time_nonneg"),
        CheckConstraint("booking_count_sample >= 0", name="ck_segment_sample_nonneg"),
    )


class DestinationDailyMetrics(Base):
    """Time-series per-destination features used by demand_forecasting & inventory models."""
    __tablename__ = "destination_daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Round 4: split grain by inventory category (hotel vs flight at same destination)
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    origin_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="SET NULL"), index=True
    )
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    search_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    booking_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_adr_inr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cancellation_rate: Mapped[float | None] = mapped_column(Float)
    load_factor: Mapped[float | None] = mapped_column(Float)

    destination: Mapped[Destination] = relationship(back_populates="daily_metrics", foreign_keys=[dest_id])

    __table_args__ = (
        UniqueConstraint(
            "dest_id", "inventory_category", "origin_dest_id", "metric_date",
            name="uq_dest_daily_metric",
            postgresql_nulls_not_distinct=True,
        ),
    )


class ProcurementBudget(Base, TimestampMixin):
    """Admin-managed persistent budget envelopes. OptimizationRuns draw from these."""
    __tablename__ = "procurement_budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    scope: Mapped[BudgetScope] = mapped_column(SAEnum(BudgetScope), nullable=False, index=True)
    scope_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), index=True
    )
    period_type: Mapped[BudgetPeriodType] = mapped_column(SAEnum(BudgetPeriodType), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    total_amount_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    spent_amount_inr: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0.00"), nullable=False
    )
    reserved_amount_inr: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0.00"), nullable=False
    )

    status: Mapped[BudgetStatus] = mapped_column(
        SAEnum(BudgetStatus), default=BudgetStatus.DRAFT, nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    ledger_entries: Mapped[list["BudgetLedgerEntry"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("total_amount_inr > 0", name="ck_budget_amount_positive"),
        CheckConstraint("spent_amount_inr >= 0 AND reserved_amount_inr >= 0",
                        name="ck_budget_consumption_nonneg"),
        CheckConstraint("spent_amount_inr + reserved_amount_inr <= total_amount_inr",
                        name="ck_budget_no_overcommit"),
        CheckConstraint("period_start <= period_end", name="ck_budget_period_range"),
        CheckConstraint(
            "(scope = 'DESTINATION' AND scope_dest_id IS NOT NULL) OR "
            "(scope != 'DESTINATION' AND scope_dest_id IS NULL)",
            name="ck_budget_dest_scope",
        ),
        Index("ix_budget_scope_period", "scope", "scope_dest_id", "period_start", "period_end"),
    )


# --- Round 4: NEW budget ledger (append-only) ---

class BudgetLedgerEntry(Base):
    """Append-only transactional ledger for ProcurementBudget. Never updated or deleted."""
    __tablename__ = "budget_ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_budgets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    transaction_type: Mapped[BudgetTransactionType] = mapped_column(
        SAEnum(BudgetTransactionType), nullable=False, index=True
    )
    # Signed amount: RESERVE/COMMIT negative, RELEASE/REFUND positive, ADJUSTMENT either.
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    previous_balance_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    new_balance_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    optimization_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="SET NULL"), index=True
    )
    po_number: Mapped[str | None] = mapped_column(
        ForeignKey("purchase_orders.po_number", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)

    # Append-only timestamp — must exist for ix_ledger_budget_time
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    budget: Mapped[ProcurementBudget] = relationship(back_populates="ledger_entries")

    __table_args__ = (
        CheckConstraint("amount_inr != 0", name="ck_ledger_amount_nonzero"),
        Index("ix_ledger_budget_time", "budget_id", "created_at"),
    )


class OptimizationConfigTemplate(Base, TimestampMixin):
    """Reusable defaults (admin-managed) that PMs apply when launching a run."""
    __tablename__ = "optimization_config_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_mode: Mapped[OptimizationMode] = mapped_column(
        SAEnum(OptimizationMode), default=OptimizationMode.JOINT, nullable=False
    )
    default_solver_backend: Mapped[SolverBackend] = mapped_column(
        SAEnum(SolverBackend), default=SolverBackend.SCIP, nullable=False
    )
    # Round 4: renamed from default_salvage_assumption_pct (it's a rate, 0-1)
    default_salvage_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    default_max_supplier_share: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    default_max_destination_share: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    default_budget_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    extra_params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("default_salvage_rate >= 0 AND default_salvage_rate <= 1",
                        name="ck_template_salvage"),
        CheckConstraint("default_max_supplier_share > 0 AND default_max_supplier_share <= 1",
                        name="ck_template_supplier_share"),
        CheckConstraint("default_max_destination_share > 0 AND default_max_destination_share <= 1",
                        name="ck_template_dest_share"),
    )


# =============================================================================
# SECTION 2: DATA PIPELINE & DATA QUALITY
# =============================================================================

class IngestionBatch(Base, TimestampMixin):
    __tablename__ = "ingestion_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False,
        default=lambda: f"BATCH_{uuid.uuid4().hex[:10].upper()}",
    )
    dataset_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    batch_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[PipelineStatus] = mapped_column(
        SAEnum(PipelineStatus), default=PipelineStatus.PENDING, nullable=False
    )
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_duplicates_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    processed_parquet_path: Mapped[str | None] = mapped_column(String(512))

    quality_reports: Mapped[list["DataQualityReport"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class DataQualityReport(Base, TimestampMixin):
    __tablename__ = "data_quality_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_name: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[DataQualitySeverity] = mapped_column(SAEnum(DataQualitySeverity), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    violated_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    batch: Mapped[IngestionBatch] = relationship(back_populates="quality_reports")


# =============================================================================
# SECTION 3: FEATURE ENGINEERING REGISTRY
# =============================================================================

class FeatureSet(Base, TimestampMixin):
    __tablename__ = "feature_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parquet_path: Mapped[str] = mapped_column(String(512), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_columns_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    temporal_split_cutoff: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    training_runs: Mapped[list["ModelTrainingRun"]] = relationship(back_populates="feature_set")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_feature_set_version"),
    )


# =============================================================================
# SECTION 4: ACTIVE INVENTORY & SUPPLIER OFFERS
# =============================================================================

class SupplierOffer(Base, TimestampMixin):
    __tablename__ = "supplier_offers"

    offer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Round 4: canonical inventory FK (nullable initially for back-compat; should be NOT NULL for new rows)
    inventory_id: Mapped[str | None] = mapped_column(
        ForeignKey("inventory_items.inventory_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    origin_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType), nullable=False)

    # INR-normalized commercial terms (what MILP consumes)
    unit_cost_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    list_price_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Round 4: original currency provenance
    original_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    original_list_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency_code: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    exchange_rate_id: Mapped[int | None] = mapped_column(
        ForeignKey("exchange_rates.id", ondelete="SET NULL"), index=True
    )
    pricing_basis: Mapped[str | None] = mapped_column(String(32))  # PER_UNIT, PER_STAY, ...
    external_offer_reference: Mapped[str | None] = mapped_column(String(128), index=True)

    moq: Mapped[int] = mapped_column(Integer, nullable=False)
    # Contractual maximum quantity (distinct from point-in-time availability, which lives in InventorySnapshot)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[OfferStatus] = mapped_column(
        SAEnum(OfferStatus), default=OfferStatus.ACTIVE, nullable=False
    )

    # Hotel 4-outcome economics
    customer_refund_rate_rc: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resale_probability_f: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resale_discount_delta: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    supplier_refund_unsold_r_u: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    supplier_refund_cancelled_r_c: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Flight spoilage & salvage
    salvage_rate_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spoilage_penalty_psi_inr: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    supplier: Mapped[Supplier] = relationship(back_populates="offers")
    inventory_item: Mapped[InventoryItem | None] = relationship(back_populates="offers")
    destination: Mapped[Destination] = relationship(
        back_populates="offers", foreign_keys=[dest_id]
    )
    origin_destination: Mapped[Destination | None] = relationship(
        back_populates="origin_offers", foreign_keys=[origin_dest_id]
    )
    predictions: Mapped[list["OfferPrediction"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("unit_cost_inr >= 0", name="ck_offer_positive_cost"),
        CheckConstraint("list_price_inr >= 0", name="ck_offer_positive_price"),
        CheckConstraint("original_unit_cost IS NULL OR original_unit_cost >= 0",
                        name="ck_offer_original_cost_nonneg"),
        CheckConstraint("original_list_price IS NULL OR original_list_price >= 0",
                        name="ck_offer_original_price_nonneg"),
        CheckConstraint("moq >= 1", name="ck_offer_moq_min"),
        CheckConstraint("max_capacity >= moq", name="ck_offer_capacity_gte_moq"),
        CheckConstraint("valid_from <= valid_until", name="ck_offer_valid_range"),
        CheckConstraint("valid_until <= travel_date", name="ck_offer_valid_before_travel"),
        CheckConstraint("customer_refund_rate_rc >= 0 AND customer_refund_rate_rc <= 1",
                        name="ck_offer_rc"),
        CheckConstraint("resale_probability_f >= 0 AND resale_probability_f <= 1", name="ck_offer_f"),
        CheckConstraint("supplier_refund_unsold_r_u >= 0 AND supplier_refund_unsold_r_u <= 1",
                        name="ck_offer_ru"),
        CheckConstraint("supplier_refund_cancelled_r_c >= 0 AND supplier_refund_cancelled_r_c <= 1",
                        name="ck_offer_rc_ref"),
        CheckConstraint("salvage_rate_s >= 0 AND salvage_rate_s <= 1", name="ck_offer_salvage"),
        CheckConstraint("spoilage_penalty_psi_inr >= 0", name="ck_offer_spoilage"),
        CheckConstraint(
            "(inventory_category = 'HOTEL' AND origin_dest_id IS NULL) OR "
            "(inventory_category = 'FLIGHT' AND (origin_dest_id IS NULL OR origin_dest_id != dest_id))",
            name="ck_offer_origin_by_category",
        ),
        CheckConstraint(
            "(inventory_category = 'HOTEL' AND unit_type = 'ROOM_NIGHT') OR "
            "(inventory_category = 'FLIGHT' AND unit_type = 'SEAT')",
            name="ck_offer_category_unit",
        ),
        Index("ix_offer_active_lookup", "status", "valid_until", "inventory_category"),
    )


class InventorySnapshot(Base):
    """Point-in-time inventory availability per InventoryItem."""
    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_id: Mapped[str] = mapped_column(
        ForeignKey("inventory_items.inventory_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="SET NULL"), index=True
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    travel_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    available_units: Mapped[int] = mapped_column(Integer, nullable=False)
    # Renamed from reserved_units (Round 4): booked + available = total
    booked_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depletion_velocity_per_day: Mapped[float | None] = mapped_column(Float)

    inventory_item: Mapped[InventoryItem] = relationship(back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint(
            "inventory_id", "travel_date", "snapshot_at",
            name="uq_inventory_snapshot_point",
        ),
        CheckConstraint("total_units >= 0", name="ck_snapshot_total_nonneg"),
        CheckConstraint("available_units >= 0", name="ck_snapshot_available_nonneg"),
        CheckConstraint("booked_units >= 0", name="ck_snapshot_booked_nonneg"),
        CheckConstraint(
            "available_units + booked_units = total_units",
            name="ck_snapshot_capacity_conservation",
        ),
    )


class SupplierPerformanceSnapshot(Base):
    __tablename__ = "supplier_performance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fulfillment_rate_7d: Mapped[float] = mapped_column(Float, nullable=False)
    fulfillment_rate_30d: Mapped[float] = mapped_column(Float, nullable=False)
    avg_lead_time_days_30d: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_variance_30d: Mapped[float] = mapped_column(Float, nullable=False)
    orders_count_30d: Mapped[int] = mapped_column(Integer, nullable=False)
    dispute_count_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    supplier: Mapped[Supplier] = relationship(back_populates="performance_snapshots")

    __table_args__ = (
        UniqueConstraint("supplier_id", "as_of_date", name="uq_supplier_perf_date"),
        CheckConstraint("fulfillment_rate_30d >= 0 AND fulfillment_rate_30d <= 1",
                        name="ck_supplier_perf_fr"),
    )


# =============================================================================
# SECTION 5: ML MODEL REGISTRY, TRAINING & FORECASTS
# =============================================================================

class MLModel(Base, TimestampMixin):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_type: Mapped[MLModelType] = mapped_column(SAEnum(MLModelType), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_dir: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    training_cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_champion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Round 4: model governance
    artifact_checksum: Mapped[str | None] = mapped_column(String(64))
    feature_schema_version: Mapped[str | None] = mapped_column(String(32))
    feature_schema_hash: Mapped[str | None] = mapped_column(String(64))
    framework_version: Mapped[str | None] = mapped_column(String(32))
    # BASELINE | TRAINED | EXPERIMENTAL | CHAMPION
    model_status: Mapped[str] = mapped_column(String(32), default="TRAINED", nullable=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    training_runs: Mapped[list["ModelTrainingRun"]] = relationship(back_populates="promoted_model")

    __table_args__ = (
        UniqueConstraint("model_type", "version", name="uq_ml_model_version"),
        Index(
            "uq_ml_model_single_champion",
            "model_type",
            unique=True,
            postgresql_where=text("is_champion = true"),
        ),
    )


class ModelTrainingRun(Base, TimestampMixin):
    __tablename__ = "model_training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_type: Mapped[MLModelType] = mapped_column(SAEnum(MLModelType), nullable=False, index=True)
    feature_set_id: Mapped[int] = mapped_column(
        ForeignKey("feature_sets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    hyperparameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cv_folds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    status: Mapped[TrainingStatus] = mapped_column(
        SAEnum(TrainingStatus), default=TrainingStatus.PENDING, nullable=False, index=True
    )
    # Round 4: nullable for PENDING runs
    training_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    feature_importance_json: Mapped[dict[str, float] | None] = mapped_column(JSON)
    artifact_dir: Mapped[str | None] = mapped_column(String(255))
    promoted_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ml_models.id", ondelete="SET NULL"), index=True
    )
    started_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    feature_set: Mapped[FeatureSet] = relationship(back_populates="training_runs")
    promoted_model: Mapped[MLModel | None] = relationship(back_populates="training_runs")


class OfferPrediction(Base, TimestampMixin):
    __tablename__ = "offer_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("supplier_offers.offer_id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Round 4: link prediction to the run that generated it (nullable for pre-run predictions)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="SET NULL"), index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    prediction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    model_version: Mapped[str | None] = mapped_column(String(32))

    predicted_cancellation_prob: Mapped[float | None] = mapped_column(Float)
    predicted_market_price_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    predicted_sell_through_theta: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_demand_units: Mapped[int | None] = mapped_column(Integer)
    predicted_lead_time_days: Mapped[float | None] = mapped_column(Float)

    expected_unit_contribution_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    break_even_sell_through: Mapped[float] = mapped_column(Float, nullable=False)
    bayesian_shrinkage_lambda: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)
    model_versions_json: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)

    offer: Mapped[SupplierOffer] = relationship(back_populates="predictions")

    __table_args__ = (
        UniqueConstraint(
            "offer_id", "as_of_date", "run_id",
            name="uq_offer_prediction_date_run",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("predicted_sell_through_theta >= 0.0 AND predicted_sell_through_theta <= 1.0",
                        name="ck_pred_theta"),
        CheckConstraint("predicted_cancellation_prob IS NULL OR "
                        "(predicted_cancellation_prob >= 0.0 AND predicted_cancellation_prob <= 1.0)",
                        name="ck_pred_cancel_prob"),
        CheckConstraint("break_even_sell_through >= 0.0",
                        name="ck_pred_break_even"),
    )


class DestinationDemandForecast(Base):
    """Forward-looking destination demand forecast (analyst view)."""
    __tablename__ = "destination_demand_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType), nullable=False)
    origin_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="SET NULL"), index=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted_demand_units: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_search_volume: Mapped[int | None] = mapped_column(Integer)
    confidence_lower: Mapped[float | None] = mapped_column(Float)
    confidence_upper: Mapped[float | None] = mapped_column(Float)
    demand_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "dest_id", "inventory_category", "origin_dest_id", "forecast_date", "as_of_date",
            name="uq_demand_forecast_point",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("predicted_demand_units >= 0", name="ck_demand_forecast_nonneg"),
    )


class DestinationInventoryForecast(Base):
    """Forward-looking destination inventory depletion forecast (analyst view)."""
    __tablename__ = "destination_inventory_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="CASCADE"), nullable=False, index=True
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False, index=True
    )
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType), nullable=False)
    origin_dest_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="SET NULL"), index=True
    )
    # Optional: if forecasting at inventory-item grain instead of destination aggregate
    inventory_id: Mapped[str | None] = mapped_column(
        ForeignKey("inventory_items.inventory_id", ondelete="SET NULL"), index=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted_available_units: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_depletion_velocity: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_lower: Mapped[float | None] = mapped_column(Float)
    confidence_upper: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "dest_id", "inventory_category", "origin_dest_id", "forecast_date", "as_of_date",
            name="uq_inv_forecast_point",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("predicted_available_units >= 0", name="ck_inv_forecast_nonneg"),
        CheckConstraint("predicted_depletion_velocity >= 0", name="ck_inv_velocity_nonneg"),
    )


# =============================================================================
# SECTION 6: OPTIMIZATION
# =============================================================================

class PlatformOptimizationConfig(Base, TimestampMixin):
    """Admin-managed platform budgets & financial assumptions (optimization/config.py)."""
    __tablename__ = "platform_optimization_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    default_total_budget_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    max_supplier_share: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    max_destination_share: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    hotel_min_budget_share: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hotel_max_budget_share: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    flight_min_budget_share: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    flight_max_budget_share: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    target_currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    # Round 4: safer default
    allow_prototype_currency_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prototype_eur_to_inr_rate: Mapped[float] = mapped_column(Float, default=90.0, nullable=False)
    bayesian_shrinkage_lambda: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)
    default_flight_salvage_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    default_solver_backend: Mapped[SolverBackend] = mapped_column(
        SAEnum(SolverBackend), default=SolverBackend.SCIP, nullable=False
    )

    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("default_total_budget_inr > 0", name="ck_cfg_budget_positive"),
        CheckConstraint("max_supplier_share > 0 AND max_supplier_share <= 1", name="ck_cfg_sup_share"),
        CheckConstraint("max_destination_share > 0 AND max_destination_share <= 1", name="ck_cfg_dest_share"),
        CheckConstraint("bayesian_shrinkage_lambda >= 0 AND bayesian_shrinkage_lambda <= 1", name="ck_cfg_lambda"),
        CheckConstraint("hotel_min_budget_share >= 0 AND hotel_max_budget_share <= 1", name="ck_cfg_hotel_range"),
        CheckConstraint("hotel_min_budget_share <= hotel_max_budget_share", name="ck_cfg_hotel_bounds"),
        CheckConstraint("flight_min_budget_share >= 0 AND flight_max_budget_share <= 1", name="ck_cfg_flight_range"),
        CheckConstraint("flight_min_budget_share <= flight_max_budget_share", name="ck_cfg_flight_bounds"),
        Index(
            "uq_platform_config_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )


class OptimizationRun(Base, TimestampMixin):
    __tablename__ = "optimization_runs"

    run_id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        default=lambda: f"RUN_{uuid.uuid4().hex[:12].upper()}",
    )
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    parent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="SET NULL"), index=True
    )

    # Comparison mode + shared group + config anchors
    optimization_mode: Mapped[OptimizationMode] = mapped_column(
        SAEnum(OptimizationMode), default=OptimizationMode.JOINT, nullable=False, index=True
    )
    comparison_group_id: Mapped[str | None] = mapped_column(String(64), index=True)
    config_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_optimization_configs.id", ondelete="SET NULL"), index=True
    )
    config_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("optimization_config_templates.id", ondelete="SET NULL"), index=True
    )
    budget_id: Mapped[int | None] = mapped_column(
        ForeignKey("procurement_budgets.id", ondelete="SET NULL"), index=True
    )

    # OptimizationConfig inputs
    cutoff_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_budget_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    solver_backend: Mapped[SolverBackend] = mapped_column(
        SAEnum(SolverBackend), default=SolverBackend.SCIP, nullable=False
    )
    salvage_assumption_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_supplier_share: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    max_destination_share: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    target_currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    allow_prototype_currency_override: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_versions_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)

    # What-if scenarios
    scenario_name: Mapped[str | None] = mapped_column(String(100))
    scenario_parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Async execution tracking
    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Separate pipeline status from solver status (pipeline can SUCCEED even if solver INFEASIBLE)
    pipeline_status: Mapped[PipelineStatus] = mapped_column(
        SAEnum(PipelineStatus), default=PipelineStatus.PENDING, nullable=False, index=True
    )
    solver_status: Mapped[SolverStatus] = mapped_column(
        SAEnum(SolverStatus), default=SolverStatus.PENDING, nullable=False, index=True
    )
    is_optimal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    solve_time_seconds: Mapped[float | None] = mapped_column(Float)
    mip_gap_pct: Mapped[float | None] = mapped_column(Float)
    best_objective_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    best_bound_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    termination_reason: Mapped[str | None] = mapped_column(String(64))
    active_candidates_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expired_filtered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    num_variables: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    num_constraints: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    infeasibility_reason: Mapped[str | None] = mapped_column(Text)
    solver_parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ortools_version: Mapped[str | None] = mapped_column(String(32))

    # Commercial scorecard
    total_spend_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    budget_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_net_profit_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    return_on_spend_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    selected_offers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_offers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Hotel vs. Flight split
    hotel_spend_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    flight_spend_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0.00"), nullable=False)
    hotel_units_selected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flight_units_selected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Baseline comparison
    greedy_baseline_profit_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    profit_lift_vs_greedy_pct: Mapped[float | None] = mapped_column(Float)
    baseline_comparisons_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # PM plan-level approval
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_notes: Mapped[str | None] = mapped_column(Text)   # PM plan-level rationale

    # Risk metrics: HHI, variance, downside percentiles
    risk_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    artifact_dir: Mapped[str | None] = mapped_column(String(255))

    triggered_by: Mapped[User | None] = relationship(
        back_populates="optimization_runs", foreign_keys=[triggered_by_user_id]
    )
    parent_run: Mapped[OptimizationRun | None] = relationship(remote_side=[run_id])
    recommendations: Mapped[list["ProcurementRecommendation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    events: Mapped[list["OptimizationRunEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="OptimizationRunEvent.sequence_number"
    )
    artifacts: Mapped[list["OptimizationRunArtifact"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    rejections: Mapped[list["RejectedOpportunity"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    sensitivity_scenarios: Mapped[list["SensitivityScenario"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    constraints: Mapped[list["OptimizationConstraint"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["OfferPrediction"]] = relationship(
        back_populates=None, foreign_keys="OfferPrediction.run_id"
    )

    __table_args__ = (
        CheckConstraint("total_budget_inr > 0", name="ck_run_budget_positive"),
        CheckConstraint("salvage_assumption_pct >= 0 AND salvage_assumption_pct <= 1", name="ck_run_salvage"),
        CheckConstraint("max_supplier_share > 0 AND max_supplier_share <= 1", name="ck_run_supplier_share"),
        CheckConstraint("max_destination_share > 0 AND max_destination_share <= 1", name="ck_run_dest_share"),
        CheckConstraint("budget_utilization_pct >= 0", name="ck_run_budget_util"),
        Index("ix_run_cutoff_status", "cutoff_date", "solver_status"),
        Index("ix_run_mode_approval", "optimization_mode", "approval_status"),
        Index("ix_run_comparison_group", "comparison_group_id"),
    )


class OptimizationConstraint(Base):
    __tablename__ = "optimization_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    constraint_type: Mapped[ConstraintType] = mapped_column(
        SAEnum(ConstraintType), nullable=False, index=True
    )
    entity_id: Mapped[str | None] = mapped_column(String(64))
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    is_binding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slack_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    notes: Mapped[str | None] = mapped_column(Text)

    run: Mapped[OptimizationRun] = relationship(back_populates="constraints")

    __table_args__ = (
        Index("ix_constraint_run_type", "run_id", "constraint_type"),
    )


class SensitivityScenario(Base):
    __tablename__ = "sensitivity_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    sweep_parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    parameter_value: Mapped[float] = mapped_column(Float, nullable=False)
    total_spend_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    expected_net_profit_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    return_on_spend_pct: Mapped[float] = mapped_column(Float, nullable=False)
    selected_offers_count: Mapped[int] = mapped_column(Integer, nullable=False)
    solver_status: Mapped[SolverStatus] = mapped_column(
        SAEnum(SolverStatus), default=SolverStatus.OPTIMAL, nullable=False
    )

    run: Mapped[OptimizationRun] = relationship(back_populates="sensitivity_scenarios")

    __table_args__ = (
        UniqueConstraint("run_id", "sweep_parameter", "parameter_value", name="uq_sensitivity_point"),
    )
class OptimizationRunEvent(Base):
    """Execution timeline & progress event log for SSE streaming & audit."""
    __tablename__ = "optimization_run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped["OptimizationRun"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_opt_run_event_seq", "run_id", "sequence_number"),
    )


class OptimizationRunArtifact(Base):
    """Artifact metadata for files generated during an optimization run."""
    __tablename__ = "optimization_run_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped["OptimizationRun"] = relationship(back_populates="artifacts")

    __table_args__ = (
        UniqueConstraint("run_id", "filename", name="uq_run_artifact_filename"),
    )



# =============================================================================
# SECTION 7: EXPLAINABLE RECOMMENDATIONS & REJECTIONS
# =============================================================================

class ProcurementRecommendation(Base, TimestampMixin):
    __tablename__ = "procurement_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("supplier_offers.offer_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_predictions.id", ondelete="SET NULL"), index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False
    )
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType), nullable=False)

    recommended_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_spend_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    expected_unit_contribution_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_total_contribution_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    sell_through_rate: Mapped[float] = mapped_column(Float, nullable=False)
    moq_applied: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity_available: Mapped[int] = mapped_column(Integer, nullable=False)

    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_notes: Mapped[str | None] = mapped_column(Text)

    run: Mapped[OptimizationRun] = relationship(back_populates="recommendations")
    purchase_order_line: Mapped[PurchaseOrderLine | None] = relationship(
        back_populates="recommendation", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("run_id", "offer_id", name="uq_rec_run_offer"),
        CheckConstraint("recommended_qty >= moq_applied", name="ck_rec_qty_gte_moq"),
        CheckConstraint("sell_through_rate >= 0 AND sell_through_rate <= 1", name="ck_rec_sell_through"),
        CheckConstraint("recommended_qty > 0", name="ck_rec_qty_positive"),
    )


class RejectedOpportunity(Base):
    __tablename__ = "rejected_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("supplier_offers.offer_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_predictions.id", ondelete="SET NULL"), index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"), nullable=False
    )
    dest_id: Mapped[str] = mapped_column(
        ForeignKey("destinations.dest_id", ondelete="RESTRICT"), nullable=False
    )
    inventory_category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory), nullable=False
    )
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType), nullable=False)

    reason_code: Mapped[RejectionReasonCode] = mapped_column(
        SAEnum(RejectionReasonCode), nullable=False, index=True
    )
    reason_detail: Mapped[str] = mapped_column(Text, nullable=False)
    # Round 4: nullable — some rejections happen before economics are computed (e.g., EXPIRED_OFFER)
    expected_unit_contribution_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    moq_cost_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    run: Mapped[OptimizationRun] = relationship(back_populates="rejections")

    __table_args__ = (
        Index("ix_rejected_run_reason", "run_id", "reason_code"),
        UniqueConstraint("run_id", "offer_id", name="uq_rejected_run_offer"),
    )


# =============================================================================
# SECTION 8: USERS, ACCESS CONTROL & SESSION
# =============================================================================

class User(Base, TimestampMixin):
    """Email + bcrypt/argon2 hashed password authentication."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.PROCUREMENT_MANAGER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Lifecycle & security
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    custom_permissions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Round 4: email verification, login throttling, password rotation
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    optimization_runs: Mapped[list[OptimizationRun]] = relationship(
        back_populates="triggered_by", foreign_keys="OptimizationRun.triggered_by_user_id"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="RefreshToken.user_id"
    )

    __table_args__ = (
        CheckConstraint("length(hashed_password) >= 20", name="ck_user_hashed_password_len"),
        CheckConstraint("failed_login_attempts >= 0", name="ck_user_failed_logins_nonneg"),
    )


class RefreshToken(Base, TimestampMixin):
    """JWT refresh token rotation & session revocation. Revoked iff revoked_at IS NOT NULL."""
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    token_family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Round 4: reuse detection — points to the token that replaced this one during rotation
    replaced_by_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"), index=True
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens", foreign_keys=[user_id])
    replaced_by_token: Mapped[RefreshToken | None] = relationship(
        remote_side=[id], foreign_keys=[replaced_by_token_id]
    )

    __table_args__ = (
        Index("ix_refresh_family_active", "token_family_id", "revoked_at"),
    )


# =============================================================================
# SECTION 8b: ONE-TIME ACTION TOKENS (email verify, password reset, invites)
# =============================================================================

class UserActionTokenPurpose(str, enum.Enum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"
    INVITE = "INVITE"


class UserActionToken(Base):
    """Hashed, single-use, time-limited tokens for out-of-band auth flows."""
    __tablename__ = "user_action_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[UserActionTokenPurpose] = mapped_column(
        SAEnum(UserActionTokenPurpose), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_action_token_user_purpose", "user_id", "purpose"),
    )


# =============================================================================
# SECTION 9: PURCHASE ORDERS & FULFILLMENT LOOP-BACK
# =============================================================================

class PurchaseOrder(Base, TimestampMixin):
    """PO header — one supplier, many lines. Created from one or more recommendations."""
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        default=lambda: f"PO-{uuid.uuid4().hex[:10].upper()}",
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Optional but recommended: directly links PO to the budget it drew from
    budget_id: Mapped[int | None] = mapped_column(
        ForeignKey("procurement_budgets.id", ondelete="SET NULL"), index=True
    )
    ordered_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    total_committed_spend_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    status: Mapped[POStatus] = mapped_column(
        SAEnum(POStatus), default=POStatus.SUBMITTED, nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("total_committed_spend_inr >= 0", name="ck_po_spend_nonneg"),
    )


class PurchaseOrderLine(Base, TimestampMixin):
    """PO line — one recommendation committed to a PO header."""
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(
        ForeignKey("purchase_orders.po_number", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_recommendations.id", ondelete="RESTRICT"),
        unique=True, nullable=False,
    )
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("supplier_offers.offer_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total_inr: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    recommendation: Mapped[ProcurementRecommendation] = relationship(
        back_populates="purchase_order_line"
    )
    fulfillments: Mapped[list["PurchaseOrderFulfillment"]] = relationship(
        back_populates="line", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("ordered_qty > 0", name="ck_po_line_qty_positive"),
        CheckConstraint("unit_cost_inr >= 0", name="ck_po_line_unit_cost_nonneg"),
        CheckConstraint("line_total_inr >= 0", name="ck_po_line_total_nonneg"),
    )


class PurchaseOrderFulfillment(Base, TimestampMixin):
    """Post-PO delivery / spoilage / salvage — feeds supplier performance & model retraining."""
    __tablename__ = "purchase_order_fulfillments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_lines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivered_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_unit_cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    actual_total_cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))

    # Flight spoilage & salvage
    spoilage_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    salvaged_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fulfilled_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Hotel 4-outcome actuals
    cancelled_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resold_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unsold_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    supplier_refund_received_inr: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0.00"), nullable=False
    )

    actual_revenue_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    actual_net_profit_inr: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    status: Mapped[FulfillmentStatus] = mapped_column(
        SAEnum(FulfillmentStatus), default=FulfillmentStatus.PENDING, nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    dispute_status: Mapped[str | None] = mapped_column(String(32), default="NONE", index=True)
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disputed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    dispute_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispute_resolution_notes: Mapped[str | None] = mapped_column(Text)

    line: Mapped[PurchaseOrderLine] = relationship(back_populates="fulfillments")

    __table_args__ = (
        CheckConstraint("delivered_qty >= 0", name="ck_ful_delivered_nonneg"),
        CheckConstraint("spoilage_units >= 0", name="ck_ful_spoilage_nonneg"),
        CheckConstraint("salvaged_units >= 0", name="ck_ful_salvaged_nonneg"),
        CheckConstraint("fulfilled_units >= 0", name="ck_ful_fulfilled_nonneg"),
        CheckConstraint("cancelled_units >= 0 AND resold_units >= 0 AND unsold_units >= 0",
                        name="ck_ful_hotel_nonneg"),
        CheckConstraint("resold_units <= cancelled_units", name="ck_ful_hotel_resold_lte_cancelled"),
        CheckConstraint("supplier_refund_received_inr >= 0", name="ck_ful_refund_nonneg"),
    )


# =============================================================================
# SECTION 10: REPORTS
# =============================================================================

class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        default=lambda: f"RPT_{uuid.uuid4().hex[:10].upper()}",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    report_type: Mapped[ReportType] = mapped_column(SAEnum(ReportType), nullable=False, index=True)
    report_format: Mapped[ReportFormat] = mapped_column(
        SAEnum(ReportFormat), default=ReportFormat.PDF, nullable=False
    )
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus), default=ReportStatus.PENDING, nullable=False, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("optimization_runs.run_id", ondelete="SET NULL"), index=True
    )
    comparison_group_id: Mapped[str | None] = mapped_column(String(64), index=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    generated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)


class ReportSchedule(Base, TimestampMixin):
    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[ReportType] = mapped_column(SAEnum(ReportType), nullable=False)
    report_format: Mapped[ReportFormat] = mapped_column(
        SAEnum(ReportFormat), default=ReportFormat.PDF, nullable=False
    )
    cron_expression: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


# =============================================================================
# SECTION 11: AUDIT & COMPLIANCE
# =============================================================================

class AuditLog(Base):
    """Append-only user action trail. Never updated or deleted once written."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    old_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    new_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_user_time", "user_id", "occurred_at"),
    )


# =============================================================================
# SECTION 12: NOTIFICATIONS & ALERTS
# =============================================================================

class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_notif_user_unread", "user_id", "is_read"),
    )


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel), default=NotificationChannel.IN_APP, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "notification_type", "channel", name="uq_notif_pref"),
    )


# --- Round 4: NEW per-channel delivery tracking ---

class NotificationDelivery(Base, TimestampMixin):
    """Per-channel delivery attempt record — enables retry, audit, and provider tracking."""
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel), nullable=False, index=True
    )
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(128))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    notification: Mapped[Notification] = relationship(back_populates="deliveries")

    __table_args__ = (
        UniqueConstraint("notification_id", "channel", name="uq_notif_delivery_channel"),
        CheckConstraint("attempt_count >= 0", name="ck_delivery_attempts_nonneg"),
    )
