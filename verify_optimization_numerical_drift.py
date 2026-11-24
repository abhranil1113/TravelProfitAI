import sys
from optimization.config import OptimizationConfig
from optimization.pipeline import OptimizationPipeline

def main():
    print("Running numerical verification of OptimizationPipeline...")
    cfg = OptimizationConfig(
        run_id="NUMERICAL_VERIFICATION_CHECK",
        optimization_timestamp="2026-06-01",
        total_budget=100000.0
    )
    pipeline = OptimizationPipeline(cfg)
    plan = pipeline.run(output_dir=None)
    metrics = plan.evaluation_metrics

    print("=== NUMERICAL VERIFICATION RESULTS ===")
    print(f"Solver Status: {metrics.solver_status}")
    print(f"Is Proven Optimal: {metrics.is_proven_optimal}")
    print(f"Total Budget: {metrics.total_budget}")
    print(f"Total Spend: {metrics.total_spend:.4f}")
    print(f"Expected Net Profit: {metrics.expected_net_profit:.4f}")
    print(f"Return on Spend: {metrics.return_on_procurement_spend:.6f}")
    print(f"Hotel Spend: {metrics.hotel_spend:.4f}")
    print(f"Flight Spend: {metrics.flight_spend:.4f}")
    print(f"Total Units Procured: {metrics.total_units_procured}")
    print(f"Hotel Room Nights: {metrics.hotel_room_nights_procured}")
    print(f"Flight Seats: {metrics.flight_seats_procured}")
    print(f"Selected Opportunities: {metrics.selected_opportunities_count}")
    print(f"Config Fingerprint: {cfg.get_fingerprint()}")

    # Baseline benchmarks from test_joint_pipeline_execution_and_persistence
    # Expected spend: 55794.32, profit: 5391.35, total units: 16
    expected_spend = 55794.32
    expected_profit = 5391.35
    expected_units = 16

    spend_diff = abs(metrics.total_spend - expected_spend)
    profit_diff = abs(metrics.expected_net_profit - expected_profit)
    units_diff = abs(metrics.total_units_procured - expected_units)

    print(f"Spend Difference vs Baseline: {spend_diff:.6f}")
    print(f"Profit Difference vs Baseline: {profit_diff:.6f}")
    print(f"Units Difference vs Baseline: {units_diff}")

    assert spend_diff < 1e-4, f"Spend difference {spend_diff} exceeds tolerance"
    assert profit_diff < 1e-4, f"Profit difference {profit_diff} exceeds tolerance"
    assert units_diff == 0, f"Units difference {units_diff} must be 0"

    print("VERIFICATION SUCCESSFUL: Zero numerical drift confirmed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
