from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import (
    ApprovalStatus,
    OptimizationMode,
    PipelineStatus,
    SolverBackend,
    SolverStatus,
)


class OptimizationRunTriggerRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    optimization_mode: OptimizationMode = OptimizationMode.JOINT
    budget_id: Optional[int] = None
    total_budget_inr: Optional[Decimal] = Field(None, gt=0)
    cutoff_date: Optional[date] = None
    solver_backend: SolverBackend = SolverBackend.SCIP
    salvage_assumption_pct: Decimal = Field(Decimal("0.10"), ge=0, le=1)
    max_supplier_share: Decimal = Field(Decimal("0.40"), gt=0, le=1)
    max_destination_share: Decimal = Field(Decimal("0.35"), gt=0, le=1)
    target_currency: str = Field("INR", min_length=3, max_length=3)
    allow_prototype_currency_override: bool = False
    config_profile_id: Optional[int] = None
    config_template_id: Optional[int] = None
    scenario_name: Optional[str] = Field(None, max_length=128)
    scenario_parameters: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)


class OptimizationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    run_id: str
    triggered_by_user_id: Optional[int] = None
    parent_run_id: Optional[str] = None
    optimization_mode: OptimizationMode
    comparison_group_id: Optional[str] = None
    config_profile_id: Optional[int] = None
    config_template_id: Optional[int] = None
    budget_id: Optional[int] = None
    cutoff_date: Optional[date] = None
    total_budget_inr: Decimal
    solver_backend: SolverBackend
    salvage_assumption_pct: Decimal
    max_supplier_share: Decimal
    max_destination_share: Decimal
    target_currency: str
    pipeline_status: PipelineStatus
    solver_status: Optional[SolverStatus] = None
    is_optimal: bool = False
    solve_time_seconds: Optional[Decimal] = None
    mip_gap_pct: Optional[Decimal] = None
    best_objective_inr: Optional[Decimal] = None
    total_spend_inr: Optional[Decimal] = None
    budget_utilization_pct: Optional[Decimal] = None
    expected_net_profit_inr: Optional[Decimal] = None
    return_on_spend_pct: Optional[Decimal] = None
    selected_offers_count: Optional[int] = None
    rejected_offers_count: Optional[int] = None
    hotel_spend_inr: Optional[Decimal] = None
    flight_spend_inr: Optional[Decimal] = None
    greedy_baseline_profit_inr: Optional[Decimal] = None
    profit_lift_vs_greedy_pct: Optional[Decimal] = None
    approval_status: ApprovalStatus
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OptimizationRunListResponse(BaseModel):
    items: List[OptimizationRunResponse]
    total: int
    page: int
    page_size: int


class OptimizationRunStatusResponse(BaseModel):
    run_id: str
    pipeline_status: PipelineStatus
    solver_status: Optional[SolverStatus] = None
    is_optimal: bool = False
    heartbeat_at: Optional[datetime] = None
    progress_pct: Optional[float] = None
    error_message: Optional[str] = None


class RunDecisionRequest(BaseModel):
    decision_notes: Optional[str] = Field(None, max_length=1000)


class RunCompareRequest(BaseModel):
    run_ids: List[str] = Field(..., min_length=2, max_length=10)
    comparison_name: Optional[str] = None


class RunCompareItem(BaseModel):
    run_id: str
    optimization_mode: OptimizationMode
    solver_backend: SolverBackend
    total_spend_inr: Optional[Decimal] = None
    expected_net_profit_inr: Optional[Decimal] = None
    return_on_spend_pct: Optional[Decimal] = None
    budget_utilization_pct: Optional[Decimal] = None
    selected_offers_count: Optional[int] = None
    solve_time_seconds: Optional[Decimal] = None
    is_optimal: bool = False


class RunCompareResponse(BaseModel):
    comparison_group_id: Optional[str] = None
    runs: List[RunCompareItem]


class OptimizationScorecardResponse(BaseModel):
    run_id: str
    optimization_mode: OptimizationMode
    total_spend_inr: Decimal
    expected_net_profit_inr: Decimal
    return_on_spend_pct: Decimal
    budget_utilization_pct: Decimal
    hotel_spend_inr: Decimal
    flight_spend_inr: Decimal
    hotel_units_selected: int
    flight_units_selected: int
    selected_offers_count: int
    rejected_offers_count: int
    greedy_baseline_profit_inr: Optional[Decimal] = None
    profit_lift_vs_greedy_pct: Optional[Decimal] = None
    solve_time_seconds: Optional[Decimal] = None


class BaselineComparisonResponse(BaseModel):
    run_id: str
    baselines: List[Dict[str, Any]]


class RiskMetricsResponse(BaseModel):
    run_id: str
    supplier_hhi: Optional[float] = None
    destination_hhi: Optional[float] = None
    risk_metrics_json: Optional[Dict[str, Any]] = None


class OptimizationConstraintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    constraint_type: str
    entity_id: Optional[str] = None
    threshold_value: Decimal
    threshold_unit: str
    is_binding: bool
    slack_value: Optional[Decimal] = None
    notes: Optional[str] = None


class SensitivityScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    sweep_parameter: str
    parameter_value: Decimal
    total_spend_inr: Decimal
    expected_net_profit_inr: Decimal
    return_on_spend_pct: Decimal
    selected_offers_count: int
    solver_status: SolverStatus


class SensitivityRunRequest(BaseModel):
    sweep_parameter: str = Field("total_budget_inr", description="Parameter to sweep: total_budget_inr or max_supplier_share")
    variation_pcts: List[float] = Field(default=[-0.20, -0.10, 0.0, 0.10, 0.20])


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    filename: str
    artifact_type: str
    file_size_bytes: int
    storage_path: str
    mime_type: str
    checksum_sha256: Optional[str] = None
    created_at: datetime


class GeneratePurchaseOrdersResponse(BaseModel):
    run_id: str
    purchase_orders_created: int
    total_amount_inr: Decimal
    purchase_order_numbers: List[str]
