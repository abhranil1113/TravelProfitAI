"""
optimization/solvers/joint_optimizer.py

Unified Joint Mixed Integer Linear Programming (MILP) procurement model.
Optimizes both hotel room nights and flight seats simultaneously under a single shared budget,
category min/max spend allocations, segregated physical demand caps, MOQ, capacity,
and portfolio supplier concentration limits.
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


class JointProcurementOptimizer(BaseProcurementOptimizer):
    """
    Unified multi-product MILP solver optimizing portfolio allocation across
    hotel and flight inventories simultaneously.
    """

    def __init__(self):
        super().__init__(name="JointProcurementOptimizer")

    def solve(
        self,
        candidates: List[CandidateOffer],
        config: OptimizationConfig
    ) -> SolverResult:
        if not candidates or config.total_budget <= 0.0:
            logger.info("No candidates or zero total budget provided.")
            return self._create_empty_result(
                solver_name=self.name,
                total_budget=config.total_budget
            )

        solver = SolverFactory.create_solver(config.solver, problem_name="Joint_Procurement_MILP")
        start_time = time.perf_counter()

        q_vars: Dict[str, pywraplp.Variable] = {}
        y_vars: Dict[str, pywraplp.Variable] = {}
        cand_map: Dict[str, CandidateOffer] = {}

        # 1. Decision Variables
        # q_k: Integer quantity of units (ROOM_NIGHT for hotels, SEAT for flights)
        # y_k: Binary selection indicator
        for c in candidates:
            cand_map[c.opportunity_id] = c
            q_vars[c.opportunity_id] = solver.IntVar(
                0, int(c.available_qty), f"q_{c.opportunity_id}"
            )
            y_vars[c.opportunity_id] = solver.BoolVar(f"y_{c.opportunity_id}")

            # Linking Constraints: MOQ and Upper Bound
            # q_k <= Q_k^max * y_k
            solver.Add(q_vars[c.opportunity_id] <= int(c.available_qty) * y_vars[c.opportunity_id])
            # q_k >= Q_k^min * y_k
            solver.Add(q_vars[c.opportunity_id] >= int(c.moq) * y_vars[c.opportunity_id])

        # 2. Objective Function: Maximize Total Expected Net Contribution
        # Maximize sum_{i in Hotel} e_i * q_i + sum_{j in Flight} e_j * q_j
        objective = solver.Objective()
        for opp_id, var in q_vars.items():
            c = cand_map[opp_id]
            objective.SetCoefficient(var, float(c.unit_contribution))
        objective.SetMaximization()

        # 3. Master Shared Budget Constraint
        # sum_{k} c_k * q_k <= B_total
        total_budget_constraint = solver.Constraint(0.0, float(config.total_budget), "master_shared_budget")
        for opp_id, var in q_vars.items():
            total_budget_constraint.SetCoefficient(var, float(cand_map[opp_id].unit_cost))

        # 4. Category-Specific Budget Constraints
        hotel_opps = [c.opportunity_id for c in candidates if c.inventory_type == "HOTEL"]
        flight_opps = [c.opportunity_id for c in candidates if c.inventory_type == "FLIGHT"]

        # Hotel category bounds
        if config.hotel_budget_max is not None or config.hotel_budget_min > 0:
            h_min = float(config.hotel_budget_min)
            h_max = float(config.hotel_budget_max) if config.hotel_budget_max is not None else float(config.total_budget)
            h_constraint = solver.Constraint(h_min, h_max, "hotel_category_budget")
            for opp_id in hotel_opps:
                h_constraint.SetCoefficient(q_vars[opp_id], float(cand_map[opp_id].unit_cost))

        # Flight category bounds
        if config.flight_budget_max is not None or config.flight_budget_min > 0:
            f_min = float(config.flight_budget_min)
            f_max = float(config.flight_budget_max) if config.flight_budget_max is not None else float(config.total_budget)
            f_constraint = solver.Constraint(f_min, f_max, "flight_category_budget")
            for opp_id in flight_opps:
                f_constraint.SetCoefficient(q_vars[opp_id], float(cand_map[opp_id].unit_cost))

        # 5. Segregated Destination / Market Demand Absorption Limits
        # Never pool physical room nights and seats into a common sum!
        # Hotel destination caps
        dest_hotel_opps: Dict[str, List[str]] = defaultdict(list)
        dest_hotel_caps: Dict[str, Optional[int]] = {}
        for c in candidates:
            if c.inventory_type == "HOTEL":
                dest_hotel_opps[c.destination_id].append(c.opportunity_id)
                if c.destination_id not in dest_hotel_caps:
                    dest_hotel_caps[c.destination_id] = c.aggregate_demand
                else:
                    curr_cap = dest_hotel_caps[c.destination_id]
                    if curr_cap is None or c.aggregate_demand is None:
                        dest_hotel_caps[c.destination_id] = None
                    else:
                        dest_hotel_caps[c.destination_id] = max(curr_cap, c.aggregate_demand)

        for dest_id, opp_ids in dest_hotel_opps.items():
            cap = dest_hotel_caps[dest_id]
            if cap is None or cap == 0:
                # None (unavailable demand) blocks procurement; 0 forces quantity to zero
                h_dest_c = solver.Constraint(0.0, 0.0, f"hotel_demand_cap_{dest_id}")
                for opp_id in opp_ids:
                    h_dest_c.SetCoefficient(q_vars[opp_id], 1.0)
            elif cap > 0:
                h_dest_c = solver.Constraint(0.0, float(cap), f"hotel_demand_cap_{dest_id}")
                for opp_id in opp_ids:
                    h_dest_c.SetCoefficient(q_vars[opp_id], 1.0)

        # Flight destination caps
        dest_flight_opps: Dict[str, List[str]] = defaultdict(list)
        dest_flight_caps: Dict[str, Optional[int]] = {}
        for c in candidates:
            if c.inventory_type == "FLIGHT":
                dest_flight_opps[c.destination_id].append(c.opportunity_id)
                if c.destination_id not in dest_flight_caps:
                    dest_flight_caps[c.destination_id] = c.aggregate_demand
                else:
                    curr_cap = dest_flight_caps[c.destination_id]
                    if curr_cap is None or c.aggregate_demand is None:
                        dest_flight_caps[c.destination_id] = None
                    else:
                        dest_flight_caps[c.destination_id] = max(curr_cap, c.aggregate_demand)

        for dest_id, opp_ids in dest_flight_opps.items():
            cap = dest_flight_caps[dest_id]
            if cap is None or cap == 0:
                # None (unavailable demand) blocks procurement; 0 forces quantity to zero
                f_dest_c = solver.Constraint(0.0, 0.0, f"flight_demand_cap_{dest_id}")
                for opp_id in opp_ids:
                    f_dest_c.SetCoefficient(q_vars[opp_id], 1.0)
            elif cap > 0:
                f_dest_c = solver.Constraint(0.0, float(cap), f"flight_demand_cap_{dest_id}")
                for opp_id in opp_ids:
                    f_dest_c.SetCoefficient(q_vars[opp_id], 1.0)

        # 6. Supplier Concentration Limits (Unified portfolio spend cap)
        if config.risk.enable_supplier_concentration:
            sup_limit = config.risk.supplier_concentration_limit * config.total_budget
            sup_opps: Dict[str, List[str]] = defaultdict(list)
            for c in candidates:
                sup_opps[c.supplier_id].append(c.opportunity_id)

            for sup_id, opp_ids in sup_opps.items():
                sup_c = solver.Constraint(0.0, float(sup_limit), f"joint_sup_cap_{sup_id}")
                for opp_id in opp_ids:
                    sup_c.SetCoefficient(q_vars[opp_id], float(cand_map[opp_id].unit_cost))

        # 7. Destination Concentration Limits (Total spend per destination cap)
        if config.risk.enable_destination_concentration:
            dest_limit = config.risk.destination_exposure_limit * config.total_budget
            dest_spend_opps: Dict[str, List[str]] = defaultdict(list)
            for c in candidates:
                dest_spend_opps[c.destination_id].append(c.opportunity_id)

            for dest_id, opp_ids in dest_spend_opps.items():
                dest_c = solver.Constraint(0.0, float(dest_limit), f"joint_dest_spend_cap_{dest_id}")
                for opp_id in opp_ids:
                    dest_c.SetCoefficient(q_vars[opp_id], float(cand_map[opp_id].unit_cost))

        # 8. Solve Model
        status_code = solver.Solve()
        elapsed_sec = time.perf_counter() - start_time
        status_str, is_optimal = self._translate_status(status_code)

        # 9. Extract Solution
        selected_quantities: Dict[str, int] = {}
        selected_offers: Dict[str, int] = {}
        total_spend = 0.0
        hotel_spend = 0.0
        flight_spend = 0.0

        if is_optimal or status_str == "FEASIBLE":
            for opp_id, var in q_vars.items():
                qty = int(round(var.solution_value()))
                y_val = int(round(y_vars[opp_id].solution_value()))
                if qty > 0 and y_val > 0:
                    selected_quantities[opp_id] = qty
                    selected_offers[opp_id] = 1
                    spend = qty * cand_map[opp_id].unit_cost
                    total_spend += spend
                    if cand_map[opp_id].inventory_type == "HOTEL":
                        hotel_spend += spend
                    else:
                        flight_spend += spend

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
            hotel_spend=float(hotel_spend),
            flight_spend=float(flight_spend),
            remaining_budget=float(config.total_budget - total_spend)
        )
