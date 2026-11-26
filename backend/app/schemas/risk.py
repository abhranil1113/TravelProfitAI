from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.models.schema import (
    OptimizationMode,
    RiskScenarioType,
    SolverBackend,
    StressTestStatus,
)


# =============================================================================
# DOMAIN 1: ADVANCED PORTFOLIO RISK & SCENARIO ENGINE
# =============================================================================

def _validate_correlation_matrix(mat: Optional[Dict[str, Dict[str, float]]]) -> None:
    if not mat:
        return
    keys = set(mat.keys())
    for row_k, row_vals in mat.items():
        if not isinstance(row_vals, dict):
            raise ValueError(f"Correlation row '{row_k}' must be a mapping.")
        for col_k, corr in row_vals.items():
            if col_k not in keys:
                raise ValueError(f"Correlation matrix column '{col_k}' missing from row keys.")
            if not math.isfinite(corr) or corr < -1.0 or corr > 1.0:
                raise ValueError(f"Correlation ({row_k}, {col_k})={corr} must be finite and in [-1.0, 1.0].")
            if row_k == col_k and abs(corr - 1.0) > 1e-6:
                raise ValueError(f"Diagonal correlation ({row_k}, {col_k}) must equal 1.0.")
            sym = mat.get(col_k, {}).get(row_k)
            if sym is not None and abs(sym - corr) > 1e-6:
                raise ValueError(f"Correlation matrix must be symmetric: ({row_k},{col_k})={corr} != ({col_k},{row_k})={sym}.")


class RiskScenarioCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    scenario_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    scenario_type: RiskScenarioType
    probability_weight: float = Field(0.10, gt=0.0, le=1.0)
    demand_multiplier: float = Field(1.0, gt=0.0, le=5.0)
    cancellation_delta: float = Field(0.0, ge=-1.0, le=1.0)
    fx_shock_pct: float = Field(0.0, ge=-0.99, le=5.0)
    supplier_capacity_multiplier: float = Field(1.0, ge=0.0, le=2.0)
    correlation_matrix_json: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    shock_parameters_json: Dict[str, Any] = Field(default_factory=dict)
    target_dest_id: Optional[str] = Field(None, max_length=32)
    target_supplier_id: Optional[str] = Field(None, max_length=32)
    is_active: bool = True

    @field_validator("scenario_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_correlation_matrix(self) -> RiskScenarioCreateRequest:
        _validate_correlation_matrix(self.correlation_matrix_json)
        return self


class RiskScenarioUpdateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    scenario_type: Optional[RiskScenarioType] = None
    probability_weight: Optional[float] = Field(None, gt=0.0, le=1.0)
    demand_multiplier: Optional[float] = Field(None, gt=0.0, le=5.0)
    cancellation_delta: Optional[float] = Field(None, ge=-1.0, le=1.0)
    fx_shock_pct: Optional[float] = Field(None, ge=-0.99, le=5.0)
    supplier_capacity_multiplier: Optional[float] = Field(None, ge=0.0, le=2.0)
    correlation_matrix_json: Optional[Dict[str, Dict[str, float]]] = None
    shock_parameters_json: Optional[Dict[str, Any]] = None
    target_dest_id: Optional[str] = Field(None, max_length=32)
    target_supplier_id: Optional[str] = Field(None, max_length=32)
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_correlation_matrix(self) -> RiskScenarioUpdateRequest:
        _validate_correlation_matrix(self.correlation_matrix_json)
        return self


class RiskScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    scenario_code: str
    name: str
    description: Optional[str] = None
    scenario_type: RiskScenarioType
    probability_weight: float
    demand_multiplier: float
    cancellation_delta: float
    fx_shock_pct: float
    supplier_capacity_multiplier: float
    correlation_matrix_json: Dict[str, Any] = Field(default_factory=dict)
    shock_parameters_json: Dict[str, Any] = Field(default_factory=dict)
    target_dest_id: Optional[str] = None
    target_supplier_id: Optional[str] = None
    is_active: bool
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class RiskScenarioListResponse(BaseModel):
    items: List[RiskScenarioResponse]
    total: int
    page: int
    page_size: int


class StressTestExecuteRequest(BaseModel):
    scenario_ids: List[int] = Field(..., min_length=1, max_length=25)
    fx_base_currency: Optional[str] = Field("INR", min_length=3, max_length=3)
    include_line_impacts: bool = True


class StressTestLineImpact(BaseModel):
    recommendation_id: int
    offer_id: str
    supplier_id: str
    dest_id: str
    baseline_profit_inr: Decimal
    stressed_profit_inr: Decimal
    effective_capacity_units: int
    fulfilled_demand_units: int


class PortfolioStressTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stress_test_uid: str
    run_id: str
    scenario_id: int
    status: StressTestStatus
    baseline_profit_inr: Decimal
    stressed_profit_inr: Decimal
    profit_delta_inr: Decimal
    profit_drawdown_pct: float
    var_95_inr: Decimal
    cvar_95_inr: Decimal
    availability_fulfillment_pct: float
    demand_fulfillment_pct: float
    line_impacts_json: List[Dict[str, Any]] = Field(default_factory=list)
    executed_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class StressTestBatchResponse(BaseModel):
    run_id: str
    tests_executed: int
    worst_case_profit_inr: Decimal
    worst_case_drawdown_pct: float
    aggregate_var_95_inr: Decimal
    aggregate_cvar_95_inr: Decimal
    results: List[PortfolioStressTestResponse]


class CVaROptimizationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    optimization_mode: OptimizationMode = OptimizationMode.JOINT
    budget_id: Optional[int] = None
    total_budget_inr: Optional[Decimal] = Field(None, gt=0)
    cutoff_date: Optional[date] = None
    solver_backend: SolverBackend = SolverBackend.HIGHS
    max_supplier_share: Decimal = Field(Decimal("0.40"), gt=0, le=1)
    max_destination_share: Decimal = Field(Decimal("0.35"), gt=0, le=1)
    confidence_level_alpha: float = Field(0.95, gt=0.5, lt=1.0)
    risk_aversion_lambda: float = Field(0.50, ge=0.0, le=1.0)
    scenario_ids: List[int] = Field(..., min_length=2, max_length=50)
    min_availability_target_pct: float = Field(80.0, ge=0.0, le=100.0)
    min_demand_fulfillment_pct: float = Field(75.0, ge=0.0, le=100.0)
    scenario_name: Optional[str] = Field(None, max_length=100)
    idempotency_key: Optional[str] = Field(None, max_length=128)

    @field_validator("scenario_ids")
    @classmethod
    def validate_distinct_scenarios(cls, v: List[int]) -> List[int]:
        if len(set(v)) < 2:
            raise ValueError("At least 2 distinct scenario_ids are required for CVaR optimization.")
        return v


class CVaROptimizationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    confidence_level_alpha: float
    risk_aversion_lambda: float
    num_scenarios: int
    min_availability_target_pct: float
    min_demand_fulfillment_pct: float
    achieved_availability_pct: float
    achieved_demand_fulfillment_pct: float
    expected_profit_inr: Decimal
    var_inr: Decimal
    cvar_inr: Decimal
    risk_adjusted_profit_inr: Decimal
    scenario_outcomes_json: List[Dict[str, Any]] = Field(default_factory=list)
    scenario_ids_json: List[int] = Field(default_factory=list)
    created_at: datetime


class PortfolioRiskSummaryResponse(BaseModel):
    run_id: Optional[str] = None
    evaluated_runs_count: int
    total_committed_spend_inr: Decimal
    expected_profit_inr: Decimal
    portfolio_var_95_inr: Decimal
    portfolio_cvar_95_inr: Decimal
    avg_availability_fulfillment_pct: float
    avg_demand_fulfillment_pct: float
    supplier_hhi: float
    destination_hhi: float
    active_scenarios_count: int
    stress_tests_count: int
    risk_grade: str


class RiskAdjustedComparisonItem(BaseModel):
    run_id: str
    optimization_mode: OptimizationMode
    scenario_name: Optional[str] = None
    total_spend_inr: Decimal
    expected_profit_inr: Decimal
    var_95_inr: Decimal
    cvar_95_inr: Decimal
    risk_adjusted_profit_inr: Decimal
    sharpe_like_ratio: float
    availability_fulfillment_pct: float
    demand_fulfillment_pct: float


class RiskAdjustedComparisonResponse(BaseModel):
    baseline_run_id: str
    compared_runs: List[RiskAdjustedComparisonItem]
    recommended_run_id: str
    rationale: str
