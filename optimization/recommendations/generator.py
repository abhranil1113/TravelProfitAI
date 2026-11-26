"""
optimization/recommendations/generator.py

Generates typed, explainable RecommendationRecord and RejectedOpportunityRecord collections
from candidate opportunities and solver outputs.
Applies counterfactual constraint binding checks to accurately attribute rejection causes.
"""

from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any

from optimization.config import OptimizationConfig
from optimization.schemas import (
    ProcurementOpportunity,
    CandidateOffer,
    SolverResult,
    RecommendationRecord,
    RejectedOpportunityRecord
)
from optimization.recommendations.rejection_reasons import RejectionReasonCode
from optimization.recommendations.explanations import ExplanationEngine


class RecommendationGenerator:
    """Generates explainable recommendation and rejection records."""

    @staticmethod
    def generate(
        opportunities: List[ProcurementOpportunity],
        candidates: List[CandidateOffer],
        solver_result: SolverResult,
        config: OptimizationConfig,
        expired_offers: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[RecommendationRecord], List[RejectedOpportunityRecord]]:
        """
        Produces selected recommendations and structured rejections with evidence-backed reasons.
        """
        opp_map: Dict[str, ProcurementOpportunity] = {o.opportunity_id: o for o in opportunities}
        cand_map: Dict[str, CandidateOffer] = {c.opportunity_id: c for c in candidates}

        recommendations: List[RecommendationRecord] = []
        rejected: List[RejectedOpportunityRecord] = []

        # 1. Process Selected Opportunities
        for opp_id, qty in solver_result.selected_quantities.items():
            if qty <= 0 or opp_id not in opp_map:
                continue
            opp = opp_map[opp_id]
            rationale = ExplanationEngine.build_selection_rationale(opp, qty, solver_result, config)

            rec = RecommendationRecord(
                recommendation_id=f"REC_{config.run_id}_{opp_id}",
                run_id=config.run_id,
                opportunity_id=opp_id,
                offer_id=opp.offer_id,
                supplier_id=opp.supplier_id,
                inventory_type=opp.inventory_type,
                inventory_id=opp.inventory_id,
                destination_id=opp.destination_id,
                origin_id=opp.origin_id,
                travel_date=opp.travel_date,
                procurement_quantity=qty,
                unit_type=opp.unit_type,
                unit_purchase_cost=float(round(opp.purchase_cost, 2)),
                total_procurement_cost=float(round(qty * opp.purchase_cost, 2)),
                unit_selling_price=float(round(opp.selling_price, 2)),
                expected_unit_contribution=float(round(opp.expected_unit_contribution, 2)),
                expected_total_net_profit=float(round(qty * opp.expected_unit_contribution, 2)),
                expected_sell_through=float(round(opp.sell_through_probability, 4)),
                expected_cancellation_prob=(
                    float(round(opp.predicted_cancellation_prob, 4))
                    if opp.predicted_cancellation_prob is not None else None
                ),
                currency=opp.currency,
                selection_status="SELECTED",
                selection_rationale=rationale
            )
            recommendations.append(rec)

        # 2. Analyze Constraint Saturation for Rejection Attribution
        # Destination absorption
        dest_procured_units: Dict[Tuple[str, str], int] = defaultdict(int)
        supplier_spend: Dict[str, float] = defaultdict(float)

        for opp_id, qty in solver_result.selected_quantities.items():
            if opp_id in cand_map:
                c = cand_map[opp_id]
                dest_procured_units[(c.destination_id, c.inventory_type)] += qty
                supplier_spend[c.supplier_id] += qty * c.unit_cost

        sup_cap_threshold = (
            config.risk.supplier_concentration_limit * config.total_budget
            if config.risk.enable_supplier_concentration else float("inf")
        )

        selected_set = set(solver_result.selected_quantities.keys())

        # 3. Process Unselected Active Opportunities
        for opp in opportunities:
            if opp.opportunity_id in selected_set:
                continue

            reason_code = RejectionReasonCode.NOT_SELECTED_BY_OPTIMAL_ALLOCATION
            ctx: Dict[str, Any] = {"total_budget": config.total_budget}

            # Check intrinsic economic viability
            if opp.expected_unit_contribution <= 0.0:
                reason_code = RejectionReasonCode.NEGATIVE_CONTRIBUTION
            elif opp.available_quantity <= 0 or opp.available_quantity < opp.minimum_purchase_qty:
                reason_code = RejectionReasonCode.INSUFFICIENT_SUPPLIER_CAPACITY
            elif (opp.minimum_purchase_qty * opp.purchase_cost) > config.total_budget:
                reason_code = RejectionReasonCode.MOQ_EXCEEDS_BUDGET
            elif opp.aggregate_demand_cap is None or opp.aggregate_demand_cap == 0:
                reason_code = RejectionReasonCode.DESTINATION_CAP_BINDING
            elif opp.aggregate_demand_cap is not None and opp.minimum_purchase_qty > opp.aggregate_demand_cap:
                reason_code = RejectionReasonCode.MOQ_EXCEEDS_DEMAND
            else:
                # Check binding portfolio constraints
                # Supplier cap binding?
                current_sup_spend = supplier_spend.get(opp.supplier_id, 0.0)
                if current_sup_spend + (opp.minimum_purchase_qty * opp.purchase_cost) > sup_cap_threshold + 1e-4:
                    reason_code = RejectionReasonCode.SUPPLIER_CAP_BINDING
                # Destination cap binding?
                elif (
                    opp.aggregate_demand_cap is not None and
                    dest_procured_units.get((opp.destination_id, opp.inventory_type), 0) >= opp.aggregate_demand_cap
                ):
                    reason_code = RejectionReasonCode.DESTINATION_CAP_BINDING
                elif opp.purchase_cost <= 0 or opp.selling_price <= 0:
                    reason_code = RejectionReasonCode.INVALID_COMMERCIAL_INPUT

            explanation = ExplanationEngine.build_rejection_explanation(opp, reason_code, ctx)

            rej = RejectedOpportunityRecord(
                opportunity_id=opp.opportunity_id,
                offer_id=opp.offer_id,
                supplier_id=opp.supplier_id,
                inventory_type=opp.inventory_type,
                inventory_id=opp.inventory_id,
                destination_id=opp.destination_id,
                travel_date=opp.travel_date,
                unit_purchase_cost=float(round(opp.purchase_cost, 2)),
                expected_unit_contribution=float(round(opp.expected_unit_contribution, 2)),
                moq=opp.minimum_purchase_qty,
                available_qty=opp.available_quantity,
                rejection_primary_reason=reason_code.value,
                rejection_explanation=explanation
            )
            rejected.append(rej)

        # 4. Process Expired Offers (if provided)
        if expired_offers:
            for exp in expired_offers:
                opp_id = f"EXPIRED_{exp.get('offer_id', 'UNKNOWN')}"
                rej = RejectedOpportunityRecord(
                    opportunity_id=opp_id,
                    offer_id=str(exp.get("offer_id", "UNKNOWN")),
                    supplier_id=str(exp.get("supplier_id", "UNKNOWN")),
                    inventory_type=str(exp.get("inventory_type", "HOTEL")),
                    inventory_id=str(exp.get("inventory_id", "UNKNOWN")),
                    destination_id=str(exp.get("destination_id", "UNKNOWN")),
                    travel_date=str(exp.get("travel_date", "UNKNOWN")),
                    unit_purchase_cost=float(round(float(exp.get("cost_per_unit", 0.0)), 2)),
                    expected_unit_contribution=0.0,
                    moq=int(exp.get("minimum_purchase_quantity", 1)),
                    available_qty=int(exp.get("quantity_available", 0)),
                    rejection_primary_reason=RejectionReasonCode.EXPIRED_OFFER.value,
                    rejection_explanation=(
                        f"Offer expired on or before point-in-time cutoff {config.optimization_timestamp} "
                        f"(valid_until: {exp.get('valid_until', 'N/A')})."
                    )
                )
                rejected.append(rej)

        return recommendations, rejected
