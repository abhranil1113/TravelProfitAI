"""
optimization/schemas.py

Typed data schemas for procurement opportunities, solver results,
evaluation metrics, and actionable recommendations.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ProcurementOpportunity(BaseModel):
    """Normalized internal procurement opportunity schema."""
    opportunity_id: str
    offer_id: str
    supplier_id: str
    inventory_type: str  # 'HOTEL' or 'FLIGHT'
    inventory_id: str
    origin_id: Optional[str] = None
    destination_id: str
    travel_date: str
    purchase_cost: float
    selling_price: float
    available_quantity: int
    minimum_purchase_qty: int
    refundable: bool
    offer_valid_until: str
    currency: str
    unit_type: str  # 'ROOM_NIGHT' or 'SEAT'

    # Point-in-time inventory capacity
    point_in_time_capacity: int

    # Inferred ML predictions & market ceilings
    predicted_cancellation_prob: Optional[float] = None
    predicted_market_price: Optional[float] = None
    predicted_search_volume: Optional[float] = None
    predicted_inventory_depletion: Optional[float] = None

    # Economic parameters
    sell_through_probability: float
    expected_unit_contribution: float
    expected_unit_revenue: float

    # Aggregate destination demand cap
    aggregate_demand_cap: int


class CandidateOffer(BaseModel):
    """Lightweight representation of an offer passed into the MILP model builder."""
    index: int
    opportunity_id: str
    offer_id: str
    supplier_id: str
    inventory_type: str
    inventory_id: str
    destination_id: str
    travel_date: str
    unit_cost: float
    unit_selling_price: float
    available_qty: int
    moq: int
    unit_contribution: float
    unit_type: str
    aggregate_demand: int


class SolverTerminationStatus(str):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    ABNORMAL = "ABNORMAL"
    NOT_SOLVED = "NOT_SOLVED"
    TIMEOUT = "TIMEOUT"


class SolverResult(BaseModel):
    """Standardized output from any MILP optimizer backend."""
    status: str
    is_proven_optimal: bool
    objective_value: float
    best_bound: Optional[float] = None
    optimality_gap: Optional[float] = None
    execution_time_seconds: float
    solver_name: str
    num_variables: int
    num_constraints: int
    selected_quantities: Dict[str, int]  # opportunity_id -> quantity
    selected_offers: Dict[str, int]      # opportunity_id -> 1/0
    total_spend: float
    hotel_spend: float
    flight_spend: float
    remaining_budget: float


class EvaluationMetrics(BaseModel):
    """Commercial, operational, and algorithmic evaluation scorecard."""
    run_id: str
    optimization_timestamp: str
    solver_status: str
    is_proven_optimal: bool
    execution_time_sec: float
    total_budget: float
    total_spend: float
    budget_utilization_pct: float
    remaining_budget: float
    expected_net_profit: float
    return_on_procurement_spend: float  # (profit / spend)
    
    # Portfolio breakdown
    hotel_spend: float
    flight_spend: float
    hotel_room_nights_procured: int
    flight_seats_procured: int
    total_units_procured: int
    
    # Counts
    total_eligible_opportunities: int
    selected_opportunities_count: int
    rejected_opportunities_count: int
    selected_suppliers_count: int
    
    # Risk and exposure metrics
    max_single_supplier_spend: float
    max_supplier_concentration_pct: float
    max_single_destination_spend: float
    max_destination_exposure_pct: float
    
    # Comparisons vs baselines
    profit_lift_vs_greedy_margin: Optional[float] = None
    profit_lift_vs_greedy_contribution: Optional[float] = None


class RecommendationRecord(BaseModel):
    """Detailed explainable recommendation record for procurement staff."""
    recommendation_id: str
    run_id: str
    opportunity_id: str
    offer_id: str
    supplier_id: str
    inventory_type: str
    inventory_id: str
    destination_id: str
    origin_id: Optional[str] = None
    travel_date: str
    procurement_quantity: int
    unit_type: str
    unit_purchase_cost: float
    total_procurement_cost: float
    unit_selling_price: float
    expected_unit_contribution: float
    expected_total_net_profit: float
    expected_sell_through: float
    expected_cancellation_prob: Optional[float] = None
    currency: str
    selection_status: str  # 'SELECTED'
    selection_rationale: str


class RejectedOpportunityRecord(BaseModel):
    """Detailed diagnostic record for unselected offers."""
    opportunity_id: str
    offer_id: str
    supplier_id: str
    inventory_type: str
    inventory_id: str
    destination_id: str
    travel_date: str
    unit_purchase_cost: float
    expected_unit_contribution: float
    moq: int
    available_qty: int
    rejection_primary_reason: str
    rejection_explanation: str


class OptimizationPlan(BaseModel):
    """Complete serialized procurement recommendation package."""
    run_id: str
    optimization_timestamp: str
    config_summary: Dict[str, Any]
    evaluation_metrics: EvaluationMetrics
    recommendations: List[RecommendationRecord]
    rejected_opportunities: List[RejectedOpportunityRecord]
    solver_metadata: Dict[str, Any]
