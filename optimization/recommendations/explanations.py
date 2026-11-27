"""
optimization/recommendations/explanations.py

Generates explainable, evidence-backed rationales for procurement decisions.
Produces non-fabricated explanations combining economic, ML risk, and capacity factors.
"""

from typing import Dict, Any, Optional
from optimization.schemas import ProcurementOpportunity, CandidateOffer, SolverResult
from optimization.config import OptimizationConfig
from optimization.recommendations.rejection_reasons import RejectionReasonCode


class ExplanationEngine:
    """Produces human-readable, auditable rationales for selected and rejected opportunities."""

    @staticmethod
    def build_selection_rationale(
        opp: ProcurementOpportunity,
        quantity: int,
        solver_result: SolverResult,
        config: OptimizationConfig
    ) -> str:
        """Constructs an explainable rationale for a recommended procurement."""
        inv_type = opp.inventory_type
        unit = opp.unit_type.lower()
        contrib = opp.expected_unit_contribution
        total_profit = quantity * contrib
        spend = quantity * opp.purchase_cost
        currency = opp.currency

        if inv_type == "HOTEL":
            sell_pct = opp.sell_through_probability * 100.0
            if opp.predicted_cancellation_prob is not None:
                cancel_desc = f"Model estimated {opp.predicted_cancellation_prob * 100.0:.1f}% cancellation risk"
            else:
                prior_pct = config.risk.hotel_default_cancellation_prior * 100.0
                cancel_desc = f"Baseline prior cancellation assumption ({prior_pct:.1f}%) applied (no guest-cohort booking attributes)"
            return (
                f"Selected {quantity} {unit}s from supplier {opp.supplier_id} for destination {opp.destination_id}. "
                f"Expected net contribution is +{currency} {contrib:,.2f}/unit (+{currency} {total_profit:,.2f} total) "
                f"at {spend:,.2f} {currency} spend. "
                f"Offer satisfies MOQ ({opp.minimum_purchase_qty}) and capacity ({opp.available_quantity}). "
                f"{cancel_desc} with {sell_pct:.1f}% sell-through."
            )
        else:
            sell_pct = opp.sell_through_probability * 100.0
            salvage_mode = "10% contractual salvage" if config.use_flight_salvage_optional else "0% baseline spoilage"
            return (
                f"Selected {quantity} {unit}s from supplier {opp.supplier_id} for destination {opp.destination_id}. "
                f"Expected net contribution is +{currency} {contrib:,.2f}/unit (+{currency} {total_profit:,.2f} total) "
                f"at {spend:,.2f} {currency} spend under {salvage_mode}. "
                f"Offer satisfies MOQ ({opp.minimum_purchase_qty}) and capacity ({opp.available_quantity}) "
                f"with {sell_pct:.1f}% market sell-through."
            )

    @staticmethod
    def build_rejection_explanation(
        opp: ProcurementOpportunity,
        reason_code: RejectionReasonCode,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Constructs an accurate explanation detailing why an opportunity was not selected."""
        ctx = context or {}
        currency = opp.currency

        if reason_code == RejectionReasonCode.NEGATIVE_CONTRIBUTION:
            return (
                f"Expected net contribution is negative ({currency} {opp.expected_unit_contribution:,.2f}/unit). "
                f"Procuring this inventory would yield a net financial loss under audited commercial terms."
            )
        elif reason_code == RejectionReasonCode.MOQ_EXCEEDS_BUDGET:
            moq_cost = opp.minimum_purchase_qty * opp.purchase_cost
            budget = ctx.get("total_budget", 0.0)
            return (
                f"Minimum Order Quantity ({opp.minimum_purchase_qty} units) requires {currency} {moq_cost:,.2f}, "
                f"which exceeds the total available procurement budget of {currency} {budget:,.2f}."
            )
        elif reason_code == RejectionReasonCode.MOQ_EXCEEDS_DEMAND:
            demand = opp.aggregate_demand_cap
            demand_str = f"{demand} units" if demand is not None else "unavailable"
            return (
                f"Minimum Order Quantity ({opp.minimum_purchase_qty} units) exceeds the destination "
                f"historical demand ceiling ({demand_str}). Procuring would violate demand absorption limits."
            )
        elif reason_code == RejectionReasonCode.INSUFFICIENT_SUPPLIER_CAPACITY:
            return (
                f"Available inventory quantity is 0 or less than the required minimum purchase quantity "
                f"(available: {opp.available_quantity}, MOQ: {opp.minimum_purchase_qty})."
            )
        elif reason_code == RejectionReasonCode.DESTINATION_CAP_BINDING:
            if opp.aggregate_demand_cap is None:
                return (
                    f"Destination {opp.destination_id} has no valid customer search history or demand forecast. "
                    "Procurement is blocked until demand data becomes available."
                )
            elif opp.aggregate_demand_cap == 0:
                return (
                    f"Destination {opp.destination_id} has a forecasted demand absorption limit of 0 units. "
                    "Procurement is blocked due to zero demand."
                )
            return (
                f"Destination {opp.destination_id} aggregate demand ceiling was exhausted by competing offers "
                f"providing higher expected contribution density."
            )
        elif reason_code == RejectionReasonCode.SUPPLIER_CAP_BINDING:
            return (
                f"Supplier {opp.supplier_id} concentration limit reached. Additional procurement would exceed "
                f"portfolio supplier risk constraints."
            )
        elif reason_code == RejectionReasonCode.CATEGORY_BUDGET_LIMIT:
            return (
                f"Category budget limit for {opp.inventory_type} was reached by higher-priority opportunities."
            )
        elif reason_code == RejectionReasonCode.EXPIRED_OFFER:
            return (
                f"Offer validity expired on or before the point-in-time optimization cutoff ({opp.offer_valid_until})."
            )
        elif reason_code == RejectionReasonCode.INVALID_CURRENCY:
            return (
                f"Offer currency '{currency}' does not match the target procurement currency or violates "
                f"currency validation rules."
            )
        elif reason_code == RejectionReasonCode.INVALID_COMMERCIAL_INPUT:
            return (
                f"Invalid commercial data (non-positive cost or selling price: cost={opp.purchase_cost}, price={opp.selling_price})."
            )
        else:
            return (
                f"Not selected in the optimal portfolio allocation. Other candidate offers provided higher expected "
                f"contribution density within the available budget and portfolio constraints."
            )
