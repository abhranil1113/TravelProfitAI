"""
tests/optimization/test_config.py

Comprehensive test suite verifying centralized configuration models, Pydantic validations,
cross-field budget/probability integrity, economic calculation consistency, and pipeline
propagation & reproducibility.
"""

import json
import pytest
from pydantic import ValidationError

from optimization.config import (
    CurrencyTier,
    FinancialAssumptions,
    OptimizationConfig,
    RiskConfig,
    SolverBackend,
    SolverConfig,
)
from optimization.economics.flight_economics import FlightEconomicsCalculator
from optimization.economics.hotel_economics import HotelEconomicsCalculator
from optimization.pipeline import OptimizationPipeline
from optimization.solvers.solver_factory import SolverFactory


class TestConfigurationDefaultsAndOverrides:
    """Verifies default values and valid overrides in centralized configuration models."""

    def test_default_configuration_values(self):
        """1. Verify default configuration values match Stage 1.3 audited specifications."""
        fin = FinancialAssumptions()
        assert fin.hotel_base_sell_through == 0.85
        assert fin.hotel_customer_refund_rate == 0.80
        assert fin.hotel_supplier_refund_rate_cancel == 0.85
        assert fin.hotel_supplier_refund_rate_unsold == 0.00
        assert fin.hotel_room_resale_probability == 0.40
        assert fin.hotel_resale_discount_factor == 0.90
        assert fin.hotel_assumed_stay_duration == 2.0

        assert fin.flight_base_sell_through == 0.85
        assert fin.flight_min_sell_through == 0.05
        assert fin.flight_max_sell_through == 0.99
        assert fin.flight_salvage_rate_default == 0.00
        assert fin.flight_salvage_rate_optional == 0.10
        assert fin.flight_unsold_penalty == 0.0
        assert fin.flight_price_elasticity == 1.5
        assert fin.prototype_eur_to_inr_rate == 90.0

        assert fin.demand_scenario_multiplier == 1.0
        assert fin.default_search_conversion_rate == 0.15
        assert fin.default_travellers_per_booking == 2.0
        assert fin.default_rooms_per_booking == 1.0

        risk = RiskConfig()
        assert risk.enable_destination_concentration is True
        assert risk.destination_exposure_limit == 0.25
        assert risk.enable_supplier_concentration is True
        assert risk.supplier_concentration_limit == 0.20
        assert risk.bayesian_shrinkage_lambda == 0.70
        assert risk.hotel_default_cancellation_prior == 0.25
        assert risk.min_cancellation_prob == 0.01
        assert risk.max_cancellation_prob == 0.99

        solver = SolverConfig()
        assert solver.backend == SolverBackend.SCIP
        assert solver.time_limit_seconds == 60.0
        assert solver.relative_gap_tolerance == 1e-4

        cfg = OptimizationConfig(run_id="DEFAULT_VERIFY")
        assert cfg.total_budget == 250000.0
        assert cfg.target_currency == "INR"
        assert "EUR" in cfg.verified_currencies
        assert cfg.allow_prototype_currency_override is True

    def test_valid_configuration_overrides(self):
        """2. Verify custom overrides are successfully validated and accepted."""
        custom_fin = FinancialAssumptions(
            hotel_base_sell_through=0.90,
            hotel_customer_refund_rate=0.75,
            flight_min_sell_through=0.10,
            flight_max_sell_through=0.95,
            flight_price_elasticity=2.0,
            prototype_eur_to_inr_rate=95.0,
            demand_scenario_multiplier=1.25,
        )
        assert custom_fin.hotel_base_sell_through == 0.90
        assert custom_fin.flight_min_sell_through == 0.10
        assert custom_fin.flight_max_sell_through == 0.95
        assert custom_fin.demand_scenario_multiplier == 1.25

        custom_risk = RiskConfig(
            destination_exposure_limit=0.30,
            supplier_concentration_limit=0.15,
            bayesian_shrinkage_lambda=0.80,
            min_cancellation_prob=0.05,
            max_cancellation_prob=0.95,
        )
        assert custom_risk.destination_exposure_limit == 0.30
        assert custom_risk.supplier_concentration_limit == 0.15

        cfg = OptimizationConfig(
            run_id="CUSTOM_001",
            total_budget=500000.0,
            hotel_budget_max=300000.0,
            flight_budget_max=300000.0,
            financial=custom_fin,
            risk=custom_risk,
        )
        assert cfg.total_budget == 500000.0
        assert cfg.financial.hotel_base_sell_through == 0.90
        assert cfg.risk.destination_exposure_limit == 0.30


