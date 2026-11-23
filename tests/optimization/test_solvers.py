"""
tests/optimization/test_solvers.py

Comprehensive unit tests and independent mathematical validation for MILP solvers:
HotelProcurementOptimizer, FlightProcurementOptimizer, and JointProcurementOptimizer.
Uses small, deterministic mathematical examples where optimal solutions are known analytically.
"""

import pytest
from optimization.config import OptimizationConfig, RiskConfig, SolverConfig, SolverBackend
from optimization.schemas import CandidateOffer, SolverTerminationStatus
from optimization.solvers.hotel_optimizer import HotelProcurementOptimizer
from optimization.solvers.flight_optimizer import FlightProcurementOptimizer
from optimization.solvers.joint_optimizer import JointProcurementOptimizer


def make_candidate(
    idx: int,
    opp_id: str,
    inv_type: str,
    unit_cost: float,
    selling_price: float,
    unit_contrib: float,
    available_qty: int,
    moq: int = 1,
    supplier_id: str = "SUP001",
    destination_id: str = "DEST_GOA",
    demand_cap: int = 100
) -> CandidateOffer:
    return CandidateOffer(
        index=idx,
        opportunity_id=opp_id,
        offer_id=f"OFF_{opp_id}",
        supplier_id=supplier_id,
        inventory_type=inv_type,
        inventory_id=f"INV_{opp_id}",
        destination_id=destination_id,
        travel_date="2026-06-15",
        unit_cost=unit_cost,
        unit_selling_price=selling_price,
        available_qty=available_qty,
        moq=moq,
        unit_contribution=unit_contrib,
        unit_type="ROOM_NIGHT" if inv_type == "HOTEL" else "SEAT",
        aggregate_demand=demand_cap
    )


