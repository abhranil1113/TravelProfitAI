"""
optimization/config.py

Comprehensive configuration models for Phase 5 Optimization Engine.
Follows Stage 1.3 audited assumptions and strict currency validation rules.
Refactored to centralize all business, financial, risk, and solver parameters.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, model_validator


class CurrencyTier(str, Enum):
    VERIFIED_COMMERCIAL = "VERIFIED_COMMERCIAL"
    PROTOTYPE_ASSUMED = "PROTOTYPE_ASSUMED"
    MIXED_OR_UNKNOWN = "MIXED_OR_UNKNOWN"


class SolverBackend(str, Enum):
    SCIP = "SCIP"
    CBC = "CBC"
    HIGHS = "HIGHS"
    SAT = "SAT"


class FinancialAssumptions(BaseModel):
    """Audited financial assumptions from optimization_assumptions.md."""
    # Hotel assumptions
    hotel_base_sell_through: float = Field(0.85, ge=0.0, le=1.0, description="Baseline hotel room-night sell-through probability")
    hotel_customer_refund_rate: float = Field(0.80, ge=0.0, le=1.0, description="Customer refund rate on room cancellation")
    hotel_supplier_refund_rate_cancel: float = Field(0.85, ge=0.0, le=1.0, description="Supplier refund rate on cancellation for refundable contracts")
    hotel_supplier_refund_rate_unsold: float = Field(0.00, ge=0.0, le=1.0, description="Supplier refund rate on unsold room nights")
    hotel_room_resale_probability: float = Field(0.40, ge=0.0, le=1.0, description="Probability of successfully reselling a cancelled room")
    hotel_resale_discount_factor: float = Field(0.90, ge=0.1, le=1.5, description="Price multiplier on resold room nights")
    hotel_assumed_stay_duration: float = Field(2.0, ge=1.0, le=14.0, description="Assumed stay duration in nights per booking")

    # Flight assumptions
    flight_base_sell_through: float = Field(0.85, ge=0.0, le=1.0, description="Baseline unadjusted flight sell-through probability")
    flight_min_sell_through: float = Field(0.05, ge=0.0, le=1.0, description="Lower bound for elasticity-adjusted flight sell-through")
    flight_max_sell_through: float = Field(0.99, ge=0.0, le=1.0, description="Upper bound for elasticity-adjusted flight sell-through")
    flight_salvage_rate_default: float = Field(0.00, ge=0.0, le=1.0, description="Default 0% spoilage salvage recovery rate")
    flight_salvage_rate_optional: float = Field(0.10, ge=0.0, le=1.0, description="Optional 10% contractual salvage recovery rate")
    flight_unsold_penalty: float = Field(0.0, ge=0.0, description="Penalty fee per unsold flight seat")
    flight_price_elasticity: float = Field(1.5, ge=0.1, le=5.0, description="Price elasticity exponent when price exceeds ceiling")

    # Currency conversion assumptions
    prototype_eur_to_inr_rate: float = Field(90.0, gt=0.0, description="Prototype EUR to INR conversion rate for ADR scaling")

    # Demand funnel assumptions
    demand_scenario_multiplier: float = Field(1.0, gt=0.0, description="Demand scenario stress testing multiplier")
    default_search_conversion_rate: float = Field(0.15, ge=0.0, le=1.0, description="Fallback search-to-booking conversion rate")
    default_travellers_per_booking: float = Field(2.0, ge=1.0, description="Fallback average travellers count per booking")
    default_rooms_per_booking: float = Field(1.0, ge=1.0, description="Fallback average rooms count per booking")

    @model_validator(mode="after")
    def validate_flight_sell_through_bounds(self) -> FinancialAssumptions:
        if self.flight_min_sell_through > self.flight_max_sell_through:
            raise ValueError(
                f"flight_min_sell_through ({self.flight_min_sell_through}) cannot exceed "
                f"flight_max_sell_through ({self.flight_max_sell_through})"
            )
        return self


class RiskConfig(BaseModel):
    """Risk constraints and Bayesian shrinkage weights."""
    enable_destination_concentration: bool = Field(True, description="Enforce maximum spend limit per destination")
    destination_exposure_limit: float = Field(0.25, gt=0.0, le=1.0, description="Max fraction of total budget per destination")

    enable_supplier_concentration: bool = Field(True, description="Enforce maximum spend limit per supplier")
    supplier_concentration_limit: float = Field(0.20, gt=0.0, le=1.0, description="Max fraction of total budget per supplier")

    bayesian_shrinkage_lambda: float = Field(0.70, ge=0.0, le=1.0, description="Weight on ML prediction vs destination prior")
    hotel_default_cancellation_prior: float = Field(0.25, ge=0.0, le=1.0, description="Default uninformative cancellation prior")

    min_cancellation_prob: float = Field(0.01, ge=0.0, le=1.0, description="Lower clipping bound on cancellation probability")
    max_cancellation_prob: float = Field(0.99, ge=0.0, le=1.0, description="Upper clipping bound on cancellation probability")

    @model_validator(mode="after")
    def validate_cancellation_probability_bounds(self) -> RiskConfig:
        if self.min_cancellation_prob > self.max_cancellation_prob:
            raise ValueError(
                f"min_cancellation_prob ({self.min_cancellation_prob}) cannot exceed "
                f"max_cancellation_prob ({self.max_cancellation_prob})"
            )
        return self


class SolverConfig(BaseModel):
    """MILP Solver configuration."""
    backend: SolverBackend = Field(SolverBackend.SCIP, description="Primary OR-Tools solver backend")
    time_limit_seconds: float = Field(60.0, gt=0.0, description="Solver execution time limit in seconds")
    relative_gap_tolerance: float = Field(1e-4, ge=0.0, description="MIP relative optimality gap tolerance")
    fallback_backend: Optional[SolverBackend] = Field(SolverBackend.CBC, description="First fallback backend if primary unavailable")
    fallback_order: List[SolverBackend] = Field(
        default_factory=lambda: [SolverBackend.SCIP, SolverBackend.CBC, SolverBackend.HIGHS, SolverBackend.SAT],
        description="Ordered sequence of solver backends to try"
    )
    enable_logging: bool = Field(False, description="Enable OR-Tools verbose terminal solver logs")


class OptimizationConfig(BaseModel):
    """Master configuration for an optimization execution run."""
    run_id: str = Field(..., description="Unique run identifier")
    optimization_timestamp: str = Field("2026-06-01", description="Point-in-time cutoff date YYYY-MM-DD")
    total_budget: float = Field(250000.0, ge=0.0, description="Total procurement budget in currency units")
    
    # Category budgets (None means unconstrained dynamic allocation up to total_budget)
    hotel_budget_max: Optional[float] = Field(None, ge=0.0, description="Upper spend limit for hotel inventory")
    flight_budget_max: Optional[float] = Field(None, ge=0.0, description="Upper spend limit for flight inventory")
    hotel_budget_min: float = Field(0.0, ge=0.0, description="Minimum spend requirement for hotel inventory")
    flight_budget_min: float = Field(0.0, ge=0.0, description="Minimum spend requirement for flight inventory")

    # Currency controls
    target_currency: str = Field("INR", description="Operational currency for procurement")
    verified_currencies: Set[str] = Field(
        default_factory=lambda: {"EUR", "USD", "GBP"},
        description="Currencies recognized as verified corporate bank settlements"
    )
    allow_prototype_currency_override: bool = Field(
        True,
        description="Allows unverified synthetic prototype currency (INR) for development/testing"
    )

    # Sub-configurations
    financial: FinancialAssumptions = Field(default_factory=FinancialAssumptions)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    solver: SolverConfig = Field(default_factory=SolverConfig)

    # Flight salvage scenario selection
    use_flight_salvage_optional: bool = Field(
        False,
        description="False: baseline strict spoilage 0% salvage. True: optional contractual 10% salvage."
    )

    # Prediction & Demand overrides
    demand_history_window_days: int = Field(30, gt=0, description="Days of historical search volume to analyze")
    demand_forecast_horizon_days: float = Field(7.0, gt=0.0, description="Days in future demand forecast horizon")
    default_search_volume: float = Field(10.0, ge=0.0, description="Default 7-day search volume when missing")
    default_available_inventory: float = Field(10.0, ge=0.0, description="Default available inventory units fallback")

    # Sensitivity analysis defaults
    sensitivity_budget_levels: List[float] = Field(
        default_factory=lambda: [50000.0, 100000.0, 250000.0, 500000.0, 1000000.0],
        description="Parametric budget levels for sensitivity sweep"
    )
    sensitivity_supplier_limits: List[float] = Field(
        default_factory=lambda: [0.10, 0.20, 0.35, 0.50, 1.0],
        description="Parametric supplier concentration limits for sensitivity sweep"
    )

    # Data paths override
    data_paths: Optional[Dict[str, str]] = Field(None, description="Optional custom dataset file paths override")
    models_base_dir: str = Field("data/models", description="Base directory containing Phase 4 ML model artifacts")

    def get_fingerprint(self) -> str:
        """Computes deterministic SHA-256 fingerprint of the configuration."""
        data_str = json.dumps(self.model_dump(), sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_budget_consistency(self) -> OptimizationConfig:
        # 1. Category min cannot exceed category max
        if self.hotel_budget_max is not None and self.hotel_budget_min > self.hotel_budget_max:
            raise ValueError(
                f"hotel_budget_min ({self.hotel_budget_min}) cannot exceed "
                f"hotel_budget_max ({self.hotel_budget_max})"
            )
        if self.flight_budget_max is not None and self.flight_budget_min > self.flight_budget_max:
            raise ValueError(
                f"flight_budget_min ({self.flight_budget_min}) cannot exceed "
                f"flight_budget_max ({self.flight_budget_max})"
            )

        # 2. Category max cannot exceed total budget
        if self.hotel_budget_max is not None and self.hotel_budget_max > self.total_budget:
            raise ValueError(
                f"hotel_budget_max ({self.hotel_budget_max}) cannot exceed total_budget ({self.total_budget})"
            )
        if self.flight_budget_max is not None and self.flight_budget_max > self.total_budget:
            raise ValueError(
                f"flight_budget_max ({self.flight_budget_max}) cannot exceed total_budget ({self.total_budget})"
            )

        # 3. Sum of category minimums cannot exceed total budget
        if (self.hotel_budget_min + self.flight_budget_min) > self.total_budget:
            raise ValueError(
                f"Sum of category minimum budgets ({self.hotel_budget_min + self.flight_budget_min}) "
                f"cannot exceed total_budget ({self.total_budget})"
            )

        return self
