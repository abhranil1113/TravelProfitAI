"""
tests/optimization/test_recommendations.py

Unit tests for procurement recommendation and rejection generation.
Validates:
1. Recommendation record creation for selected offers.
2. Accurate, non-fabricated, evidence-backed selection rationales.
3. Structured rejection reason attribution (NEGATIVE_CONTRIBUTION, MOQ_EXCEEDS_BUDGET, etc.).
4. Expired offer rejection handling.
"""

import pytest
from optimization.config import OptimizationConfig, RiskConfig
from optimization.schemas import ProcurementOpportunity, CandidateOffer, SolverResult
from optimization.recommendations.generator import RecommendationGenerator
from optimization.recommendations.rejection_reasons import RejectionReasonCode


def make_opportunity(
    opp_id: str,
    inv_type: str,
    cost: float,
    price: float,
    contrib: float,
    avail: int,
    moq: int = 1,
    sup: str = "SUP001",
    dest: str = "DEST_MUMBAI",
    demand: int = 100,
    valid_until: str = "2026-06-30"
) -> ProcurementOpportunity:
    return ProcurementOpportunity(
        opportunity_id=opp_id,
        offer_id=f"OFF_{opp_id}",
        supplier_id=sup,
        inventory_type=inv_type,
        inventory_id=f"INV_{opp_id}",
        destination_id=dest,
        travel_date="2026-06-15",
        purchase_cost=cost,
        selling_price=price,
        available_quantity=avail,
        minimum_purchase_qty=moq,
        refundable=True,
        offer_valid_until=valid_until,
        currency="INR",
        unit_type="ROOM_NIGHT" if inv_type == "HOTEL" else "SEAT",
        point_in_time_capacity=avail,
        predicted_cancellation_prob=0.18,
        sell_through_probability=0.85,
        expected_unit_contribution=contrib,
        expected_unit_revenue=contrib + cost,
        aggregate_demand_cap=demand
    )


class TestRecommendationGeneration:
    """Tests recommendation and rejection generation logic."""

    def test_selected_offer_recommendation_details(self):
        """Selected offer must produce fully typed RecommendationRecord with non-empty rationale."""
        opp1 = make_opportunity("OPP_1", "HOTEL", 2000.0, 2500.0, 350.0, avail=20, moq=2)
        cand1 = CandidateOffer(
            index=0, opportunity_id="OPP_1", offer_id="OFF_OPP_1", supplier_id="SUP001",
            inventory_type="HOTEL", inventory_id="INV_OPP_1", destination_id="DEST_MUMBAI",
            travel_date="2026-06-15", unit_cost=2000.0, unit_selling_price=2500.0,
            available_qty=20, moq=2, unit_contribution=350.0, unit_type="ROOM_NIGHT",
            aggregate_demand=100
        )
        solver_res = SolverResult(
            status="OPTIMAL", is_proven_optimal=True, objective_value=3500.0,
            execution_time_seconds=0.01, solver_name="TestSolver", num_variables=1,
            num_constraints=1, selected_quantities={"OPP_1": 10}, selected_offers={"OPP_1": 1},
            total_spend=20000.0, hotel_spend=20000.0, flight_spend=0.0, remaining_budget=5000.0
        )
        cfg = OptimizationConfig(run_id="REC_TEST_RUN", total_budget=25000.0)

        recs, rejs = RecommendationGenerator.generate([opp1], [cand1], solver_res, cfg)

        assert len(recs) == 1
        assert len(rejs) == 0
        r = recs[0]
        assert r.opportunity_id == "OPP_1"
        assert r.procurement_quantity == 10
        assert r.unit_purchase_cost == 2000.0
        assert r.total_procurement_cost == 20000.0
        assert r.expected_total_net_profit == 3500.0
        assert r.selection_status == "SELECTED"
        assert "Selected 10 room_nights" in r.selection_rationale
        assert "SUP001" in r.selection_rationale

    def test_negative_contribution_rejection_reason(self):
        """Offers with negative expected contribution must be rejected with NEGATIVE_CONTRIBUTION."""
        opp_neg = make_opportunity("OPP_NEG", "FLIGHT", 5000.0, 4500.0, -800.0, avail=10, moq=1)
        solver_res = SolverResult(
            status="OPTIMAL", is_proven_optimal=True, objective_value=0.0,
            execution_time_seconds=0.01, solver_name="TestSolver", num_variables=1,
            num_constraints=1, selected_quantities={}, selected_offers={},
            total_spend=0.0, hotel_spend=0.0, flight_spend=0.0, remaining_budget=25000.0
        )
        cfg = OptimizationConfig(run_id="REJ_TEST_RUN", total_budget=25000.0)

        recs, rejs = RecommendationGenerator.generate([opp_neg], [], solver_res, cfg)

        assert len(recs) == 0
        assert len(rejs) == 1
        rej = rejs[0]
        assert rej.rejection_primary_reason == RejectionReasonCode.NEGATIVE_CONTRIBUTION.value
        assert "negative" in rej.rejection_explanation.lower()

    def test_moq_exceeds_budget_rejection_reason(self):
        """If MOQ cost > total budget, reason must be MOQ_EXCEEDS_BUDGET."""
        opp_moq = make_opportunity("OPP_EXPENSIVE", "HOTEL", 10000.0, 15000.0, 3000.0, avail=10, moq=5)
        solver_res = SolverResult(
            status="OPTIMAL", is_proven_optimal=True, objective_value=0.0,
            execution_time_seconds=0.01, solver_name="TestSolver", num_variables=1,
            num_constraints=1, selected_quantities={}, selected_offers={},
            total_spend=0.0, hotel_spend=0.0, flight_spend=0.0, remaining_budget=20000.0
        )
        # Total budget is 20,000, but MOQ requires 5 * 10,000 = 50,000
        cfg = OptimizationConfig(run_id="REJ_MOQ_RUN", total_budget=20000.0)

        recs, rejs = RecommendationGenerator.generate([opp_moq], [], solver_res, cfg)

        assert len(rejs) == 1
        assert rejs[0].rejection_primary_reason == RejectionReasonCode.MOQ_EXCEEDS_BUDGET.value

    def test_expired_offer_attribution(self):
        """Expired offers must be categorized as EXPIRED_OFFER."""
        expired_data = [{
            "offer_id": "OFF_OLD",
            "supplier_id": "SUP999",
            "inventory_type": "HOTEL",
            "inventory_id": "INV_OLD",
            "destination_id": "DEST_OLD",
            "travel_date": "2026-05-01",
            "cost_per_unit": 3000.0,
            "minimum_purchase_quantity": 2,
            "quantity_available": 10,
            "valid_until": "2026-05-15"
        }]
        solver_res = SolverResult(
            status="OPTIMAL", is_proven_optimal=True, objective_value=0.0,
            execution_time_seconds=0.01, solver_name="TestSolver", num_variables=0,
            num_constraints=0, selected_quantities={}, selected_offers={},
            total_spend=0.0, hotel_spend=0.0, flight_spend=0.0, remaining_budget=20000.0
        )
        cfg = OptimizationConfig(run_id="REJ_EXP_RUN", optimization_timestamp="2026-06-01")

        recs, rejs = RecommendationGenerator.generate([], [], solver_res, cfg, expired_offers=expired_data)

        assert len(rejs) == 1
        assert rejs[0].rejection_primary_reason == RejectionReasonCode.EXPIRED_OFFER.value
        assert "expired on or before" in rejs[0].rejection_explanation.lower()
