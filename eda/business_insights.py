"""
TBO InventoryIQ - Business Insights & Procurement Intelligence Engine (Phase 2)
Synthesizes analytical discoveries into actionable procurement strategies,
margin optimization guidelines, overbooking buffers, and inventory holding rules.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np


def extract_high_priority_procurement_targets(demand_supply_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Identifies destinations with acute supply deficits relative to active search demand.
    These represent prime procurement opportunities where immediate inventory purchase
    can capture unmet customer booking demand.
    """
    constrained = demand_supply_df[
        (demand_supply_df["demand_to_supply_ratio"] > 1.2)
    ].sort_values(by="demand_to_supply_ratio", ascending=False)

    return constrained.head(10).to_dict(orient="records")


def extract_inventory_risk_warnings(demand_supply_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Identifies over-supplied or low-demand destinations where procurement should be paused,
    or promotional discounting applied to avoid unsold perishable inventory.
    """
    over_supplied = demand_supply_df[
        (demand_supply_df["demand_to_supply_ratio"] < 0.6) & (demand_supply_df["available_units"] > 20)
    ].sort_values(by="demand_to_supply_ratio", ascending=True)

    return over_supplied.head(10).to_dict(orient="records")


def synthesize_supplier_competitiveness(supplier_kpis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ranks suppliers based on average profit margins, volume, and refundability.
    """
    suppliers = supplier_kpis.get("supplier_breakdown", [])
    if not suppliers:
        return {"status": "no_supplier_data"}

    # Sort suppliers by margin percentage descending
    sorted_by_margin = sorted(suppliers, key=lambda s: s.get("avg_margin_pct", 0), reverse=True)
    preferred_partner = sorted_by_margin[0] if sorted_by_margin else {}

    return {
        "highest_margin_supplier": preferred_partner.get("supplier_id"),
        "highest_margin_pct": round(preferred_partner.get("avg_margin_pct", 0), 2),
        "overall_avg_margin_pct": supplier_kpis.get("avg_margin_pct", 0),
        "negative_margin_leakage_pct": supplier_kpis.get("negative_margin_pct", 0),
        "refundable_inventory_share_pct": supplier_kpis.get("refundable_offers_pct", 0),
        "recommended_supplier_strategy": (
            "Prioritize procurement with top-margin suppliers who offer refundable contracts. "
            "Implement automated price gating to block negative margin inventory offers."
        ),
    }


def synthesize_cancellation_risk_and_buffers(hotel_kpis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derives overbooking buffers and risk policies based on observed cancellation rates.
    """
    overall_cancel_rate = hotel_kpis.get("cancellation_rate_pct", 0.0)
    avg_lead_time = hotel_kpis.get("avg_lead_time_days", 0.0)

    # Segments with extreme cancellation rates
    segments = hotel_kpis.get("cancellation_by_market_segment", [])
    high_risk_segments = [s for s in segments if s.get("cancellation_rate_pct", 0) > 40.0]

    # Deposit types impact
    deposits = hotel_kpis.get("cancellation_by_deposit_type", [])

    # Recommended overbooking buffer:
    # Safe conservative formula: buffer = overall_cancel_rate * 0.40 (ensures minimal walk risk)
    conservative_buffer_pct = round(overall_cancel_rate * 0.40, 1)

    return {
        "overall_cancellation_rate_pct": overall_cancel_rate,
        "avg_booking_lead_time_days": avg_lead_time,
        "recommended_overbooking_buffer_pct": conservative_buffer_pct,
        "high_risk_market_segments": [s.get("market_segment") for s in high_risk_segments],
        "procurement_cancellation_guideline": (
            f"Given an observed {overall_cancel_rate:.1f}% hotel cancellation rate, procurement agreements "
            f"must demand minimum 7-day cancellation windows or refundable supplier terms. "
            f"Apply an active {conservative_buffer_pct:.1f}% overbooking allowance for non-peak inventory."
        ),
    }


def synthesize_flight_yield_insights(price_kpis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts dynamic flight yield curve insights (days_left surge and cabin multiplier).
    """
    ratio = price_kpis.get("business_to_economy_price_ratio", 1.0)
    corr = price_kpis.get("days_left_price_correlation", 0.0)

    return {
        "business_to_economy_multiplier": ratio,
        "days_left_correlation": corr,
        "procurement_timing_rule": (
            "Flight prices surge significantly as departure approaches (negative days_left correlation). "
            "Advance wholesale block procurement must be secured >30 days before travel to capture maximum yield spread."
        ),
    }


def generate_executive_business_insights(
    demand_supply_df: pd.DataFrame,
    supplier_kpis: Dict[str, Any],
    hotel_kpis: Dict[str, Any],
    flight_price_kpis: Dict[str, Any],
    inventory_kpis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Consolidates executive-level procurement and profit optimization guidance.
    """
    high_priority_targets = extract_high_priority_procurement_targets(demand_supply_df)
    inventory_risk_targets = extract_inventory_risk_warnings(demand_supply_df)
    supplier_insights = synthesize_supplier_competitiveness(supplier_kpis)
    cancellation_insights = synthesize_cancellation_risk_and_buffers(hotel_kpis)
    flight_insights = synthesize_flight_yield_insights(flight_price_kpis)

    return {
        "strategic_summary": "TBO InventoryIQ Phase 2 Analytical & Procurement Intelligence Assessment",
        "top_procurement_destinations": [t.get("destination_id") for t in high_priority_targets[:5]],
        "over_supplied_destinations": [t.get("destination_id") for t in inventory_risk_targets[:5]],
        "supplier_intelligence": supplier_insights,
        "cancellation_and_overbooking": cancellation_insights,
        "flight_procurement_dynamics": flight_insights,
        "inventory_utilization_benchmark_pct": inventory_kpis.get("overall_utilization_rate_pct", 0.0),
        "stockout_frequency_pct": inventory_kpis.get("stockout_frequency_pct", 0.0),
    }
