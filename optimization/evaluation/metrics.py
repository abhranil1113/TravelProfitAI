"""
optimization/evaluation/metrics.py

Calculates comprehensive commercial, operational, and algorithmic metrics
for procurement optimization solutions.
"""

from collections import defaultdict
from typing import List, Dict, Optional

from optimization.config import OptimizationConfig
from optimization.schemas import (
    ProcurementOpportunity,
    CandidateOffer,
    SolverResult,
    EvaluationMetrics
)


class MetricsCalculator:
    """Calculates standardized EvaluationMetrics from candidate opportunities and solver output."""

    @staticmethod
    def calculate_metrics(
        config: OptimizationConfig,
        candidates: List[CandidateOffer],
        solver_result: SolverResult,
        profit_lift_vs_greedy_margin: Optional[float] = None,
        profit_lift_vs_greedy_contrib: Optional[float] = None
    ) -> EvaluationMetrics:
        cand_map: Dict[str, CandidateOffer] = {c.opportunity_id: c for c in candidates}
        total_budget = config.total_budget
        total_spend = solver_result.total_spend
        remaining_budget = max(0.0, total_budget - total_spend)
        budget_util_pct = (total_spend / total_budget * 100.0) if total_budget > 0 else 0.0

        hotel_spend = 0.0
        flight_spend = 0.0
        hotel_rooms = 0
        flight_seats = 0
        total_units = 0
        expected_profit = 0.0

        supplier_spends: Dict[str, float] = defaultdict(float)
        destination_spends: Dict[str, float] = defaultdict(float)

        for opp_id, qty in solver_result.selected_quantities.items():
            if qty <= 0 or opp_id not in cand_map:
                continue
            c = cand_map[opp_id]
            spend = qty * c.unit_cost
            profit = qty * c.unit_contribution

            expected_profit += profit
            total_units += qty

            if c.inventory_type == "HOTEL":
                hotel_spend += spend
                hotel_rooms += qty
            else:
                flight_spend += spend
                flight_seats += qty

            supplier_spends[c.supplier_id] += spend
            destination_spends[c.destination_id] += spend

        return_on_spend = (expected_profit / total_spend) if total_spend > 0 else 0.0

        # Max concentrations
        max_sup_spend = max(supplier_spends.values()) if supplier_spends else 0.0
        max_sup_pct = (max_sup_spend / total_spend * 100.0) if total_spend > 0 else 0.0

        max_dest_spend = max(destination_spends.values()) if destination_spends else 0.0
        max_dest_pct = (max_dest_spend / total_spend * 100.0) if total_spend > 0 else 0.0

        selected_count = len(solver_result.selected_quantities)
        total_candidates = len(candidates)
        rejected_count = max(0, total_candidates - selected_count)

        return EvaluationMetrics(
            run_id=config.run_id,
            optimization_timestamp=config.optimization_timestamp,
            solver_status=solver_result.status,
            is_proven_optimal=solver_result.is_proven_optimal,
            execution_time_sec=solver_result.execution_time_seconds,
            total_budget=float(total_budget),
            total_spend=float(total_spend),
            budget_utilization_pct=float(round(budget_util_pct, 2)),
            remaining_budget=float(round(remaining_budget, 2)),
            expected_net_profit=float(round(expected_profit, 2)),
            return_on_procurement_spend=float(round(return_on_spend, 4)),
            hotel_spend=float(round(hotel_spend, 2)),
            flight_spend=float(round(flight_spend, 2)),
            hotel_room_nights_procured=int(hotel_rooms),
            flight_seats_procured=int(flight_seats),
            total_units_procured=int(total_units),
            total_eligible_opportunities=int(total_candidates),
            selected_opportunities_count=int(selected_count),
            rejected_opportunities_count=int(rejected_count),
            selected_suppliers_count=len(supplier_spends),
            max_single_supplier_spend=float(round(max_sup_spend, 2)),
            max_supplier_concentration_pct=float(round(max_sup_pct, 2)),
            max_single_destination_spend=float(round(max_dest_spend, 2)),
            max_destination_exposure_pct=float(round(max_dest_pct, 2)),
            profit_lift_vs_greedy_margin=profit_lift_vs_greedy_margin,
            profit_lift_vs_greedy_contribution=profit_lift_vs_greedy_contrib
        )
