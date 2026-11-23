"""
optimization/solvers/hotel_optimizer.py

Hotel-only Mixed Integer Linear Programming (MILP) procurement model.
Optimizes room night procurement subject to budget, MOQ, capacity, destination demand,
and supplier concentration limits.
"""

import time
import logging
from collections import defaultdict
from typing import List, Dict
from ortools.linear_solver import pywraplp

from optimization.config import OptimizationConfig
from optimization.schemas import CandidateOffer, SolverResult
from optimization.solvers.base_solver import BaseProcurementOptimizer
from optimization.solvers.solver_factory import SolverFactory

logger = logging.getLogger(__name__)


class HotelProcurementOptimizer(BaseProcurementOptimizer):
    """Dedicated optimizer for hotel room-night procurement."""

    def __init__(self):
        super().__init__(name="HotelProcurementOptimizer")

    def solve(
        self,
        candidates: List[CandidateOffer],
        config: OptimizationConfig
    ) -> SolverResult:
        # Filter for hotel candidates
        hotel_candidates = [c for c in candidates if c.inventory_type == "HOTEL"]
        effective_budget = config.hotel_budget_max if config.hotel_budget_max is not None else config.total_budget

        if not hotel_candidates or effective_budget <= 0.0:
            logger.info("No eligible hotel candidates or zero budget provided.")
            return self._create_empty_result(
                solver_name=self.name,
                total_budget=effective_budget
            )

        solver = SolverFactory.create_solver(config.solver, problem_name="Hotel_Procurement_MILP")
        start_time = time.perf_counter()

        q_vars: Dict[str, pywraplp.Variable] = {}
        y_vars: Dict[str, pywraplp.Variable] = {}
        cand_map: Dict[str, CandidateOffer] = {}

        # 1. Decision Variables
        # q_i: Integer quantity of room nights
        # y_i: Binary selection indicator
        for c in hotel_candidates:
            cand_map[c.opportunity_id] = c
            q_vars[c.opportunity_id] = solver.IntVar(
                0, int(c.available_qty), f"q_{c.opportunity_id}"
            )
            y_vars[c.opportunity_id] = solver.BoolVar(f"y_{c.opportunity_id}")

            # Linking Constraints: MOQ and Upper Bound
            # q_i <= Q_i^max * y_i  ==>  q_i - Q_i^max * y_i <= 0
            solver.Add(q_vars[c.opportunity_id] <= int(c.available_qty) * y_vars[c.opportunity_id])
            # q_i >= Q_i^min * y_i  ==>  q_i - Q_i^min * y_i >= 0
            solver.Add(q_vars[c.opportunity_id] >= int(c.moq) * y_vars[c.opportunity_id])

        # 2. Objective Function: Maximize Expected Net Contribution
        # Maximize sum(e_i * q_i)
        objective = solver.Objective()
        for opp_id, var in q_vars.items():
            c = cand_map[opp_id]
            objective.SetCoefficient(var, float(c.unit_contribution))
        objective.SetMaximization()

        # 3. Budget Constraint
        # sum(c_i * q_i) <= B_H
        budget_constraint = solver.Constraint(0.0, float(effective_budget), "hotel_budget")
        for opp_id, var in q_vars.items():
            budget_constraint.SetCoefficient(var, float(cand_map[opp_id].unit_cost))

        # 4. Destination Demand Absorption Limits
        # For each destination, total room nights procured cannot exceed aggregate demand cap
        dest_opps: Dict[str, List[str]] = defaultdict(list)
        dest_caps: Dict[str, int] = {}
        for c in hotel_candidates:
            dest_opps[c.destination_id].append(c.opportunity_id)
            dest_caps[c.destination_id] = max(dest_caps.get(c.destination_id, 0), c.aggregate_demand)

        for dest_id, opp_ids in dest_opps.items():
            cap = dest_caps[dest_id]
            if cap > 0:
                dest_constraint = solver.Constraint(0.0, float(cap), f"dest_cap_{dest_id}")
                for opp_id in opp_ids:
                    dest_constraint.SetCoefficient(q_vars[opp_id], 1.0)

        # 5. Supplier Concentration Limit
        if config.risk.enable_supplier_concentration:
            sup_limit = config.risk.supplier_concentration_limit * effective_budget
            sup_opps: Dict[str, List[str]] = defaultdict(list)
            for c in hotel_candidates:
                sup_opps[c.supplier_id].append(c.opportunity_id)

            for sup_id, opp_ids in sup_opps.items():
                sup_constraint = solver.Constraint(0.0, float(sup_limit), f"sup_cap_{sup_id}")
                for opp_id in opp_ids:
                    sup_constraint.SetCoefficient(q_vars[opp_id], float(cand_map[opp_id].unit_cost))

        # 6. Solve Model
        status_code = solver.Solve()
        elapsed_sec = time.perf_counter() - start_time
        status_str, is_optimal = self._translate_status(status_code)

        # 7. Extract Solution
        selected_quantities: Dict[str, int] = {}
        selected_offers: Dict[str, int] = {}
        total_spend = 0.0

        if is_optimal or status_str == "FEASIBLE":
            for opp_id, var in q_vars.items():
                qty = int(round(var.solution_value()))
                y_val = int(round(y_vars[opp_id].solution_value()))
                if qty > 0 and y_val > 0:
                    selected_quantities[opp_id] = qty
                    selected_offers[opp_id] = 1
                    total_spend += qty * cand_map[opp_id].unit_cost

        obj_val = solver.Objective().Value() if (is_optimal or status_str == "FEASIBLE") else 0.0
        best_bound = solver.Objective().BestBound() if (is_optimal or status_str == "FEASIBLE") else 0.0
        gap = abs(best_bound - obj_val) / (abs(obj_val) + 1e-9) if obj_val != 0 else 0.0

        return SolverResult(
            status=status_str,
            is_proven_optimal=is_optimal,
            objective_value=float(obj_val),
            best_bound=float(best_bound),
            optimality_gap=float(gap),
            execution_time_seconds=float(elapsed_sec),
            solver_name=self.name,
            num_variables=solver.NumVariables(),
            num_constraints=solver.NumConstraints(),
            selected_quantities=selected_quantities,
            selected_offers=selected_offers,
            total_spend=float(total_spend),
            hotel_spend=float(total_spend),
            flight_spend=0.0,
            remaining_budget=float(effective_budget - total_spend)
        )
