"""
scripts/benchmark_optimization_performance.py

Benchmarks Google OR-Tools MILP solver scalability across offer pool sizes:
10, 50, 100, 500, 1000, and full active candidate pool (3,257).
Records runtime, variable counts, constraint counts, status, objective, and gap.
"""

import os
import time
import json
import logging
from typing import List, Dict, Any

from optimization.config import OptimizationConfig
from optimization.data.candidate_builder import CandidateOpportunityBuilder
from optimization.solvers.joint_optimizer import JointProcurementOptimizer
from optimization.schemas import CandidateOffer, SolverResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Benchmark")


def run_benchmarks():
    cfg = OptimizationConfig(
        run_id="BENCHMARK_SCALABILITY",
        optimization_timestamp="2026-06-01",
        total_budget=500000.0
    )
    logger.info("Loading candidate opportunities for benchmarking...")
    builder = CandidateOpportunityBuilder(cfg)
    opps, all_candidates, audit = builder.build_candidate_opportunities()
    total_avail = len(all_candidates)
    logger.info(f"Loaded {total_avail} total active candidate offers.")

    slice_sizes = [10, 50, 100, 500, 1000, total_avail]
    benchmark_results = []
    optimizer = JointProcurementOptimizer()

    print("\n" + "="*95)
    print(f"{'OFFERS':<8} | {'VARS':<8} | {'CONSTR':<8} | {'STATUS':<10} | {'OPTIMAL':<8} | {'OBJ VALUE':<12} | {'SPEND':<12} | {'TIME (s)':<10}")
    print("="*95)

    for n in slice_sizes:
        sub_cands = all_candidates[:n]
        start_t = time.perf_counter()
        res: SolverResult = optimizer.solve(sub_cands, cfg)
        elapsed = time.perf_counter() - start_t

        row = {
            "num_offers": n,
            "num_variables": res.num_variables,
            "num_constraints": res.num_constraints,
            "status": res.status,
            "is_proven_optimal": res.is_proven_optimal,
            "objective_value": round(res.objective_value, 2),
            "total_spend": round(res.total_spend, 2),
            "execution_time_seconds": round(res.execution_time_seconds, 4),
            "wall_clock_time_seconds": round(elapsed, 4),
            "solver_name": res.solver_name,
            "optimality_gap": res.optimality_gap,
            "selected_offers_count": len(res.selected_quantities)
        }
        benchmark_results.append(row)

        print(f"{n:<8} | {res.num_variables:<8} | {res.num_constraints:<8} | {res.status:<10} | {str(res.is_proven_optimal):<8} | {res.objective_value:<12.2f} | {res.total_spend:<12.2f} | {res.execution_time_seconds:<10.4f}")

    print("="*95 + "\n")

    out_path = "reports/optimization/solver_performance_benchmarks.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)

    logger.info(f"Saved benchmark results to {out_path}")
    return benchmark_results


if __name__ == "__main__":
    run_benchmarks()
