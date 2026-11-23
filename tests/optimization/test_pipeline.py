"""
tests/optimization/test_pipeline.py

Integration tests for master OptimizationPipeline.
Validates:
1. Hotel-only procurement execution.
2. Flight-only procurement execution.
3. Joint multi-product procurement execution.
4. Correct persistence of CSV recommendations, rejections, and summary JSONs.
5. Run ID isolation.
"""

import os
import json
import pytest
from optimization.config import OptimizationConfig
from optimization.pipeline import OptimizationPipeline


class TestOptimizationPipeline:
    """End-to-end integration tests for OptimizationPipeline."""

    def test_joint_pipeline_execution_and_persistence(self, tmp_path):
        """Joint optimization executes, solves, and saves artifacts to run directory."""
        run_id = "TEST_JOINT_PIPE_001"
        out_dir = str(tmp_path / "opt_output")
        cfg = OptimizationConfig(
            run_id=run_id,
            optimization_timestamp="2026-06-01",
            total_budget=100000.0
        )
        pipeline = OptimizationPipeline(cfg)
        plan = pipeline.run(output_dir=out_dir)

        assert plan.run_id == run_id
        assert plan.evaluation_metrics.solver_status in ["OPTIMAL", "FEASIBLE"]
        assert plan.evaluation_metrics.total_spend <= cfg.total_budget
        assert plan.evaluation_metrics.remaining_budget >= 0.0

        # Verify output files in canonical directory
        rec_csv = os.path.join(out_dir, "procurement_recommendations.csv")
        rej_csv = os.path.join(out_dir, "rejected_opportunities.csv")
        summary_json = os.path.join(out_dir, "optimization_summary.json")

        assert os.path.exists(rec_csv)
        assert os.path.exists(rej_csv)
        assert os.path.exists(summary_json)

        # Verify run-isolated archive
        run_archive = os.path.join(out_dir, "optimization_runs", run_id)
        assert os.path.exists(os.path.join(run_archive, "procurement_recommendations.csv"))
        assert os.path.exists(os.path.join(run_archive, "optimization_summary.json"))

        # Verify summary JSON content
        with open(summary_json, "r") as f:
            data = json.load(f)
        assert data["run_id"] == run_id
        assert "solver_metadata" in data

    def test_hotel_only_pipeline_execution(self, tmp_path):
        """Setting flight_budget_max=0.0 must enforce Hotel-only optimization."""
        run_id = "TEST_HOTEL_ONLY_PIPE"
        out_dir = str(tmp_path / "hotel_opt")
        cfg = OptimizationConfig(
            run_id=run_id,
            optimization_timestamp="2026-06-01",
            total_budget=80000.0,
            flight_budget_max=0.0
        )
        pipeline = OptimizationPipeline(cfg)
        plan = pipeline.run(output_dir=out_dir)

        assert plan.evaluation_metrics.flight_spend == 0.0
        assert plan.evaluation_metrics.flight_seats_procured == 0
        for rec in plan.recommendations:
            assert rec.inventory_type == "HOTEL"

    def test_flight_only_pipeline_execution(self, tmp_path):
        """Setting hotel_budget_max=0.0 must enforce Flight-only optimization."""
        run_id = "TEST_FLIGHT_ONLY_PIPE"
        out_dir = str(tmp_path / "flight_opt")
        cfg = OptimizationConfig(
            run_id=run_id,
            optimization_timestamp="2026-06-01",
            total_budget=80000.0,
            hotel_budget_max=0.0
        )
        pipeline = OptimizationPipeline(cfg)
        plan = pipeline.run(output_dir=out_dir)

        assert plan.evaluation_metrics.hotel_spend == 0.0
        assert plan.evaluation_metrics.hotel_room_nights_procured == 0
        for rec in plan.recommendations:
            assert rec.inventory_type == "FLIGHT"