class TestIndependentDeterministicSolvers:
    """Deterministic hand-verifiable mathematical optimization test cases."""

    def test_hotel_two_offers_budget_allocation(self):
        """
        Offer A: cost=1000, contrib=300 (ROI 0.30), avail=5, MOQ=2
        Offer B: cost=1000, contrib=100 (ROI 0.10), avail=5, MOQ=2
        Budget = 4000.
        Expected optimal: 4 units of Offer A (spend 4000, profit 1200).
        """
        cands = [
            make_candidate(0, "H_A", "HOTEL", 1000.0, 1500.0, 300.0, available_qty=5, moq=2),
            make_candidate(1, "H_B", "HOTEL", 1000.0, 1500.0, 100.0, available_qty=5, moq=2),
        ]
        cfg = OptimizationConfig(
            run_id="DET_H1",
            total_budget=4000.0,
            risk=RiskConfig(enable_supplier_concentration=False)
        )
        solver = HotelProcurementOptimizer()
        res = solver.solve(cands, cfg)

        assert res.status == SolverTerminationStatus.OPTIMAL
        assert res.is_proven_optimal is True
        assert res.selected_quantities.get("H_A") == 4
        assert "H_B" not in res.selected_quantities
        assert res.total_spend == 4000.0
        assert res.objective_value == 1200.0

    def test_moq_enforcement_all_or_nothing(self):
        """
        Offer A: cost=1000, contrib=500, avail=10, MOQ=5 (min spend 5000).
        Budget = 4000.
        Cannot afford MOQ of 5, so solver must NOT buy 1, 2, 3, or 4 units!
        Expected optimal: 0 units selected, profit 0.
        """
        cands = [
            make_candidate(0, "H_MOQ", "HOTEL", 1000.0, 1600.0, 500.0, available_qty=10, moq=5)
        ]
        cfg = OptimizationConfig(run_id="DET_MOQ", total_budget=4000.0)
        solver = HotelProcurementOptimizer()
        res = solver.solve(cands, cfg)

        assert res.selected_quantities.get("H_MOQ", 0) == 0
        assert res.total_spend == 0.0
        assert res.objective_value == 0.0

    def test_capacity_upper_bound_enforcement(self):
        """
        Offer A: cost=500, contrib=200, avail=3, MOQ=1.
        Budget = 10,000.
        Even with huge budget, solver cannot purchase more than 3 units.
        Expected optimal: 3 units (spend 1500, profit 600).
        """
        cands = [
            make_candidate(0, "H_CAP", "HOTEL", 500.0, 800.0, 200.0, available_qty=3, moq=1)
        ]
        cfg = OptimizationConfig(run_id="DET_CAP", total_budget=10000.0)
        solver = HotelProcurementOptimizer()
        res = solver.solve(cands, cfg)

        assert res.selected_quantities.get("H_CAP") == 3
        assert res.total_spend == 1500.0
        assert res.objective_value == 600.0

    def test_destination_demand_absorption_cap(self):
        """
        Offer A: cost=500, contrib=250, avail=20, MOQ=2, demand_cap=6.
        Budget = 50,000.
        Solver must not exceed destination demand ceiling of 6 units.
        Expected optimal: 6 units (spend 3000, profit 1500).
        """
        cands = [
            make_candidate(0, "H_DEST", "HOTEL", 500.0, 800.0, 250.0, available_qty=20, moq=2, demand_cap=6)
        ]
        cfg = OptimizationConfig(run_id="DET_DEST", total_budget=50000.0)
        solver = HotelProcurementOptimizer()
        res = solver.solve(cands, cfg)

        assert res.selected_quantities.get("H_DEST") == 6
        assert res.total_spend == 3000.0
        assert res.objective_value == 1500.0

    def test_supplier_concentration_cap(self):
        """
        Offer S1: Supplier SUP001, cost=1000, contrib=500, avail=10, MOQ=1.
        Budget = 10,000. Supplier concentration limit = 20% (max 2,000 spend).
        Solver must purchase at most 2 units from SUP001.
        """
        cands = [
            make_candidate(0, "H_SUP", "HOTEL", 1000.0, 1600.0, 500.0, available_qty=10, moq=1, supplier_id="SUP001")
        ]
        cfg = OptimizationConfig(
            run_id="DET_SUP",
            total_budget=10000.0,
            risk=RiskConfig(enable_supplier_concentration=True, supplier_concentration_limit=0.20)
        )
        solver = HotelProcurementOptimizer()
        res = solver.solve(cands, cfg)

        assert res.selected_quantities.get("H_SUP") == 2
        assert res.total_spend == 2000.0
        assert res.objective_value == 1000.0

    def test_joint_optimizer_competing_hotel_and_flight(self):
        """
        Shared budget = 5000.
        Hotel H1: cost=1000, contrib=400 (ROI 0.40), avail=3, MOQ=1
        Flight F1: cost=1000, contrib=200 (ROI 0.20), avail=5, MOQ=1
        Shared budget allows 5 total units.
        Optimizer should purchase all 3 of H1 (profit 1200) + 2 of F1 (profit 400).
        Total profit = 1600, total spend = 5000.
        """
        cands = [
            make_candidate(0, "H1", "HOTEL", 1000.0, 1500.0, 400.0, available_qty=3, moq=1, supplier_id="SUP_H", destination_id="DEST_H"),
            make_candidate(1, "F1", "FLIGHT", 1000.0, 1300.0, 200.0, available_qty=5, moq=1, supplier_id="SUP_F", destination_id="DEST_F"),
        ]
        cfg = OptimizationConfig(
            run_id="DET_JOINT",
            total_budget=5000.0,
            risk=RiskConfig(enable_supplier_concentration=False, enable_destination_concentration=False)
        )
        solver = JointProcurementOptimizer()
        res = solver.solve(cands, cfg)

        assert res.status == SolverTerminationStatus.OPTIMAL
        assert res.selected_quantities.get("H1") == 3
        assert res.selected_quantities.get("F1") == 2
        assert res.hotel_spend == 3000.0
        assert res.flight_spend == 2000.0
        assert res.total_spend == 5000.0
        assert res.objective_value == 1600.0

    def test_negative_contribution_never_selected(self):
        """
        Offer with negative contribution (-200) must NEVER be procured by any optimizer.
        """
        cands = [
            make_candidate(0, "H_NEG", "HOTEL", 1000.0, 800.0, -200.0, available_qty=10, moq=1)
        ]
        cfg = OptimizationConfig(run_id="DET_NEG", total_budget=10000.0)
        for solver_cls in [HotelProcurementOptimizer, JointProcurementOptimizer]:
            solver = solver_cls()
            res = solver.solve(cands, cfg)
            assert res.selected_quantities.get("H_NEG", 0) == 0
            assert res.total_spend == 0.0
            assert res.objective_value == 0.0