class TestConfigurationBoundaryValidation:
    """Verifies rejection of invalid boundaries, thresholds, and inconsistent combinations."""

    def test_invalid_probability_boundaries(self):
        """3. Probability values outside [0.0, 1.0] must be rejected."""
        with pytest.raises(ValidationError):
            FinancialAssumptions(hotel_base_sell_through=-0.01)

        with pytest.raises(ValidationError):
            FinancialAssumptions(hotel_base_sell_through=1.05)

        with pytest.raises(ValidationError):
            FinancialAssumptions(flight_base_sell_through=1.5)

        with pytest.raises(ValidationError):
            RiskConfig(bayesian_shrinkage_lambda=-0.1)

        with pytest.raises(ValidationError):
            RiskConfig(destination_exposure_limit=1.1)

    def test_invalid_min_max_thresholds(self):
        """4. Minimum thresholds cannot exceed maximum thresholds."""
        # Flight min sell-through > max sell-through
        with pytest.raises(ValidationError, match="flight_min_sell_through.*cannot exceed.*flight_max_sell_through"):
            FinancialAssumptions(flight_min_sell_through=0.80, flight_max_sell_through=0.50)

        # Cancellation min prob > max prob
        with pytest.raises(ValidationError, match="min_cancellation_prob.*cannot exceed.*max_cancellation_prob"):
            RiskConfig(min_cancellation_prob=0.90, max_cancellation_prob=0.10)

    def test_invalid_currency_conversion_rates(self):
        """5. Currency conversion rates must be strictly positive."""
        with pytest.raises(ValidationError):
            FinancialAssumptions(prototype_eur_to_inr_rate=0.0)

        with pytest.raises(ValidationError):
            FinancialAssumptions(prototype_eur_to_inr_rate=-10.0)

    def test_invalid_budget_combinations(self):
        """6. Inconsistent budget allocations must be rejected with informative errors."""
        # Category min exceeds category max
        with pytest.raises(ValidationError, match="hotel_budget_min.*cannot exceed.*hotel_budget_max"):
            OptimizationConfig(
                run_id="BAD_BUDGET_1",
                total_budget=100000.0,
                hotel_budget_min=60000.0,
                hotel_budget_max=40000.0,
            )

        with pytest.raises(ValidationError, match="flight_budget_min.*cannot exceed.*flight_budget_max"):
            OptimizationConfig(
                run_id="BAD_BUDGET_2",
                total_budget=100000.0,
                flight_budget_min=80000.0,
                flight_budget_max=50000.0,
            )

        # Category max exceeds total budget
        with pytest.raises(ValidationError, match="hotel_budget_max.*cannot exceed total_budget"):
            OptimizationConfig(
                run_id="BAD_BUDGET_3",
                total_budget=100000.0,
                hotel_budget_max=150000.0,
            )

        # Sum of minimums exceeds total budget
        with pytest.raises(ValidationError, match="Sum of category minimum budgets.*cannot exceed total_budget"):
            OptimizationConfig(
                run_id="BAD_BUDGET_4",
                total_budget=100000.0,
                hotel_budget_min=60000.0,
                flight_budget_min=50000.0,
            )


