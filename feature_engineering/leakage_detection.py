"""
TBO InventoryIQ - Target Leakage Audit & Quarantine Engine (Phase 3)
Systematically evaluates every engineered feature against prediction cutoff timestamps,
quarantining post-event outcome variables and circular formula identities.
"""

from typing import Dict, List, Any
import pandas as pd
from feature_engineering.config import LEAKAGE_EXCLUSIONS


def audit_feature_leakage(
    dataset_name: str,
    feature_name: str,
    target_variable: str,
    prediction_context: str,
) -> Dict[str, Any]:
    """
    Evaluates an individual feature against temporal cutoff and target leakage rules.
    """
    quarantined = LEAKAGE_EXCLUSIONS.get(dataset_name, [])

    # Default evaluation
    risk = "None"
    decision = "Include"
    reason = "Feature observed prior to prediction cutoff; zero target information."

    # Specific Domain Rules (checked first for domain-tailored reasoning)
    if dataset_name == "hotel_cancellation_features":
        if feature_name in ["market_segment_historical_cancel_rate", "deposit_type_historical_cancel_rate"]:
            risk = "High / Global Target Leakage"
            decision = "Quarantined / Analytical Reference Only"
            reason = "Calculated using target averages from complete dataset across train/val/test splits. Preserved as analytical reference; excluded from model inputs."
        elif "reservation_status" in feature_name:
            risk = "Critical / Direct Leakage"
            decision = "Quarantined / Excluded"
            reason = "Encodes checkout or cancellation state after checkout date."
        elif feature_name in ["assigned_room_type", "room_type_changed"]:
            risk = "Critical / Post-Booking Operational Outcome"
            decision = "Quarantined / Excluded"
            reason = "Operational room assignment occurs at check-in/night audit; unavailable at booking transaction time."
        elif feature_name == "booking_changes":
            risk = "Medium / Post-Booking Modification"
            decision = "Include with Caution"
            reason = "Modifications occur between booking creation and arrival; valid for dynamic monitoring but excluded from Day-0 transaction models."
        elif feature_name == "adr":
            risk = "Low"
            decision = "Include"
            reason = "Contracted rate agreed at booking time prior to check-in."

    elif dataset_name == "flight_price_features":
        if feature_name == target_variable:
            risk = "Target Variable"
            decision = "Target Only"
            reason = "Supervised regression label; excluded from input feature matrix."
        elif feature_name == "price_log":
            risk = "Critical / Direct Target Transform"
            decision = "Quarantined / Excluded"
            reason = "Log transformation of target regression price; must never enter inputs."
        elif feature_name == "price_record_id":
            risk = "Metadata Identifier"
            decision = "Excluded Identifier"
            reason = "Synthetic surrogate identifier; excluded from model features."

    elif dataset_name == "flight_operations_features":
        if feature_name in ["is_cancelled", "is_diverted", "arrival_delay_minutes", "departure_delay_minutes", "is_ontime_arrival"]:
            risk = "Critical / Post-Flight Operational Outcome"
            decision = "Quarantined / Excluded"
            reason = "Observed only after scheduled flight departure/arrival; unavailable at booking/procurement time."

    elif dataset_name == "customer_demand_features":
        if feature_name in ["clicked", "booking_completed", "has_funnel_anomaly"]:
            risk = "Critical for Search Volume"
            decision = "Business Metric Only / Quarantined for Volume"
            reason = "Funnel outcomes occur after search submission; cannot predict forward search initiation."

    elif dataset_name == "inventory_features":
        if "prev_" in feature_name or "change_in_" in feature_name or "velocity" in feature_name:
            risk = "Temporal Lag"
            decision = "Include (Strict Past Lags Only)"
            reason = "Computed strictly on historical snapshots prior to current snapshot_date."

    elif dataset_name == "supplier_profitability_features":
        if feature_name in ["gross_margin_percentage", "markup_percentage"]:
            risk = "Deterministic Metric"
            decision = "Business Metric / Analytical Target"
            reason = "Deterministic formula from purchase_cost and selling_price; do not predict from inputs."

    # General Quarantined Fallback
    elif feature_name in quarantined:
        risk = "Critical / Post-Event Leakage"
        decision = "Quarantined / Excluded"
        reason = f"Occurs after the event or directly encodes the target outcome ({target_variable})."

    return {
        "dataset_name": dataset_name,
        "feature_name": feature_name,
        "target_variable": target_variable,
        "prediction_context": prediction_context,
        "leakage_risk": risk,
        "final_decision": decision,
        "rationale": reason,
    }


def run_full_leakage_audit(datasets_feature_map: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """
    Executes leakage audit across all candidate feature datasets.
    """
    targets = {
        "hotel_cancellation_features": ("is_canceled", "Booking Creation Time (Pre-Arrival)"),
        "flight_price_features": ("price", "Flight Search Quote Time (Pre-Departure)"),
        "customer_demand_features": ("search_volume", "Prior Time-Window Horizon"),
        "inventory_features": ("available_quantity", "Snapshot Observation Date"),
        "supplier_profitability_features": ("gross_margin_percentage", "Wholesale Procurement Window"),
        "flight_operations_features": ("ARRIVAL_DELAY", "Scheduled Flight Departure Time"),
        "market_demand_features": ("demand_index", "Seasonal Travel Date"),
    }

    audit_records = []
    for ds_name, features in datasets_feature_map.items():
        target_var, context = targets.get(ds_name, ("N/A", "General Analytical Grain"))
        for feat in features:
            audit_records.append(
                audit_feature_leakage(ds_name, feat, target_var, context)
            )

    return audit_records
