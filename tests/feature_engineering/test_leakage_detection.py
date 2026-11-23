"""
Tests for Target Leakage Detection & Audit Module
Validates quarantine logic for post-event and operational check-in outcomes.
"""

import pytest
from feature_engineering.leakage_detection import (
    audit_feature_leakage,
    run_full_leakage_audit,
)


def test_audit_feature_leakage_quarantined():
    # reservation_status in hotel cancellation prediction must be quarantined
    res = audit_feature_leakage(
        dataset_name="hotel_cancellation_features",
        feature_name="reservation_status",
        target_variable="is_canceled",
        prediction_context="Booking Creation Time",
    )
    assert "Critical" in res["leakage_risk"]
    assert res["final_decision"] == "Quarantined / Excluded"


def test_audit_feature_leakage_operational_room_type():
    # assigned_room_type occurs at check-in; quarantined for pre-booking models
    res = audit_feature_leakage(
        dataset_name="hotel_cancellation_features",
        feature_name="assigned_room_type",
        target_variable="is_canceled",
        prediction_context="Booking Creation Time (Pre-Arrival)",
    )
    assert "Critical" in res["leakage_risk"] or "High" in res["leakage_risk"]
    assert res["final_decision"] == "Quarantined / Excluded"


def test_audit_feature_leakage_approved():
    # lead_time is valid pre-booking feature
    res = audit_feature_leakage(
        dataset_name="hotel_cancellation_features",
        feature_name="lead_time_days",
        target_variable="is_canceled",
        prediction_context="Booking Creation Time",
    )
    assert res["leakage_risk"] == "None"
    assert res["final_decision"] == "Include"


def test_run_full_leakage_audit():
    feature_map = {
        "hotel_cancellation_features": ["is_canceled", "lead_time_days", "reservation_status", "assigned_room_type"],
        "customer_demand_features": ["search_lead_days", "clicked"],
    }
    audits = run_full_leakage_audit(feature_map)
    assert len(audits) == 6
    decisions = {a["feature_name"]: a["final_decision"] for a in audits}
    assert decisions["lead_time_days"] == "Include"
    assert "Quarantined" in decisions["reservation_status"]
    assert "Quarantined" in decisions["assigned_room_type"]
