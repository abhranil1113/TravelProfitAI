"""
optimization/solvers/flight_optimizer.py

Flight-only Mixed Integer Linear Programming (MILP) procurement model.
Optimizes seat procurement subject to budget, MOQ, capacity, route/destination demand,
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


class FlightProcurementOptimizer(BaseProcurementOptimizer):
    """Dedicated optimizer for flight seat procurement."""

    def __init__(self):
        super().__init__(name="FlightProcurementOptimizer")

    def solve(
        self,
        candidates: List[CandidateOffer],
        config: OptimizationConfig
    ) -> SolverResult:
        flight_candidates = [c for c in candidates if c.inventory_type == "FLIGHT"]
        effective_budget = config.flight_budget_max if config.flight_budget_max is not None else config.total_budget

        if not flight_candidates or effective_budget <= 0.0:
            logger.info("No eligible flight candidates or zero budget provided.")
            return self._create_empty_result(
                solver_name=self.name,
                total_budget=effective_budget
            )

        solver = SolverFactory.create_solver(config.solver, problem_name="Flight_Procurement_MILP")
        start_time = time.perf_counter()

        q_vars: Dict[str, pywraplp.Variable] = {}
        y_vars: Dict[str, pywraplp.Variable] = {}
        cand_map: Dict[str, CandidateOffer] = {}

        # 1. Decision Variables
        # q_j: Integer quantity of flight seats
        # y_j: Binary selection indicator
        for c in flight_candidates:
            cand_map[c.opportunity_id] = c
            q_vars[c.opportunity_id] = solver.IntVar(
                0, int(c.available_qty), f"q_{c.opportunity_id}"
            )
            y_vars[c.opportunity_id] = solver.BoolVar(f"y_{c.opportunity_id}")

            # Linking Constraints: MOQ and Upper Bound
            solver.Add(q_vars[c.opportunity_id] <= int(c.available_qty) * y_vars[c.opportunity_id])
            solver.Add(q_vars[c.opportunity_id] >= int(c.moq) * y_vars[c.opportunity_id])

        # 2. Objective Function: Maximize Expected Net Contribution
        objective = solver.Objective()
        for opp_id, var in q_vars.items():
            c = cand_map[opp_id]
            objective.SetCoefficient(var, float(c.unit_contribution))
        objective.SetMaximization()

        # 3. Budget Constraint
        budget_constraint = solver.Constraint(0.0, float(effective_budget), "flight_budget")
        for opp_id, var in q_vars.items():
            budget_constraint.SetCoefficient(var, float(cand_map[opp_id].unit_cost))

        # 4. Destination / Market Demand Absorption Limits
        dest_opps: Dict[str, List[str]] = defaultdict(list)
        dest_caps: Dict[str, Optional[int]] = {}
        for c in flight_candidates:
            dest_opps[c.destination_id].append(c.opportunity_id)
            if c.destination_id not in dest_caps:
                dest_caps[c.destination_id] = c.aggregate_demand
            else:
                curr_cap = dest_caps[c.destination_id]
                if curr_cap is None or c.aggregate_demand is None:
                    dest_caps[c.destination_id] = None
                else:
                    dest_caps[c.destination_id] = max(curr_cap, c.aggregate_demand)

        for dest_id, opp_ids in dest_opps.items():
            cap = dest_caps[dest_id]
            if cap is None or cap == 0:
                # None (unavailable demand) blocks procurement; 0 forces quantity to zero
                dest_constraint = solver.Constraint(0.0, 0.0, f"flight_dest_cap_{dest_id}")
                for opp_id in opp_ids:
                    dest_constraint.SetCoefficient(q_vars[opp_id], 1.0)
            elif cap > 0:
                dest_constraint = solver.Constraint(0.0, float(cap), f"flight_dest_cap_{dest_id}")
                for opp_id in opp_ids:
                    dest_constraint.SetCoefficient(q_vars[opp_id], 1.0)

        # 5. Supplier Concentration Limit
        if config.risk.enable_supplier_concentration:
            sup_limit = config.risk.supplier_concentration_limit * effective_budget
            sup_opps: Dict[str, List[str]] = defaultdict(list)
            for c in flight_candidates:
                sup_opps[c.supplier_id].append(c.opportunity_id)

            for sup_id, opp_ids in sup_opps.items():
                sup_constraint = solver.Constraint(0.0, float(sup_limit), f"flight_sup_cap_{sup_id}")
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
            hotel_spend=0.0,
            flight_spend=float(total_spend),
            remaining_budget=float(effective_budget - total_spend)
        )
