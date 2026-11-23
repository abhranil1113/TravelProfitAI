"""
optimization/evaluation/sensitivity.py

Parametric sensitivity analysis framework for procurement optimization.
Executes systematic sweeps over:
- Total procurement budget (scaling from conservative to aggressive)
- Sell-through probability expectations
- Flight salvage recovery regimes (0% baseline vs 10% contractual)
- Supplier concentration limits
"""

from typing import List, Dict, Any
from pydantic import BaseModel

from optimization.config import OptimizationConfig
from optimization.schemas import CandidateOffer
from optimization.solvers.joint_optimizer import JointProcurementOptimizer


class SensitivityScenarioResult(BaseModel):
    scenario_name: str
    parameter_name: str
    parameter_value: Any
    total_budget: float
    total_spend: float
    budget_utilization_pct: float
    expected_profit: float
    return_on_spend: float
    hotel_spend: float
    flight_spend: float
    hotel_units: int
    flight_units: int
    selected_offers_count: int


class SensitivityAnalyzer:
    """Performs parametric sensitivity sweeps using pre-computed candidate pools."""

    @staticmethod
    def sweep_budget(
        candidates: List[CandidateOffer],
        base_config: OptimizationConfig,
        budget_levels: List[float] = [50000.0, 100000.0, 250000.0, 500000.0, 1000000.0]
    ) -> List[SensitivityScenarioResult]:
        results = []
        optimizer = JointProcurementOptimizer()

        for b in budget_levels:
            cfg = base_config.model_copy(update={"total_budget": b, "hotel_budget_max": None, "flight_budget_max": None})
            sol = optimizer.solve(candidates, cfg)

            cand_map = {c.opportunity_id: c for c in candidates}
            h_units = sum(qty for opp, qty in sol.selected_quantities.items() if cand_map[opp].inventory_type == "HOTEL")
            f_units = sum(qty for opp, qty in sol.selected_quantities.items() if cand_map[opp].inventory_type == "FLIGHT")
            util = (sol.total_spend / b * 100.0) if b > 0 else 0.0
            ros = (sol.objective_value / sol.total_spend) if sol.total_spend > 0 else 0.0

            results.append(SensitivityScenarioResult(
                scenario_name=f"Budget_₹{int(b):,}",
                parameter_name="total_budget",
                parameter_value=b,
                total_budget=b,
                total_spend=sol.total_spend,
                budget_utilization_pct=round(util, 2),
                expected_profit=round(sol.objective_value, 2),
                return_on_spend=round(ros, 4),
                hotel_spend=round(sol.hotel_spend, 2),
                flight_spend=round(sol.flight_spend, 2),
                hotel_units=h_units,
                flight_units=f_units,
                selected_offers_count=len(sol.selected_quantities)
            ))

        return results

    @staticmethod
    def sweep_supplier_concentration(
        candidates: List[CandidateOffer],
        base_config: OptimizationConfig,
        concentration_limits: List[float] = [0.10, 0.20, 0.35, 0.50, 1.0]
    ) -> List[SensitivityScenarioResult]:
        results = []
        optimizer = JointProcurementOptimizer()

        for cap in concentration_limits:
            cfg = base_config.model_copy(deep=True)
            cfg.risk.enable_supplier_concentration = (cap < 1.0)
            cfg.risk.supplier_concentration_limit = cap
            sol = optimizer.solve(candidates, cfg)

            cand_map = {c.opportunity_id: c for c in candidates}
            h_units = sum(qty for opp, qty in sol.selected_quantities.items() if cand_map[opp].inventory_type == "HOTEL")
            f_units = sum(qty for opp, qty in sol.selected_quantities.items() if cand_map[opp].inventory_type == "FLIGHT")
            util = (sol.total_spend / cfg.total_budget * 100.0) if cfg.total_budget > 0 else 0.0
            ros = (sol.objective_value / sol.total_spend) if sol.total_spend > 0 else 0.0

            results.append(SensitivityScenarioResult(
                scenario_name=f"SupplierCap_{int(cap*100)}%",
                parameter_name="supplier_concentration_limit",
                parameter_value=cap,
                total_budget=cfg.total_budget,
                total_spend=sol.total_spend,
                budget_utilization_pct=round(util, 2),
                expected_profit=round(sol.objective_value, 2),
                return_on_spend=round(ros, 4),
                hotel_spend=round(sol.hotel_spend, 2),
                flight_spend=round(sol.flight_spend, 2),
                hotel_units=h_units,
                flight_units=f_units,
                selected_offers_count=len(sol.selected_quantities)
            ))

        return results
