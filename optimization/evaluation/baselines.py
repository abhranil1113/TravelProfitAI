"""
optimization/evaluation/baselines.py

Heuristic baseline algorithms for comparative benchmarking against MILP optimization.
Implements:
1. No-Procurement Baseline (Zero spend, zero profit)
2. Greedy Gross Margin Baseline (Ranks by raw (p - c)/c, evaluated under true expected economics)
3. Greedy Expected Contribution Baseline (Ranks by e / c, evaluated under true expected economics)
"""

from typing import List, Dict, Any
from pydantic import BaseModel

from optimization.config import OptimizationConfig
from optimization.schemas import CandidateOffer, SolverResult


class BaselineComparisonResult(BaseModel):
    name: str
    description: str
    total_spend: float
    expected_profit: float
    return_on_spend: float
    units_procured: int
    offers_selected: int
    profit_lift_pct_vs_no_procurement: float
    profit_lift_pct_vs_greedy_margin: float


class BaselineEvaluator:
    """Evaluates heuristic procurement strategies against identical candidate sets."""

    @staticmethod
    def evaluate_no_procurement(candidates: List[CandidateOffer], budget: float) -> Dict[str, Any]:
        return {
            "name": "No Procurement",
            "description": "Procure nothing; zero spend, zero risk, zero expected return.",
            "total_spend": 0.0,
            "expected_profit": 0.0,
            "return_on_spend": 0.0,
            "units_procured": 0,
            "offers_selected": 0,
            "selected_quantities": {}
        }

    @staticmethod
    def evaluate_greedy_gross_margin(
        candidates: List[CandidateOffer],
        config: OptimizationConfig
    ) -> Dict[str, Any]:
        """
        Greedy procurement sorted descending by unadjusted gross margin ratio:
        margin_ratio = (unit_selling_price - unit_cost) / unit_cost.
        Evaluated under true expected contribution formula.
        """
        budget = config.total_budget
        # Filter for candidates with positive gross margin
        viable = [c for c in candidates if c.unit_selling_price > c.unit_cost and c.unit_cost > 0]
        # Sort descending by gross margin ratio
        sorted_cands = sorted(
            viable,
            key=lambda c: (c.unit_selling_price - c.unit_cost) / c.unit_cost,
            reverse=True
        )

        remaining_budget = budget
        selected_quantities: Dict[str, int] = {}
        total_spend = 0.0
        expected_profit = 0.0
        total_units = 0

        for c in sorted_cands:
            if remaining_budget <= 0:
                break
            # Can we afford at least MOQ?
            moq_cost = c.moq * c.unit_cost
            if moq_cost > remaining_budget:
                continue

            # Buy as many units as possible up to available_qty
            max_affordable = int(remaining_budget // c.unit_cost)
            buy_qty = min(c.available_qty, max_affordable)

            if buy_qty >= c.moq:
                selected_quantities[c.opportunity_id] = buy_qty
                spend = buy_qty * c.unit_cost
                profit = buy_qty * c.unit_contribution
                total_spend += spend
                expected_profit += profit
                total_units += buy_qty
                remaining_budget -= spend

        ros = (expected_profit / total_spend) if total_spend > 0 else 0.0
        return {
            "name": "Greedy Gross Margin",
            "description": "Ranks offers by unadjusted commercial margin ratio without considering cancellation or sell-through risk.",
            "total_spend": float(round(total_spend, 2)),
            "expected_profit": float(round(expected_profit, 2)),
            "return_on_spend": float(round(ros, 4)),
            "units_procured": total_units,
            "offers_selected": len(selected_quantities),
            "selected_quantities": selected_quantities
        }

    @staticmethod
    def evaluate_greedy_expected_contribution(
        candidates: List[CandidateOffer],
        config: OptimizationConfig
    ) -> Dict[str, Any]:
        """
        Greedy procurement sorted descending by expected contribution per unit cost:
        roi = unit_contribution / unit_cost.
        Only considers opportunities with positive expected contribution.
        """
        budget = config.total_budget
        viable = [c for c in candidates if c.unit_contribution > 0 and c.unit_cost > 0]
        sorted_cands = sorted(
            viable,
            key=lambda c: c.unit_contribution / c.unit_cost,
            reverse=True
        )

        remaining_budget = budget
        selected_quantities: Dict[str, int] = {}
        total_spend = 0.0
        expected_profit = 0.0
        total_units = 0

        for c in sorted_cands:
            if remaining_budget <= 0:
                break
            moq_cost = c.moq * c.unit_cost
            if moq_cost > remaining_budget:
                continue

            max_affordable = int(remaining_budget // c.unit_cost)
            buy_qty = min(c.available_qty, max_affordable)

            if buy_qty >= c.moq:
                selected_quantities[c.opportunity_id] = buy_qty
                spend = buy_qty * c.unit_cost
                profit = buy_qty * c.unit_contribution
                total_spend += spend
                expected_profit += profit
                total_units += buy_qty
                remaining_budget -= spend

        ros = (expected_profit / total_spend) if total_spend > 0 else 0.0
        return {
            "name": "Greedy Expected Contribution",
            "description": "Ranks offers by expected contribution per spend (e/c) using audited ML risk predictions.",
            "total_spend": float(round(total_spend, 2)),
            "expected_profit": float(round(expected_profit, 2)),
            "return_on_spend": float(round(ros, 4)),
            "units_procured": total_units,
            "offers_selected": len(selected_quantities),
            "selected_quantities": selected_quantities
        }

    @classmethod
    def compare_all(
        cls,
        candidates: List[CandidateOffer],
        solver_result: SolverResult,
        config: OptimizationConfig
    ) -> List[BaselineComparisonResult]:
        """Runs all baselines and compares against the MILP solver result."""
        no_proc = cls.evaluate_no_procurement(candidates, config.total_budget)
        greedy_margin = cls.evaluate_greedy_gross_margin(candidates, config)
        greedy_contrib = cls.evaluate_greedy_expected_contribution(candidates, config)

        results = []
        gm_profit = greedy_margin["expected_profit"]

        # 1. No procurement
        results.append(BaselineComparisonResult(
            name=no_proc["name"],
            description=no_proc["description"],
            total_spend=0.0,
            expected_profit=0.0,
            return_on_spend=0.0,
            units_procured=0,
            offers_selected=0,
            profit_lift_pct_vs_no_procurement=0.0,
            profit_lift_pct_vs_greedy_margin=0.0
        ))

        # 2. Greedy Gross Margin
        results.append(BaselineComparisonResult(
            name=greedy_margin["name"],
            description=greedy_margin["description"],
            total_spend=greedy_margin["total_spend"],
            expected_profit=greedy_margin["expected_profit"],
            return_on_spend=greedy_margin["return_on_spend"],
            units_procured=greedy_margin["units_procured"],
            offers_selected=greedy_margin["offers_selected"],
            profit_lift_pct_vs_no_procurement=100.0 if gm_profit > 0 else 0.0,
            profit_lift_pct_vs_greedy_margin=0.0
        ))

        # 3. Greedy Expected Contribution
        gc_profit = greedy_contrib["expected_profit"]
        gc_lift = ((gc_profit - gm_profit) / abs(gm_profit) * 100.0) if gm_profit != 0 else 0.0
        results.append(BaselineComparisonResult(
            name=greedy_contrib["name"],
            description=greedy_contrib["description"],
            total_spend=greedy_contrib["total_spend"],
            expected_profit=greedy_contrib["expected_profit"],
            return_on_spend=greedy_contrib["return_on_spend"],
            units_procured=greedy_contrib["units_procured"],
            offers_selected=greedy_contrib["offers_selected"],
            profit_lift_pct_vs_no_procurement=100.0 if gc_profit > 0 else 0.0,
            profit_lift_pct_vs_greedy_margin=round(gc_lift, 2)
        ))

        # 4. MILP Optimal
        milp_profit = solver_result.objective_value
        milp_lift = ((milp_profit - gm_profit) / abs(gm_profit) * 100.0) if gm_profit != 0 else 0.0
        ros = (milp_profit / solver_result.total_spend) if solver_result.total_spend > 0 else 0.0
        total_units = sum(solver_result.selected_quantities.values())

        results.append(BaselineComparisonResult(
            name="MILP Optimal (Google OR-Tools)",
            description="Optimal mathematical programming solution subject to joint budget, capacity, MOQ, demand, and risk caps.",
            total_spend=solver_result.total_spend,
            expected_profit=milp_profit,
            return_on_spend=round(ros, 4),
            units_procured=total_units,
            offers_selected=len(solver_result.selected_quantities),
            profit_lift_pct_vs_no_procurement=100.0 if milp_profit > 0 else 0.0,
            profit_lift_pct_vs_greedy_margin=round(milp_lift, 2)
        ))

        return results