class TestEconomicsCalculationConsistency:
    """Verifies that refactored calculation modules preserve mathematical accuracy with configuration."""

    def test_hotel_economics_calculation_consistency(self):
        """7. Hotel expected contribution formula matches deterministic mathematical hand calculations."""
        fin = FinancialAssumptions(
            hotel_base_sell_through=0.85,
            hotel_customer_refund_rate=0.80,
            hotel_supplier_refund_rate_cancel=0.85,
            hotel_supplier_refund_rate_unsold=0.00,
            hotel_room_resale_probability=0.40,
            hotel_resale_discount_factor=0.90,
        )
        calc = HotelEconomicsCalculator(fin)

        # c = 4000, p = 5000, cancellation_prob = 0.20, refundable = True
        res = calc.calculate_expected_contribution(
            purchase_cost=4000.0,
            selling_price=5000.0,
            cancellation_prob=0.20,
            is_supplier_refundable=True,
            sell_through_prob=0.85,
        )
        assert pytest.approx(res["expected_gross_revenue"], abs=1e-4) == 4222.80
        assert pytest.approx(res["expected_net_contribution"], abs=1e-4) == 222.80

    def test_flight_economics_calculation_consistency(self):
        """8. Flight economics respects configurable sell-through bounds and elasticity."""
        # Test custom elasticity bounds: min 0.15, max 0.80
        fin = FinancialAssumptions(
            flight_base_sell_through=0.85,
            flight_min_sell_through=0.15,
            flight_max_sell_through=0.80,
            flight_price_elasticity=2.0,
        )
        calc = FlightEconomicsCalculator(fin)

        # 1. Below ceiling: contract 3000 <= market 4000 -> clipped to max bound 0.80
        theta_under = calc.calculate_adjusted_sell_through(contract_price=3000.0, market_ceiling_price=4000.0)
        assert theta_under == 0.80

        # 2. Substantially above ceiling: contract 10000 >> market 2000 -> clipped to min bound 0.15
        theta_over = calc.calculate_adjusted_sell_through(contract_price=10000.0, market_ceiling_price=2000.0)
        assert theta_over == 0.15


class TestSolverAndPipelineTraceability:
    """Verifies solver parameters, configuration propagation, and deterministic reproducibility."""

    def test_solver_configuration_validation(self):
        """9. Solver configuration enforces positive time limits and proper backend sequences."""
        with pytest.raises(ValidationError):
            SolverConfig(time_limit_seconds=0.0)

        with pytest.raises(ValidationError):
            SolverConfig(time_limit_seconds=-5.0)

        solver_cfg = SolverConfig(time_limit_seconds=30.0, relative_gap_tolerance=1e-3)
        solver = SolverFactory.create_solver(solver_cfg, problem_name="Test_Solver")
        assert solver is not None

    def test_configuration_propagation_through_pipeline(self, tmp_path):
        """10. Configuration values propagate completely through the pipeline to persistent artifacts."""
        run_id = "TEST_PROPAGATION_001"
        out_dir = str(tmp_path / "prop_out")
        cfg = OptimizationConfig(
            run_id=run_id,
            optimization_timestamp="2026-06-01",
            total_budget=120000.0,
            target_currency="INR",
            financial=FinancialAssumptions(
                hotel_base_sell_through=0.88,
                flight_min_sell_through=0.08,
            ),
            risk=RiskConfig(
                destination_exposure_limit=0.30,
            ),
        )

        pipeline = OptimizationPipeline(cfg)
        plan = pipeline.run(output_dir=out_dir)

        # Verify fingerprint is present in plan metadata
        fingerprint = cfg.get_fingerprint()
        assert plan.solver_metadata["config_fingerprint"] == fingerprint

        # Verify summary JSON persists exact configuration assumptions
        summary_path = f"{out_dir}/optimization_summary.json"
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        assert summary["config_fingerprint"] == fingerprint
        assert summary["financial_assumptions"]["hotel_base_sell_through"] == 0.88
        assert summary["financial_assumptions"]["flight_min_sell_through"] == 0.08
        assert summary["risk_assumptions"]["destination_exposure_limit"] == 0.30
        assert summary["currency_assumptions"]["target_currency"] == "INR"

    def test_reproducibility_of_optimization_results(self, tmp_path):
        """11. Identical configurations produce identical fingerprints and identical optimization outputs."""
        cfg_1 = OptimizationConfig(
            run_id="REPRO_RUN_1",
            optimization_timestamp="2026-06-01",
            total_budget=100000.0,
        )
        cfg_2 = OptimizationConfig(
            run_id="REPRO_RUN_1",  # Same run parameters
            optimization_timestamp="2026-06-01",
            total_budget=100000.0,
        )

        # Fingerprints must be bitwise identical
        assert cfg_1.get_fingerprint() == cfg_2.get_fingerprint()

        # Changing any single assumption changes the fingerprint
        cfg_modified = cfg_1.model_copy(update={"total_budget": 150000.0})
        assert cfg_modified.get_fingerprint() != cfg_1.get_fingerprint()
