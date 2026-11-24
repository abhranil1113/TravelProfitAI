"""
optimization/pipeline.py

Master end-to-end optimization pipeline orchestrator for TBO InventoryIQ Phase 5.
Sequences data preparation, ML inference, mathematical optimization, baseline benchmarking,
parametric sensitivity analysis, explainable recommendation generation, and persistent auditing.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, List
import pandas as pd

from optimization.config import OptimizationConfig
from optimization.schemas import (
    ProcurementOpportunity,
    CandidateOffer,
    SolverResult,
    EvaluationMetrics,
    RecommendationRecord,
    RejectedOpportunityRecord,
    OptimizationPlan
)
from optimization.data.loader import DatasetLoader
from optimization.data.candidate_builder import CandidateOpportunityBuilder
from optimization.solvers.joint_optimizer import JointProcurementOptimizer
from optimization.solvers.hotel_optimizer import HotelProcurementOptimizer
from optimization.solvers.flight_optimizer import FlightProcurementOptimizer
from optimization.evaluation.metrics import MetricsCalculator
from optimization.evaluation.baselines import BaselineEvaluator, BaselineComparisonResult
from optimization.evaluation.sensitivity import SensitivityAnalyzer, SensitivityScenarioResult
from optimization.recommendations.generator import RecommendationGenerator

logger = logging.getLogger(__name__)


class OptimizationPipeline:
    """Master orchestrator for ML-powered travel inventory procurement optimization."""

    def __init__(self, config: OptimizationConfig, base_dir: Optional[str] = None):
        self.config = config
        self.base_dir = base_dir
        loader = DatasetLoader(
            base_dir=base_dir,
            custom_paths=getattr(config, "data_paths", None)
        )
        self.candidate_builder = CandidateOpportunityBuilder(config, loader=loader)

    def run(self, output_dir: Optional[str] = "data/optimization") -> OptimizationPlan:
        """
        Executes the full end-to-end optimization workflow:
        1. Ingests data and filters by point-in-time cutoff.
        2. Applies ML predictions (cancellation risk, price elasticity, demand).
        3. Formulates and solves MILP (Hotel, Flight, or Joint).
        4. Benchmarks against heuristic baselines.
        5. Performs parametric sensitivity sweeps.
        6. Generates human-explainable procurement recommendations & rejections.
        7. Persists auditable artifacts to disk.
        """
        start_time = time.perf_counter()
        logger.info(f"Starting OptimizationPipeline execution run_id={self.config.run_id} at {self.config.optimization_timestamp}")

        # 1. Build candidate opportunities
        opportunities, candidates, audit_meta = self.candidate_builder.build_candidate_opportunities()
        logger.info(f"Generated {len(opportunities)} opportunities and {len(candidates)} candidates.")

        # 2. Select and execute mathematical solver
        # Determine mode: hotel-only, flight-only, or joint
        if self.config.flight_budget_max == 0.0:
            logger.info("Executing Hotel-only procurement optimization.")
            solver = HotelProcurementOptimizer()
        elif self.config.hotel_budget_max == 0.0:
            logger.info("Executing Flight-only procurement optimization.")
            solver = FlightProcurementOptimizer()
        else:
            logger.info("Executing Unified Joint hotel and flight procurement optimization.")
            solver = JointProcurementOptimizer()

        solver_result: SolverResult = solver.solve(candidates, self.config)
        logger.info(f"Solver completed with status={solver_result.status}, obj={solver_result.objective_value:,.2f}, spend={solver_result.total_spend:,.2f}")

        # 3. Evaluate heuristic baselines and calculate profit lift
        baseline_results: List[BaselineComparisonResult] = BaselineEvaluator.compare_all(
            candidates, solver_result, self.config
        )
        gm_lift = next((b.profit_lift_pct_vs_greedy_margin for b in baseline_results if "MILP" in b.name), 0.0)
        gc_lift = 0.0

        # 4. Calculate comprehensive evaluation metrics
        metrics: EvaluationMetrics = MetricsCalculator.calculate_metrics(
            config=self.config,
            candidates=candidates,
            solver_result=solver_result,
            profit_lift_vs_greedy_margin=gm_lift,
            profit_lift_vs_greedy_contrib=gc_lift
        )

        # 5. Perform sensitivity analysis
        budget_sensitivity = SensitivityAnalyzer.sweep_budget(candidates, self.config)
        sup_sensitivity = SensitivityAnalyzer.sweep_supplier_concentration(candidates, self.config)

        # 6. Generate explainable recommendations & structured rejections
        recommendations, rejected = RecommendationGenerator.generate(
            opportunities=opportunities,
            candidates=candidates,
            solver_result=solver_result,
            config=self.config
        )

        elapsed_total = time.perf_counter() - start_time

        # 7. Package complete OptimizationPlan
        plan = OptimizationPlan(
            run_id=self.config.run_id,
            optimization_timestamp=self.config.optimization_timestamp,
            config_summary=self.config.model_dump(),
            evaluation_metrics=metrics,
            recommendations=recommendations,
            rejected_opportunities=rejected,
            solver_metadata={
                "solver_name": solver_result.solver_name,
                "solver_status": solver_result.status,
                "is_proven_optimal": solver_result.is_proven_optimal,
                "objective_value": solver_result.objective_value,
                "best_bound": solver_result.best_bound,
                "optimality_gap": solver_result.optimality_gap,
                "execution_time_seconds": solver_result.execution_time_seconds,
                "total_pipeline_time_seconds": round(elapsed_total, 3),
                "num_variables": solver_result.num_variables,
                "num_constraints": solver_result.num_constraints,
                "config_fingerprint": self.config.get_fingerprint(),
                "baseline_benchmarks": [b.model_dump() for b in baseline_results],
                "budget_sensitivity": [s.model_dump() for s in budget_sensitivity],
                "supplier_sensitivity": [s.model_dump() for s in sup_sensitivity],
                "data_audit": audit_meta,
            }
        )

        # 8. Safely persist outputs
        if output_dir:
            self._persist_artifacts(plan, output_dir)

        return plan

    def _persist_artifacts(self, plan: OptimizationPlan, output_dir: str):
        """Saves recommendation tables, JSON summaries, and isolated run archives."""
        os.makedirs(output_dir, exist_ok=True)
        run_archive_dir = os.path.join(output_dir, "optimization_runs", plan.run_id)
        os.makedirs(run_archive_dir, exist_ok=True)

        # Convert recommendations to DataFrame
        rec_data = [r.model_dump() for r in plan.recommendations]
        rec_df = pd.DataFrame(rec_data) if rec_data else pd.DataFrame(columns=[
            "recommendation_id", "opportunity_id", "offer_id", "supplier_id", "inventory_type",
            "destination_id", "travel_date", "procurement_quantity", "unit_purchase_cost",
            "total_procurement_cost", "expected_unit_contribution", "expected_total_net_profit",
            "expected_sell_through", "currency", "selection_status", "selection_rationale"
        ])

        # Convert rejected opportunities to DataFrame
        rej_data = [r.model_dump() for r in plan.rejected_opportunities]
        rej_df = pd.DataFrame(rej_data) if rej_data else pd.DataFrame(columns=[
            "opportunity_id", "offer_id", "supplier_id", "inventory_type", "destination_id",
            "travel_date", "unit_purchase_cost", "expected_unit_contribution", "moq",
            "available_qty", "rejection_primary_reason", "rejection_explanation"
        ])

        # Summary JSON dict
        summary_dict = {
            "run_id": plan.run_id,
            "optimization_timestamp": plan.optimization_timestamp,
            "config_fingerprint": self.config.get_fingerprint(),
            "currency_assumptions": {
                "target_currency": self.config.target_currency,
                "verified_currencies": sorted(list(self.config.verified_currencies)),
                "allow_prototype_currency_override": self.config.allow_prototype_currency_override,
            },
            "financial_assumptions": self.config.financial.model_dump(),
            "risk_assumptions": self.config.risk.model_dump(),
            "solver_settings": self.config.solver.model_dump(),
            "solver_status": plan.evaluation_metrics.solver_status,
            "is_proven_optimal": plan.evaluation_metrics.is_proven_optimal,
            "total_budget": plan.evaluation_metrics.total_budget,
            "total_spend": plan.evaluation_metrics.total_spend,
            "budget_utilization_pct": plan.evaluation_metrics.budget_utilization_pct,
            "expected_net_profit": plan.evaluation_metrics.expected_net_profit,
            "return_on_procurement_spend": plan.evaluation_metrics.return_on_procurement_spend,
            "hotel_spend": plan.evaluation_metrics.hotel_spend,
            "flight_spend": plan.evaluation_metrics.flight_spend,
            "hotel_room_nights_procured": plan.evaluation_metrics.hotel_room_nights_procured,
            "flight_seats_procured": plan.evaluation_metrics.flight_seats_procured,
            "total_units_procured": plan.evaluation_metrics.total_units_procured,
            "selected_opportunities_count": plan.evaluation_metrics.selected_opportunities_count,
            "rejected_opportunities_count": plan.evaluation_metrics.rejected_opportunities_count,
            "selected_suppliers_count": plan.evaluation_metrics.selected_suppliers_count,
            "max_supplier_concentration_pct": plan.evaluation_metrics.max_supplier_concentration_pct,
            "max_destination_exposure_pct": plan.evaluation_metrics.max_destination_exposure_pct,
            "profit_lift_vs_greedy_margin": plan.evaluation_metrics.profit_lift_vs_greedy_margin,
            "solver_metadata": plan.solver_metadata,
        }

        # 1. Canonical latest files
        rec_csv_path = os.path.join(output_dir, "procurement_recommendations.csv")
        rej_csv_path = os.path.join(output_dir, "rejected_opportunities.csv")
        summary_json_path = os.path.join(output_dir, "optimization_summary.json")

        rec_df.to_csv(rec_csv_path, index=False)
        rej_df.to_csv(rej_csv_path, index=False)
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary_dict, f, indent=2)

        # 2. Run-specific isolated archive files
        rec_df.to_csv(os.path.join(run_archive_dir, "procurement_recommendations.csv"), index=False)
        rej_df.to_csv(os.path.join(run_archive_dir, "rejected_opportunities.csv"), index=False)
        with open(os.path.join(run_archive_dir, "optimization_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary_dict, f, indent=2)

        logger.info(f"Successfully persisted optimization artifacts to {output_dir} and {run_archive_dir}")
