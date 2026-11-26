from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.app.models.schema import (
    Base,
    DeploymentMode,
    FXContractDirection,
    InventoryCategory,
    MLModel,
    MLModelType,
    ModelDeployment,
    PolicyOutcome,
    PolicyRule,
    PolicyScope,
    RiskScenario,
    RiskScenarioType,
    UnitType,
)
from backend.app.schemas.mlops import (
    DriftComputeRequest,
    ModelDeploymentCreateRequest,
)
from backend.app.schemas.policy import PolicyRuleCreateRequest
from backend.app.schemas.risk import CVaROptimizationRequest, RiskScenarioCreateRequest
from backend.app.schemas.supplier_portal import SupplierRatePushOfferItem
from backend.app.schemas.treasury import FXForwardCreateRequest


def test_risk_scenario_correlation_matrix_validation():
    # Valid symmetric correlation matrix
    valid = RiskScenarioCreateRequest(
        scenario_code="CORR_01",
        name="Correlated Shock",
        scenario_type=RiskScenarioType.CORRELATED_MULTIVARIATE,
        correlation_matrix_json={
            "demand": {"demand": 1.0, "fx": -0.6},
            "fx": {"demand": -0.6, "fx": 1.0},
        },
    )
    assert valid.scenario_code == "CORR_01"

    # Non-symmetric must fail
    with pytest.raises(ValidationError):
        RiskScenarioCreateRequest(
            scenario_code="CORR_BAD",
            name="Bad Corr",
            scenario_type=RiskScenarioType.CORRELATED_MULTIVARIATE,
            correlation_matrix_json={
                "demand": {"demand": 1.0, "fx": -0.6},
                "fx": {"demand": 0.4, "fx": 1.0},
            },
        )

    # Diagonal != 1.0 must fail
    with pytest.raises(ValidationError):
        RiskScenarioCreateRequest(
            scenario_code="CORR_DIAG",
            name="Bad Diag",
            scenario_type=RiskScenarioType.CORRELATED_MULTIVARIATE,
            correlation_matrix_json={"demand": {"demand": 0.8}},
        )


def test_cvar_request_bounds_validation():
    with pytest.raises(ValidationError):
        CVaROptimizationRequest(
            confidence_level_alpha=0.5,  # must be > 0.5
            scenario_ids=[1, 2],
        )
    with pytest.raises(ValidationError):
        CVaROptimizationRequest(
            confidence_level_alpha=0.95,
            scenario_ids=[1],  # min_length=2
        )


def test_mlops_shadow_vs_canary_and_drift_validation():
    # SHADOW with non-zero traffic must fail
    with pytest.raises(ValidationError):
        ModelDeploymentCreateRequest(
            model_id=1,
            deployment_mode=DeploymentMode.SHADOW,
            traffic_percentage=10.0,
        )

    # CANARY with zero traffic must fail
    with pytest.raises(ValidationError):
        ModelDeploymentCreateRequest(
            model_id=1,
            deployment_mode=DeploymentMode.CANARY,
            traffic_percentage=0.0,
        )

    # Drift requires >= 10 observations per window
    with pytest.raises(ValidationError):
        DriftComputeRequest(
            model_id=1,
            baseline_window_start=date(2026, 1, 1),
            baseline_window_end=date(2026, 1, 31),
            target_window_start=date(2026, 2, 1),
            target_window_end=date(2026, 2, 28),
            baseline_features={"f1": [1.0, 2.0]},
            target_features={"f1": [1.0, 2.0]},
        )


def test_supplier_rate_push_and_fx_forward_validation():
    # HOTEL with SEAT must fail
    with pytest.raises(ValidationError):
        SupplierRatePushOfferItem(
            offer_id="OFF_1",
            dest_id="GOI",
            inventory_category=InventoryCategory.HOTEL,
            unit_type=UnitType.SEAT,
            unit_cost=Decimal("1000.00"),
            list_price=Decimal("1200.00"),
            moq=1,
            max_capacity=10,
            valid_from=date(2026, 11, 1),
            valid_until=date(2026, 12, 1),
            travel_date=date(2026, 12, 5),
        )

    # Same base and quote currency must fail
    with pytest.raises(ValidationError):
        FXForwardCreateRequest(
            base_currency="INR",
            quote_currency="INR",
            direction=FXContractDirection.BUY_BASE_SELL_QUOTE,
            notional_amount_base=Decimal("10000.00"),
            contracted_forward_rate=Decimal("1.0"),
            trade_date=date(2026, 11, 1),
            maturity_date=date(2026, 12, 1),
            counterparty="HDFC Treasury",
        )


def test_policy_ast_blocks_unsafe_operators_and_deep_nesting():
    # Disallowed operator (e.g. eval / python_exec)
    with pytest.raises(ValidationError):
        PolicyRuleCreateRequest(
            rule_code="BAD_OP",
            name="Bad Op",
            scope=PolicyScope.PURCHASE_ORDER_CREATE,
            outcome=PolicyOutcome.BLOCK,
            condition_json={"field": "total_amount_inr", "operator": "eval", "value": "1==1"},
        )

    # Invalid field name characters
    with pytest.raises(ValidationError):
        PolicyRuleCreateRequest(
            rule_code="BAD_FLD",
            name="Bad Field",
            scope=PolicyScope.PURCHASE_ORDER_CREATE,
            outcome=PolicyOutcome.BLOCK,
            condition_json={"field": "total; DROP TABLE users", "operator": "gt", "value": 10},
        )


def test_database_tables_and_constraints(db):
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    expected_new_tables = {
        "risk_scenarios",
        "portfolio_stress_tests",
        "cvar_optimization_records",
        "model_drift_reports",
        "feature_freshness_metrics",
        "model_deployments",
        "shadow_prediction_logs",
        "model_lifecycle_events",
        "retraining_trigger_configs",
        "supplier_verification_profiles",
        "supplier_onboarding_workflows",
        "supplier_api_credentials",
        "supplier_rate_sync_logs",
        "settlement_netting_batches",
        "fx_forward_contracts",
        "currency_exposure_snapshots",
        "hedge_effectiveness_records",
        "margin_protection_rules",
        "fx_alerts",
        "policy_rules",
        "policy_rule_versions",
        "policy_evaluation_logs",
        "policy_exception_requests",
        "compliance_audit_records",
    }
    assert expected_new_tables.issubset(tables)

    # Verify DB check constraint prevents SHADOW deployment with influences_live_decisions=True
    m = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v99.0",
        algorithm="LightGBM",
        artifact_dir="data/models/hotel_cancellation",
        metrics_json={"roc_auc": 0.88},
        training_cutoff_date=date(2026, 11, 1),
        is_champion=False,
    )
    db.add(m)
    db.flush()

    bad_dep = ModelDeployment(
        model_id=m.id,
        model_type=MLModelType.HOTEL_CANCELLATION,
        deployment_mode=DeploymentMode.SHADOW,
        traffic_percentage=0.0,
        influences_live_decisions=True,
    )
    db.add(bad_dep)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
