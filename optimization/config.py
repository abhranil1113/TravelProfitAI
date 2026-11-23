"""
optimization/config.py

Comprehensive configuration models for Phase 5 Optimization Engine.
Follows Stage 1.3 audited assumptions and strict currency validation rules.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


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
    hotel_base_sell_through: float = Field(0.85, ge=0.0, le=1.0)
    hotel_customer_refund_rate: float = Field(0.80, ge=0.0, le=1.0)
    hotel_supplier_refund_rate_cancel: float = Field(0.85, ge=0.0, le=1.0)
    hotel_supplier_refund_rate_unsold: float = Field(0.00, ge=0.0, le=1.0)
    hotel_room_resale_probability: float = Field(0.40, ge=0.0, le=1.0)
    hotel_resale_discount_factor: float = Field(0.90, ge=0.1, le=1.5)
    hotel_assumed_stay_duration: float = Field(2.0, ge=1.0, le=14.0)

    # Flight assumptions
    flight_base_sell_through: float = Field(0.85, ge=0.0, le=1.0)
    flight_salvage_rate_default: float = Field(0.00, ge=0.0, le=1.0)
    flight_salvage_rate_optional: float = Field(0.10, ge=0.0, le=1.0)
    flight_unsold_penalty: float = Field(0.0, ge=0.0)
    flight_price_elasticity: float = Field(1.5, ge=0.1, le=5.0)

    # Prototype FX scale assumption
    prototype_eur_to_inr_rate: float = Field(90.0, gt=0.0)


class RiskConfig(BaseModel):
    """Risk constraints and Bayesian shrinkage weights."""
    enable_destination_concentration: bool = Field(True)
    destination_exposure_limit: float = Field(0.25, gt=0.0, le=1.0)

    enable_supplier_concentration: bool = Field(True)
    supplier_concentration_limit: float = Field(0.20, gt=0.0, le=1.0)

    bayesian_shrinkage_lambda: float = Field(0.70, ge=0.0, le=1.0)
    hotel_default_cancellation_prior: float = Field(0.25, ge=0.0, le=1.0)


class SolverConfig(BaseModel):
    """MILP Solver configuration."""
    backend: SolverBackend = Field(SolverBackend.SCIP)
    time_limit_seconds: float = Field(60.0, gt=0.0)
    relative_gap_tolerance: float = Field(1e-4, ge=0.0)
    fallback_backend: Optional[SolverBackend] = Field(SolverBackend.CBC)
    enable_logging: bool = Field(False)


class OptimizationConfig(BaseModel):
    """Master configuration for an optimization execution run."""
    run_id: str = Field(..., description="Unique run identifier")
    optimization_timestamp: str = Field("2026-06-01", description="Point-in-time cutoff date YYYY-MM-DD")
    total_budget: float = Field(250000.0, gt=0.0, description="Total procurement budget in currency units")
    
    # Category budgets (None means unconstrained dynamic allocation up to total_budget)
    hotel_budget_max: Optional[float] = Field(None, ge=0.0)
    flight_budget_max: Optional[float] = Field(None, ge=0.0)
    hotel_budget_min: float = Field(0.0, ge=0.0)
    flight_budget_min: float = Field(0.0, ge=0.0)

    # Currency controls
    target_currency: str = Field("INR", description="Operational currency for procurement")
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

    @field_validator("hotel_budget_max")
    @classmethod
    def validate_hotel_budget(cls, v, info):
        if v is not None and "total_budget" in info.data and v > info.data["total_budget"]:
            raise ValueError("hotel_budget_max cannot exceed total_budget")
        return v

    @field_validator("flight_budget_max")
    @classmethod
    def validate_flight_budget(cls, v, info):
        if v is not None and "total_budget" in info.data and v > info.data["total_budget"]:
            raise ValueError("flight_budget_max cannot exceed total_budget")
        return v
