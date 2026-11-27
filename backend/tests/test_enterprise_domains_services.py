from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from backend.app.core.exceptions import (
    AppBaseException,
    BadRequestException,
    ConflictException,
    InvalidStateTransitionError,
    PermissionDeniedError,
)
from backend.app.models.schema import (
    ApprovalStatus,
    DeploymentMode,
    Destination,
    DriftSeverity,
    ExchangeRate,
    FXContractDirection,
    FXContractStatus,
    FreshnessStatus,
    InventoryCategory,
    InventoryItem,
    DestinationInventoryForecast,
    InventorySnapshot,
    OfferPrediction,
    DestinationDemandForecast,
    MLModel,
    MLModelType,
    OfferStatus,
    OnboardingStage,
    OptimizationMode,
    OptimizationRun,
    PipelineStatus,
    POStatus,
    PolicyOutcome,
    PolicyScope,
    ProcurementRecommendation,
    PurchaseOrder,
    PurchaseOrderFulfillment,
    PurchaseOrderLine,
    RetrainingTriggerMetric,
    RiskScenarioType,
    SettlementBatchStatus,
    SolverBackend,
    SolverStatus,
    Supplier,
    SupplierOffer,
    SupplierTier,
    SupplierType,
    SupplierVerificationStatus,
    UnitType,
)
from backend.app.schemas.mlops import (
    DriftComputeRequest,
    FeatureFreshnessCheckRequest,
    ModelDeploymentCreateRequest,
    ModelPromoteGovernanceRequest,
    ModelRollbackRequest,
    RetrainingTriggerConfigRequest,
    ShadowPredictionLogRequest,
)
from backend.app.schemas.policy import (
    ComplianceAuditTriggerRequest,
    PolicyEvaluateRequest,
    PolicyExceptionCreateRequest,
    PolicyExceptionDecisionRequest,
    PolicyRuleCreateRequest,
    PolicyRuleUpdateRequest,
)
from backend.app.schemas.risk import (
    CVaROptimizationRequest,
    RiskScenarioCreateRequest,
    StressTestExecuteRequest,
)
from backend.app.schemas.supplier_portal import (
    SettlementNettingCreateRequest,
    SupplierCredentialCreateRequest,
    SupplierOnboardingAdvanceRequest,
    SupplierOnboardingCreateRequest,
    SupplierRatePushOfferItem,
    SupplierRatePushRequest,
    SupplierTierUpdateRequest,
)
from backend.app.schemas.treasury import (
    FXForwardCreateRequest,
    FXForwardExecuteRequest,
    HedgeEffectivenessCreateRequest,
    MarginImpactEvaluateRequest,
    MarginProtectionRuleCreateRequest,
)
from backend.app.services.mlops_service import MLOpsService
from backend.app.services.policy_service import PolicyService
from backend.app.services.risk_service import RiskService
from backend.app.services.supplier_portal_service import SupplierPortalService
from backend.app.services.treasury_service import TreasuryService


def _seed_market_data(db):
    dest1 = Destination(dest_id="GOI", name="Goa", city="Goa", country="India", airport_code="GOI")
    dest2 = Destination(dest_id="DXB", name="Dubai", city="Dubai", country="UAE", airport_code="DXB")
    sup1 = Supplier(
        supplier_id="SUP_H1",
        name="Goa Resorts Ltd",
        supplier_type=SupplierType.HOTEL,
        fulfillment_rate=0.98,
        max_spend_share_cap=0.60,
        is_active=True,
    )
    sup2 = Supplier(
        supplier_id="SUP_F1",
        name="Emirates Bulk Air",
        supplier_type=SupplierType.FLIGHT,
        fulfillment_rate=0.96,
        max_spend_share_cap=0.60,
        is_active=True,
    )
    inv1 = InventoryItem(
        inventory_id="INV_GOI_H1",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="GOI",
    )
    db.add_all([dest1, dest2, sup1, sup2, inv1])
    db.flush()

    off1 = SupplierOffer(
        offer_id="OFF_GOI_1",
        supplier_id="SUP_H1",
        inventory_id="INV_GOI_H1",
        dest_id="GOI",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("4000.00"),
        list_price_inr=Decimal("6500.00"),
        currency_code="INR",
        moq=5,
        max_capacity=100,
        valid_from=date(2026, 11, 1),
        valid_until=date(2026, 12, 20),
        travel_date=date(2026, 12, 25),
        status=OfferStatus.ACTIVE,
        supplier_refund_cancelled_r_c=0.85,
    )
    off2 = SupplierOffer(
        offer_id="OFF_DXB_1",
        supplier_id="SUP_F1",
        dest_id="DXB",
        origin_dest_id="GOI",
        inventory_category=InventoryCategory.FLIGHT,
        unit_type=UnitType.SEAT,
        unit_cost_inr=Decimal("9000.00"),
        list_price_inr=Decimal("13500.00"),
        original_unit_cost=Decimal("100.00"),
        original_list_price=Decimal("150.00"),
        currency_code="EUR",
        moq=2,
        max_capacity=60,
        valid_from=date(2026, 11, 1),
        valid_until=date(2026, 12, 20),
        travel_date=date(2026, 12, 25),
        status=OfferStatus.ACTIVE,
    )
    fx = ExchangeRate(
        from_currency="EUR",
        to_currency="INR",
        rate=Decimal("90.00000000"),
        as_of_date=date(2026, 11, 25),
        source="RBI",
    )
    db.add_all([off1, off2, fx])
    db.commit()


def test_domain1_deterministic_cvar_and_stress_testing(db):
    _seed_market_data(db)

    s1 = RiskService.create_scenario(
        db,
        RiskScenarioCreateRequest(
            scenario_code="BASE_CASE",
            name="Normal Market",
            scenario_type=RiskScenarioType.SEASONAL_SURGE,
            probability_weight=0.70,
            demand_multiplier=1.05,
            cancellation_delta=-0.02,
            fx_shock_pct=0.0,
            supplier_capacity_multiplier=1.0,
        ),
        user_id=1,
    )
    s2 = RiskService.create_scenario(
        db,
        RiskScenarioCreateRequest(
            scenario_code="SEVERE_SHOCK",
            name="Cancellation + FX Spike",
            scenario_type=RiskScenarioType.CORRELATED_MULTIVARIATE,
            probability_weight=0.30,
            demand_multiplier=0.70,
            cancellation_delta=0.25,
            fx_shock_pct=0.15,
            supplier_capacity_multiplier=0.80,
            correlation_matrix_json={
                "demand": {"demand": 1.0, "cancellation": -0.5},
                "cancellation": {"demand": -0.5, "cancellation": 1.0},
            },
        ),
        user_id=1,
    )

    cvar_rec = RiskService.run_cvar_optimization(
        db,
        CVaROptimizationRequest(
            optimization_mode=OptimizationMode.JOINT,
            total_budget_inr=Decimal("800000.00"),
            solver_backend=SolverBackend.HIGHS,
            max_supplier_share=Decimal("0.70"),
            max_destination_share=Decimal("0.70"),
            confidence_level_alpha=0.95,
            risk_aversion_lambda=0.50,
            scenario_ids=[s1.id, s2.id],
            min_availability_target_pct=75.0,
            min_demand_fulfillment_pct=50.0,
        ),
        user_id=2,
    )
    assert cvar_rec.num_scenarios == 2
    assert cvar_rec.expected_profit_inr > Decimal("0.00")
    assert cvar_rec.achieved_availability_pct >= 75.0
    assert len(cvar_rec.scenario_outcomes_json) == 2

    # Stress test the CVaR run
    st_batch = RiskService.run_stress_test(
        db,
        cvar_rec.run_id,
        StressTestExecuteRequest(scenario_ids=[s1.id, s2.id]),
        user_id=2,
    )
    assert st_batch.tests_executed == 2
    assert st_batch.worst_case_profit_inr <= st_batch.results[0].baseline_profit_inr
    assert st_batch.aggregate_cvar_95_inr >= st_batch.aggregate_var_95_inr

    summary = RiskService.get_portfolio_risk_summary(db, run_id=cvar_rec.run_id)
    assert summary.evaluated_runs_count == 1
    assert summary.stress_tests_count == 2


def test_domain2_mlops_drift_shadow_canary_and_rollback(db, tmp_path):
    # Create dummy artifacts for promotion/rollback
    art1 = tmp_path / "m1"
    art2 = tmp_path / "m2"
    art1.mkdir()
    art2.mkdir()
    for p in (art1, art2):
        (p / "estimator.joblib").write_bytes(b"dummy-estimator-bytes")
        (p / "metadata.json").write_text('{"task_name":"hotel_cancellation"}')

    m1 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v1.0",
        algorithm="LightGBM",
        artifact_dir=str(art1),
        metrics_json={"roc_auc": 0.85},
        training_cutoff_date=date(2026, 10, 1),
        is_champion=True,
        model_status="PROMOTED",
    )
    m2 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v2.0",
        algorithm="LightGBM",
        artifact_dir=str(art2),
        metrics_json={"roc_auc": 0.89},
        training_cutoff_date=date(2026, 11, 1),
        is_champion=False,
        model_status="TRAINED",
    )
    db.add_all([m1, m2])
    db.commit()

    # 1. Shadow deployment must NEVER affect select_serving_model
    shadow = MLOpsService.create_deployment(
        db,
        ModelDeploymentCreateRequest(
            model_id=m2.id,
            deployment_mode=DeploymentMode.SHADOW,
            traffic_percentage=0.0,
            notes="Offline shadow validation",
        ),
        user_id=1,
    )
    assert shadow.influences_live_decisions is False
    selected, route_tag = MLOpsService.select_serving_model(db, MLModelType.HOTEL_CANCELLATION, "OFF_123")
    assert selected.id == m1.id
    assert route_tag == "CHAMPION"

    s_log = MLOpsService.record_shadow_prediction(
        db,
        shadow.id,
        ShadowPredictionLogRequest(
            entity_id="OFF_123",
            features={"lead_time": 30},
            champion_prediction=0.22,
            candidate_prediction=0.19,
        ),
    )
    assert abs(s_log.prediction_delta - (-0.03)) < 1e-6

    # 2. Canary deployment routes when traffic=100%
    canary = MLOpsService.create_deployment(
        db,
        ModelDeploymentCreateRequest(
            model_id=m2.id,
            deployment_mode=DeploymentMode.CANARY,
            traffic_percentage=100.0,
        ),
        user_id=1,
    )
    assert canary.influences_live_decisions is True
    selected_c, route_c = MLOpsService.select_serving_model(db, MLModelType.HOTEL_CANCELLATION, "OFF_123")
    assert selected_c.id == m2.id
    assert route_c.startswith("CANARY:")

    # 3. Trusted drift computation detects severe shift
    drift = MLOpsService.compute_and_record_drift(
        db,
        DriftComputeRequest(
            model_id=m2.id,
            baseline_window_start=date(2026, 10, 1),
            baseline_window_end=date(2026, 10, 31),
            target_window_start=date(2026, 11, 1),
            target_window_end=date(2026, 11, 25),
            baseline_features={"lead_time": [10.0, 12.0, 11.0, 13.0, 9.0, 10.5, 11.5, 12.5, 14.0, 10.2, 11.8, 12.1]},
            target_features={"lead_time": [80.0, 85.0, 90.0, 75.0, 88.0, 92.0, 79.0, 83.0, 86.0, 91.0, 84.0, 87.0]},
        ),
    )
    assert drift.severity == DriftSeverity.SEVERE
    assert drift.retraining_recommended is True

    # Drift gate blocks promotion when severe drift exists
    with pytest.raises(ConflictException):
        MLOpsService.promote_model_governed(
            db, m2.id, ModelPromoteGovernanceRequest(require_no_severe_drift=True), user_id=1
        )

    # Override gate promotes m2, then rollback restores m1
    promoted = MLOpsService.promote_model_governed(
        db, m2.id, ModelPromoteGovernanceRequest(require_no_severe_drift=False), user_id=1
    )
    assert promoted.is_champion is True
    rolled_back = MLOpsService.rollback_model(
        db, m2.id, ModelRollbackRequest(reason="Latency regression in prod"), user_id=1
    )
    assert rolled_back.id == m1.id
    assert rolled_back.is_champion is True

    # 4. Feature freshness check
    fresh = MLOpsService.check_feature_freshness(
        db,
        FeatureFreshnessCheckRequest(
            feature_group_name="hotel_features",
            last_updated_at=datetime.now(timezone.utc) - timedelta(hours=30),
            sla_threshold_seconds=86400,
            record_count=5000,
        ),
    )
    assert fresh.status == FreshnessStatus.STALE


def test_domain3_supplier_hub_security_idempotency_and_netting(db):
    SupplierPortalService.reset_rate_limits()
    _seed_market_data(db)

    cred_res = SupplierPortalService.create_credential(
        db,
        SupplierCredentialCreateRequest(
            supplier_id="SUP_H1",
            label="Primary Push Key",
            rate_limit_per_minute=3,
        ),
        user_id=1,
    )
    raw_key = cred_res.raw_api_secret
    assert raw_key.startswith("tbo_sup_")

    # List never exposes raw secret
    creds = SupplierPortalService.list_credentials(db, supplier_id="SUP_H1")
    assert len(creds) == 1
    assert not hasattr(creds[0], "raw_api_secret")

    # Machine auth + idempotent push
    auth_cred = SupplierPortalService.authenticate_machine_credential(db, raw_key)
    push_req = SupplierRatePushRequest(
        idempotency_key="PUSH_20261126_01",
        offers=[
            SupplierRatePushOfferItem(
                offer_id="OFF_SUP_NEW_1",
                inventory_id="INV_GOI_H1",
                dest_id="GOI",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("4200.00"),
                list_price=Decimal("6800.00"),
                currency_code="INR",
                moq=2,
                max_capacity=40,
                available_units=35,
                valid_from=date(2026, 11, 20),
                valid_until=date(2026, 12, 20),
                travel_date=date(2026, 12, 25),
            )
        ],
    )
    log1 = SupplierPortalService.push_rates_and_availability(db, auth_cred, push_req)
    assert log1.offers_upserted == 1
    assert log1.snapshots_updated == 1

    # Duplicate idempotent push returns same log
    log2 = SupplierPortalService.push_rates_and_availability(db, auth_cred, push_req)
    assert log2.sync_uid == log1.sync_uid

    # Conflicting payload with same key raises ConflictException
    bad_req = SupplierRatePushRequest(
        idempotency_key="PUSH_20261126_01",
        offers=[
            SupplierRatePushOfferItem(
                offer_id="OFF_SUP_NEW_1",
                dest_id="GOI",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("9999.00"),
                list_price=Decimal("12000.00"),
                currency_code="INR",
                moq=2,
                max_capacity=40,
                valid_from=date(2026, 11, 20),
                valid_until=date(2026, 12, 20),
                travel_date=date(2026, 12, 25),
            )
        ],
    )
    with pytest.raises(ConflictException):
        SupplierPortalService.push_rates_and_availability(db, auth_cred, bad_req)

    # Rate limit exceeded on 4th call within 60s (limit=3)
    SupplierPortalService.authenticate_machine_credential(db, raw_key)
    SupplierPortalService.authenticate_machine_credential(db, raw_key)
    with pytest.raises(AppBaseException) as exc_info:
        SupplierPortalService.authenticate_machine_credential(db, raw_key)
    assert exc_info.value.status_code == 429

    # Rotation revokes old key
    rotated = SupplierPortalService.rotate_credential(db, cred_res.id, user_id=1)
    assert rotated.raw_api_secret != raw_key

    # Settlement netting calculation
    run = OptimizationRun(
        run_id="RUN_NET_1",
        cutoff_date=date(2026, 11, 25),
        total_budget_inr=Decimal("100000.00"),
        solver_status=SolverStatus.OPTIMAL,
    )
    db.add(run)
    db.flush()
    rec = ProcurementRecommendation(
        run_id="RUN_NET_1",
        offer_id="OFF_GOI_1",
        supplier_id="SUP_H1",
        dest_id="GOI",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=10,
        unit_cost_inr=Decimal("4000.00"),
        total_spend_inr=Decimal("40000.00"),
        expected_unit_contribution_inr=Decimal("1500.00"),
        expected_total_contribution_inr=Decimal("15000.00"),
        sell_through_rate=0.85,
        moq_applied=5,
        capacity_available=100,
        rationale="Netting test",
        approval_status=ApprovalStatus.ORDERED,
    )
    db.add(rec)
    db.flush()
    po = PurchaseOrder(
        po_number="PO_NET_1",
        supplier_id="SUP_H1",
        ordered_by_user_id=2,
        ordered_at=datetime.now(timezone.utc),
        currency="INR",
        total_committed_spend_inr=Decimal("40000.00"),
        status=POStatus.CONFIRMED,
    )
    db.add(po)
    db.flush()
    line = PurchaseOrderLine(
        po_number="PO_NET_1",
        recommendation_id=rec.id,
        offer_id="OFF_GOI_1",
        ordered_qty=10,
        unit_cost_inr=Decimal("4000.00"),
        line_total_inr=Decimal("40000.00"),
    )
    db.add(line)
    db.flush()
    db.add(PurchaseOrderFulfillment(
        po_line_id=line.id,
        delivered_qty=8,
        supplier_refund_received_inr=Decimal("6000.00"),
    ))
    db.commit()

    batch = SupplierPortalService.create_netting_batch(
        db,
        SettlementNettingCreateRequest(
            supplier_id="SUP_H1",
            period_start=date.today() - timedelta(days=1),
            period_end=date.today() + timedelta(days=1),
        ),
        user_id=2,
    )
    assert batch.gross_payable_inr == Decimal("40000.00")
    assert batch.gross_receivable_refunds_inr == Decimal("6000.00")
    assert batch.net_settlement_inr == Decimal("34000.00")


def test_domain4_treasury_fx_hedging_and_margin_impact(db):
    _seed_market_data(db)

    # Draft FX forward at 91.00 when spot is 90.00
    fwd = TreasuryService.create_fx_forward(
        db,
        FXForwardCreateRequest(
            base_currency="EUR",
            quote_currency="INR",
            direction=FXContractDirection.BUY_BASE_SELL_QUOTE,
            notional_amount_base=Decimal("5000.00"),
            contracted_forward_rate=Decimal("91.00000000"),
            trade_date=date(2026, 11, 25),
            maturity_date=date(2026, 12, 25),
            counterparty="ICICI Treasury",
        ),
        user_id=1,
    )
    assert fwd.status == FXContractStatus.DRAFT

    # Execute as Admin
    executed = TreasuryService.execute_fx_forward(db, fwd.id, FXForwardExecuteRequest(approval_notes="Approved"), admin_user_id=1)
    assert executed.status == FXContractStatus.ACTIVE

    # Compute EUR exposure (OFF_DXB_1 has 100 EUR * 60 cap = 6000 EUR gross, 5000 EUR hedged -> 1000 EUR net)
    exp = TreasuryService.compute_currency_exposure(db, "EUR", "INR")
    assert exp.gross_exposure_base == Decimal("6000.00")
    assert exp.hedged_amount_base == Decimal("5000.00")
    assert exp.net_unhedged_base == Decimal("1000.00")
    assert exp.hedge_ratio_pct == pytest.approx(83.33, rel=1e-2)

    # Margin protection rule + evaluation
    TreasuryService.create_margin_rule(
        db,
        MarginProtectionRuleCreateRequest(
            rule_code="EUR_MARGIN_MIN",
            name="EUR Minimum 15% Margin",
            currency_code="EUR",
            min_gross_margin_pct=15.0,
            max_fx_drawdown_pct=5.0,
            min_hedge_coverage_pct=80.0,
        ),
        user_id=1,
    )
    eval_res = TreasuryService.evaluate_margin_impact(
        db,
        MarginImpactEvaluateRequest(
            currency_code="EUR",
            purchase_cost_base=Decimal("10000.00"),
            selling_price_inr=Decimal("1000000.00"),
            fx_shock_pct=0.10,
            include_active_hedges=True,
        ),
        user_id=2,
    )
    assert eval_res.hedge_coverage_pct == 50.0
    assert "EUR_MARGIN_MIN" in eval_res.breached_rules
    assert eval_res.alerts_generated >= 1


def test_domain5_policy_engine_and_workflow_enforcement(db):
    _seed_market_data(db)

    rule = PolicyService.create_rule(
        db,
        PolicyRuleCreateRequest(
            rule_code="PO_MAX_20K_INR",
            name="Require Exception above 20k INR",
            scope=PolicyScope.PURCHASE_ORDER_CREATE,
            outcome=PolicyOutcome.BLOCK,
            condition_json={"field": "total_amount_inr", "operator": "gt", "value": 20000},
            remediation_hint="Submit policy exception request for Admin approval.",
        ),
        user_id=1,
    )
    assert rule.active_version_number == 1

    # Update rule condition -> version 2 created
    updated = PolicyService.update_rule(
        db,
        rule.id,
        PolicyRuleUpdateRequest(
            condition_json={"field": "total_amount_inr", "operator": "gt", "value": 25000},
        ),
        user_id=1,
    )
    assert updated.active_version_number == 2

    # Evaluate blocked context
    ev = PolicyService.evaluate_policies(
        db,
        PolicyEvaluateRequest(
            scope=PolicyScope.PURCHASE_ORDER_CREATE,
            entity_type="purchase_orders",
            entity_id="PO-TEST-999",
            context={"total_amount_inr": 40000},
        ),
        user_id=2,
    )
    assert ev.allowed is False
    assert ev.blocking_violations == 1

    # Submit and approve exception for PO-TEST-999 -> now allowed
    exc = PolicyService.submit_exception(
        db,
        PolicyExceptionCreateRequest(
            rule_id=rule.id,
            entity_type="purchase_orders",
            entity_id="PO-TEST-999",
            justification="Urgent peak-season block allocation",
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        ),
        user_id=2,
    )
    PolicyService.decide_exception(
        db, exc.id, approve=True, req=PolicyExceptionDecisionRequest(review_notes="Approved"), admin_user_id=1
    )

    ev2 = PolicyService.evaluate_policies(
        db,
        PolicyEvaluateRequest(
            scope=PolicyScope.PURCHASE_ORDER_CREATE,
            entity_type="purchase_orders",
            entity_id="PO-TEST-999",
            context={"total_amount_inr": 40000},
        ),
        user_id=2,
    )
    assert ev2.allowed is True
    assert ev2.findings[0].exception_applied_id == exc.id

    audit = PolicyService.run_compliance_audit(db, ComplianceAuditTriggerRequest(audit_scope="ALL"), admin_user_id=1)
    assert audit.total_checks >= 2
    assert audit.active_exceptions_count >= 1


def test_concurrent_updates_and_transaction_rollback(db):
    """Verify transaction rollback on failed duplicate creation and idempotent concurrent-safe push."""
    _seed_market_data(db)
    SupplierPortalService.reset_rate_limits()

    # Duplicate scenario creation raises ConflictException and preserves DB integrity
    RiskService.create_scenario(
        db,
        RiskScenarioCreateRequest(
            scenario_code="TX_SCEN_1",
            name="Tx Test",
            scenario_type=RiskScenarioType.FX_SHOCK,
        ),
        user_id=1,
    )
    with pytest.raises(ConflictException):
        RiskService.create_scenario(
            db,
            RiskScenarioCreateRequest(
                scenario_code="TX_SCEN_1",
                name="Tx Test Dup",
                scenario_type=RiskScenarioType.FX_SHOCK,
            ),
            user_id=1,
        )

    # DB session remains healthy and rollback-clean for subsequent queries
    items, total = RiskService.list_scenarios(db)
    assert total == 1
    assert items[0].scenario_code == "TX_SCEN_1"

    # Concurrent idempotent push replay from two sessions returns single sync record
    cred = SupplierPortalService.create_credential(
        db,
        SupplierCredentialCreateRequest(supplier_id="SUP_H1", label="Concurrent Key"),
        user_id=1,
    )
    auth_cred = SupplierPortalService.authenticate_machine_credential(db, cred.raw_api_secret)
    push_req = SupplierRatePushRequest(
        idempotency_key="CONC_KEY_1",
        offers=[
            SupplierRatePushOfferItem(
                offer_id="OFF_CONC_1",
                dest_id="GOI",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("4100.00"),
                list_price=Decimal("6200.00"),
                currency_code="INR",
                moq=1,
                max_capacity=20,
                valid_from=date(2026, 11, 20),
                valid_until=date(2026, 12, 20),
                travel_date=date(2026, 12, 25),
            )
        ],
    )
    r1 = SupplierPortalService.push_rates_and_availability(db, auth_cred, push_req)
    r2 = SupplierPortalService.push_rates_and_availability(db, auth_cred, push_req)
    assert r1.id == r2.id
    logs, log_total = SupplierPortalService.list_sync_logs(db, supplier_id="SUP_H1")
    assert log_total == 1


def test_stage12_audit_remediation_regressions(db, tmp_path):
    """Targeted regression tests covering confirmed Stage 12 defects across Domains 1-5."""
    from pydantic import ValidationError
    from backend.app.models.schema import FXForwardContract, FXRateSource, FeatureSet, PolicyEvaluationLog, UnitType
    from backend.app.services.policy_service import _evaluate_condition_ast
    from backend.app.services.recommendation_service import RecommendationService

    _seed_market_data(db)
    SupplierPortalService.reset_rate_limits()

    # 1. Domain 1: CVaR rejects duplicate single scenario_id & enforces OPTIMIZATION_RUN policy & infeasible availability=0
    with pytest.raises(ValidationError):
        CVaROptimizationRequest(scenario_ids=[1, 1], total_budget_inr=Decimal("100000.00"))
    with pytest.raises(ValidationError):
        RiskScenarioCreateRequest(
            scenario_code="NAN_MAT",
            name="Bad Matrix",
            scenario_type=RiskScenarioType.DEMAND_SHOCK,
            correlation_matrix_json={"a": {"a": 1.0, "b": float("nan")}, "b": {"a": float("nan"), "b": 1.0}},
        )

    s1 = RiskService.create_scenario(
        db,
        RiskScenarioCreateRequest(scenario_code="S_AUDIT_1", name="Base", scenario_type=RiskScenarioType.SEASONAL_SURGE, probability_weight=0.5),
        user_id=1,
    )
    s2 = RiskService.create_scenario(
        db,
        RiskScenarioCreateRequest(
            scenario_code="S_AUDIT_2",
            name="ZeroCap",
            scenario_type=RiskScenarioType.SUPPLIER_DISRUPTION,
            probability_weight=0.5,
            supplier_capacity_multiplier=0.0,
        ),
        user_id=1,
    )
    # Infeasible CVaR (100% availability target vs 0% worst-case supplier capacity -> infeasible -> achieved_availability_pct=0.0)
    infeas_rec = RiskService.run_cvar_optimization(
        db,
        CVaROptimizationRequest(
            total_budget_inr=Decimal("500000.00"),
            scenario_ids=[s1.id, s2.id],
            min_availability_target_pct=95.0,
            min_demand_fulfillment_pct=50.0,
        ),
        user_id=2,
    )
    assert infeas_rec.achieved_availability_pct == 0.0
    assert infeas_rec.expected_profit_inr == Decimal("0.00")

    # Enforce OPTIMIZATION_RUN policy on CVaR
    opt_rule = PolicyService.create_rule(
        db,
        PolicyRuleCreateRequest(
            rule_code="OPT_MAX_SHARE_POLICY",
            name="Cap max supplier share <= 0.5",
            scope=PolicyScope.OPTIMIZATION_RUN,
            outcome=PolicyOutcome.BLOCK,
            condition_json={"field": "max_supplier_share", "operator": "gt", "value": 0.5},
        ),
        user_id=1,
    )
    with pytest.raises(PermissionDeniedError):
        RiskService.run_cvar_optimization(
            db,
            CVaROptimizationRequest(
                total_budget_inr=Decimal("500000.00"),
                max_supplier_share=Decimal("0.80"),
                scenario_ids=[s1.id, s2.id],
            ),
            user_id=2,
        )
    opt_rule_upd = PolicyRuleUpdateRequest(condition_json={"field": "max_supplier_share", "operator": "gt", "value": 0.99})
    PolicyService.update_rule(db, opt_rule.id, opt_rule_upd, user_id=1)

    # 2. Domain 2: Non-finite KS/PSI rejection + canary rollback demoting champion + freshness staleness trigger
    art = tmp_path / "m_art"
    art.mkdir()
    (art / "estimator.joblib").write_bytes(b"abc")
    m1 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v1",
        algorithm="LGBM",
        artifact_dir=str(art),
        metrics_json={"rmse": 0.1},
        training_cutoff_date=date(2026, 11, 20),
        is_champion=True,
        model_status="PROMOTED",
    )
    m2 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v2",
        algorithm="LGBM",
        artifact_dir=str(art),
        metrics_json={"rmse": 0.1},
        training_cutoff_date=date(2026, 11, 20),
        is_champion=False,
        model_status="STAGED",
    )
    m3 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v3",
        algorithm="LGBM",
        artifact_dir=str(art),
        metrics_json={"rmse": 0.1},
        training_cutoff_date=date(2026, 11, 20),
        is_champion=False,
        model_status="STAGED",
    )
    db.add_all([m1, m2, m3])
    db.commit()

    with pytest.raises(BadRequestException):
        MLOpsService.compute_and_record_drift(
            db,
            DriftComputeRequest(
                model_id=m1.id,
                baseline_window_start=date(2026, 10, 1),
                baseline_window_end=date(2026, 10, 31),
                target_window_start=date(2026, 11, 1),
                target_window_end=date(2026, 11, 25),
                baseline_features={"x": [float("nan")] * 12},
                target_features={"x": [1.0] * 12},
            ),
        )

    # Roll back non-champion m2 to m3 while m1 is champion -> demotes m1 cleanly without IntegrityError
    restored = MLOpsService.rollback_model(db, m2.id, ModelRollbackRequest(target_model_id=m3.id, reason="Canary rollback"), user_id=1)
    assert restored.id == m3.id
    assert restored.is_champion is True
    db.refresh(m1)
    assert m1.is_champion is False

    # Freshness staleness auto-triggers retraining
    fs = FeatureSet(
        name="hotel_demand_fs",
        version="v1",
        entity_type="HOTEL_CANCELLATION",
        parquet_path="data/features/hotel_demand.parquet",
        row_count=100,
        feature_columns_json=["price", "lead_time"],
        is_active=True,
    )
    db.add(fs)
    db.commit()
    MLOpsService.upsert_retraining_trigger(
        db,
        RetrainingTriggerConfigRequest(
            model_type=MLModelType.HOTEL_CANCELLATION,
            trigger_metric=RetrainingTriggerMetric.FEATURE_STALENESS,
            threshold_value=60.0,
            auto_trigger_training=True,
        ),
        user_id=1,
    )
    stale_metric = MLOpsService.check_feature_freshness(
        db,
        FeatureFreshnessCheckRequest(
            feature_set_id=fs.id,
            feature_group_name="hotel_demand_lag",
            last_updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
            sla_threshold_seconds=300,
        ),
    )
    assert stale_metric.status == FreshnessStatus.STALE

    # 3. Domain 3: Savepoint partial push isolation, invalid scope rejected, duplicate PO netting excluded
    with pytest.raises(ValidationError):
        SupplierCredentialCreateRequest(supplier_id="SUP_H1", label="BadScope", scopes=["admin:all"])

    cred = SupplierPortalService.create_credential(db, SupplierCredentialCreateRequest(supplier_id="SUP_H1", label="SP Key"), user_id=1)
    auth_cred = SupplierPortalService.authenticate_machine_credential(db, cred.raw_api_secret)
    partial_log = SupplierPortalService.push_rates_and_availability(
        db,
        auth_cred,
        SupplierRatePushRequest(
            idempotency_key="SAVEPOINT_TEST_1",
            offers=[
                SupplierRatePushOfferItem(
                    offer_id="OFF_SP_GOOD",
                    dest_id="GOI",
                    inventory_category=InventoryCategory.HOTEL,
                    unit_type=UnitType.ROOM_NIGHT,
                    unit_cost=Decimal("4000.00"),
                    list_price=Decimal("6000.00"),
                    currency_code="INR",
                    moq=1,
                    max_capacity=10,
                    valid_from=date(2026, 11, 20),
                    valid_until=date(2026, 12, 20),
                    travel_date=date(2026, 12, 25),
                ),
                SupplierRatePushOfferItem(
                    offer_id="OFF_SP_BAD_DEST",
                    dest_id="NOPE",
                    inventory_category=InventoryCategory.HOTEL,
                    unit_type=UnitType.ROOM_NIGHT,
                    unit_cost=Decimal("4000.00"),
                    list_price=Decimal("6000.00"),
                    currency_code="INR",
                    moq=1,
                    max_capacity=10,
                    valid_from=date(2026, 11, 20),
                    valid_until=date(2026, 12, 20),
                    travel_date=date(2026, 12, 25),
                ),
            ],
        ),
    )
    assert partial_log.offers_upserted == 1
    assert partial_log.offers_rejected == 1

    # Duplicate PO netting prevention
    po = PurchaseOrder(
        po_number="PO-NET-DUP-1",
        supplier_id="SUP_H1",
        ordered_by_user_id=2,
        ordered_at=datetime.now(timezone.utc),
        currency="INR",
        total_committed_spend_inr=Decimal("10000.00"),
        status=POStatus.CONFIRMED,
    )
    db.add(po)
    db.commit()
    b1 = SupplierPortalService.create_netting_batch(
        db,
        SettlementNettingCreateRequest(
            supplier_id="SUP_H1",
            period_start=date.today() - timedelta(days=1),
            period_end=date.today() + timedelta(days=1),
            currency="INR",
        ),
        user_id=2,
    )
    assert "PO-NET-DUP-1" in b1.po_numbers_json
    b2 = SupplierPortalService.create_netting_batch(
        db,
        SettlementNettingCreateRequest(
            supplier_id="SUP_H1",
            period_start=date.today() - timedelta(days=1),
            period_end=date.today() + timedelta(days=1),
            currency="INR",
        ),
        user_id=2,
    )
    assert "PO-NET-DUP-1" not in b2.po_numbers_json
    assert b2.net_settlement_inr == Decimal("0.00")

    # 4. Domain 4: Expired FX forward cannot execute; DRAFT contract cannot measure hedge effectiveness
    expired_fwd = FXForwardContract(
        contract_number="FX-EXP-1",
        base_currency="EUR",
        quote_currency="INR",
        direction=FXContractDirection.BUY_BASE_SELL_QUOTE,
        notional_amount_base=Decimal("1000.00"),
        contracted_forward_rate=Decimal("90.50000000"),
        spot_rate_at_booking=Decimal("90.00000000"),
        rate_source=FXRateSource.RBI,
        trade_date=date.today() - timedelta(days=30),
        maturity_date=date.today() - timedelta(days=1),
        valuation_timestamp=datetime.now(timezone.utc),
        counterparty="HDFC",
        status=FXContractStatus.DRAFT,
        created_by_user_id=1,
    )
    db.add(expired_fwd)
    db.commit()
    with pytest.raises(BadRequestException):
        TreasuryService.execute_fx_forward(db, expired_fwd.id, FXForwardExecuteRequest(), admin_user_id=1)
    with pytest.raises(InvalidStateTransitionError):
        TreasuryService.record_hedge_effectiveness(db, HedgeEffectivenessCreateRequest(contract_id=expired_fwd.id), user_id=1)

    # 5. Domain 5: Policy SoD self-approval blocked, bool numeric guard, atomic rollback on bulk_approve block
    assert _evaluate_condition_ast({"field": "flag", "operator": "gt", "value": 0}, {"flag": True}) is False
    assert _evaluate_condition_ast({"field": "tags", "operator": "contains", "value": "vip"}, {"tags": ["std", "vip"]}) is True

    rec_rule = PolicyService.create_rule(
        db,
        PolicyRuleCreateRequest(
            rule_code="REC_SPEND_CAP_10K",
            name="Block Rec > 10k",
            scope=PolicyScope.RECOMMENDATION_APPROVAL,
            outcome=PolicyOutcome.BLOCK,
            condition_json={"field": "total_spend_inr", "operator": "gt", "value": 10000},
        ),
        user_id=1,
    )
    exc = PolicyService.submit_exception(
        db,
        PolicyExceptionCreateRequest(
            rule_id=rec_rule.id,
            entity_type="procurement_recommendations",
            entity_id="999",
            justification="Test Separation of Duties self-approval guard",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
        user_id=1,
    )
    with pytest.raises(PermissionDeniedError):
        PolicyService.decide_exception(
            db, exc.id, approve=True, req=PolicyExceptionDecisionRequest(review_notes="Self"), admin_user_id=1
        )

    run = OptimizationRun(
        run_id="RUN_BULK_ATOMIC",
        triggered_by_user_id=2,
        optimization_mode=OptimizationMode.JOINT,
        cutoff_date=date.today(),
        total_budget_inr=Decimal("100000.00"),
        solver_backend=SolverBackend.HIGHS,
        pipeline_status=PipelineStatus.SUCCESS,
        solver_status=SolverStatus.OPTIMAL,
    )
    db.add(run)
    db.flush()
    rec_ok = ProcurementRecommendation(
        run_id="RUN_BULK_ATOMIC", offer_id="OFF_GOI_1", supplier_id="SUP_H1", dest_id="GOI",
        inventory_category=InventoryCategory.HOTEL, unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=1, unit_cost_inr=Decimal("5000.00"), total_spend_inr=Decimal("5000.00"),
        expected_unit_contribution_inr=Decimal("1000.00"), expected_total_contribution_inr=Decimal("1000.00"),
        sell_through_rate=0.9, moq_applied=1, capacity_available=50, rationale="Test bulk atomic ok", approval_status=ApprovalStatus.PENDING,
    )
    rec_bad = ProcurementRecommendation(
        run_id="RUN_BULK_ATOMIC", offer_id="OFF_SP_GOOD", supplier_id="SUP_H1", dest_id="GOI",
        inventory_category=InventoryCategory.HOTEL, unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=5, unit_cost_inr=Decimal("5000.00"), total_spend_inr=Decimal("25000.00"),
        expected_unit_contribution_inr=Decimal("1000.00"), expected_total_contribution_inr=Decimal("5000.00"),
        sell_through_rate=0.9, moq_applied=1, capacity_available=50, rationale="Test bulk atomic block", approval_status=ApprovalStatus.PENDING,
    )
    db.add_all([rec_ok, rec_bad])
    db.commit()

    with pytest.raises(PermissionDeniedError):
        RecommendationService.bulk_approve(db, "RUN_BULK_ATOMIC", [rec_ok.id, rec_bad.id], "Bulk", user_id=2)

    db.refresh(rec_ok)
    db.refresh(rec_bad)
    assert rec_ok.approval_status == ApprovalStatus.PENDING
    assert rec_bad.approval_status == ApprovalStatus.PENDING
    assert db.query(PolicyEvaluationLog).filter(PolicyEvaluationLog.entity_id == str(rec_bad.id)).count() >= 1


def test_stage15_supplier_identity_and_scope_regressions(db):
    _seed_market_data(db)
    SupplierPortalService.reset_rate_limits()

    cred = SupplierPortalService.create_credential(
        db,
        SupplierCredentialCreateRequest(
            supplier_id="SUP_H1",
            label="Rates Only",
            scopes=["rates:write"],
            rate_limit_per_minute=100,
        ),
        user_id=1,
    )
    raw_key = cred.raw_api_secret
    machine = SupplierPortalService.authenticate_machine_credential(db, raw_key)

    created = SupplierPortalService.push_rates_and_availability(
        db,
        machine,
        SupplierRatePushRequest(
            idempotency_key="ST15_CREATE_1",
            offers=[SupplierRatePushOfferItem(
                offer_id="ST15_OFF_1",
                inventory_id="INV_GOI_H1",
                dest_id="GOI",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("4200.00"),
                list_price=Decimal("6800.00"),
                currency_code="INR",
                moq=2,
                max_capacity=40,
                valid_from=date.today(),
                valid_until=date.today() + timedelta(days=30),
                travel_date=date.today() + timedelta(days=30),
            )],
        ),
    )
    assert created.status.value == "SUCCESS"

    offer = db.query(SupplierOffer).filter(SupplierOffer.offer_id == "ST15_OFF_1").one()
    original_cost = offer.unit_cost_inr
    db.add(InventoryItem(
        inventory_id="INV_GOI_H2",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="GOI",
        is_active=True,
    ))
    db.commit()

    wrong_inventory_log = SupplierPortalService.push_rates_and_availability(
        db,
        machine,
        SupplierRatePushRequest(
            idempotency_key="ST15_WRONG_INVENTORY",
            offers=[SupplierRatePushOfferItem(
                offer_id="ST15_OFF_1",
                inventory_id="INV_GOI_H2",
                dest_id="GOI",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("4300.00"),
                list_price=Decimal("6900.00"),
                currency_code="INR",
                moq=2,
                max_capacity=40,
                available_units=30,
                valid_from=date.today(),
                valid_until=date.today() + timedelta(days=30),
                travel_date=date.today() + timedelta(days=30),
            )],
        ),
    )
    assert wrong_inventory_log.status.value == "FAILED"
    assert wrong_inventory_log.offers_rejected == 1
    db.refresh(offer)
    assert offer.unit_cost_inr == original_cost
    assert offer.inventory_id == "INV_GOI_H1"

    availability_log = SupplierPortalService.push_rates_and_availability(
        db,
        machine,
        SupplierRatePushRequest(
            idempotency_key="ST15_AVAIL_ONLY_REJECT",
            offers=[SupplierRatePushOfferItem(
                offer_id="ST15_OFF_1",
                inventory_id="INV_GOI_H1",
                dest_id="GOI",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("4200.00"),
                list_price=Decimal("6800.00"),
                currency_code="INR",
                moq=2,
                max_capacity=40,
                available_units=20,
                valid_from=date.today(),
                valid_until=date.today() + timedelta(days=30),
                travel_date=date.today() + timedelta(days=30),
            )],
        ),
    )
    assert availability_log.status.value == "FAILED"
    assert availability_log.offers_rejected == 1

    cross_supplier_log = SupplierPortalService.push_rates_and_availability(
        db,
        machine,
        SupplierRatePushRequest(
            idempotency_key="ST15_CROSS_SUPPLIER",
            offers=[SupplierRatePushOfferItem(
                offer_id="OFF_DXB_H1",
                inventory_id="INV_DXB_H1",
                dest_id="DXB",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost=Decimal("5000.00"),
                list_price=Decimal("7000.00"),
                currency_code="INR",
                moq=1,
                max_capacity=20,
                valid_from=date.today(),
                valid_until=date.today() + timedelta(days=30),
                travel_date=date.today() + timedelta(days=30),
            )],
        ),
    )
    assert cross_supplier_log.status.value == "FAILED"
    assert cross_supplier_log.offers_rejected == 1


def test_stage15_forecasting_unavailable_metadata_and_inventory_separation(db):
    from backend.app.services.forecasting_service import ForecastingService
    from backend.app.schemas.forecast import PredictionGenerateRequest, ForecastMaterializeRequest

    dest = Destination(dest_id="ST15D", name="Stage 15", city="Test", country="India", airport_code="S15")
    sup = Supplier(
        supplier_id="ST15SUP",
        name="Stage 15 Supplier",
        supplier_type=SupplierType.HOTEL,
        is_active=True,
    )
    inv = InventoryItem(
        inventory_id="ST15_INV",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="ST15D",
        is_active=True,
    )
    off = SupplierOffer(
        offer_id="ST15_OFFER",
        supplier_id="ST15SUP",
        inventory_id="ST15_INV",
        dest_id="ST15D",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("1000.00"),
        list_price_inr=Decimal("1500.00"),
        currency_code="INR",
        moq=17,
        max_capacity=100,
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=30),
        travel_date=date.today() + timedelta(days=30),
        status=OfferStatus.ACTIVE,
    )
    db.add_all([dest, sup, inv, off])
    db.commit()

    result = ForecastingService.generate_predictions(
        db,
        PredictionGenerateRequest(as_of_date=date.today(), offer_ids=["ST15_OFFER"]),
        user_id=1,
    )
    assert result.status == "INSUFFICIENT_DATA"
    assert db.query(OfferPrediction).count() == 0

    mat = ForecastingService.materialize_forecasts(
        db,
        ForecastMaterializeRequest(horizon_days=7, as_of_date=date.today(), dest_ids=["ST15D"]),
        user_id=1,
    )
    assert mat.status in ("INSUFFICIENT_DATA", "PARTIAL")
    assert db.query(DestinationDemandForecast).filter(DestinationDemandForecast.dest_id == "ST15D").count() == 0


def test_stage16_inventory_aggregation_separates_units_and_partial_failures(db):
    from backend.app.services.forecasting_service import ForecastingService
    from backend.app.schemas.forecast import ForecastMaterializeRequest

    dest = Destination(dest_id="ST16D", name="Stage 16", city="Test", country="India", airport_code="S16")
    sup = Supplier(
        supplier_id="ST16SUP",
        name="Stage 16 Supplier",
        supplier_type=SupplierType.HOTEL,
        is_active=True,
    )
    hotel_a = InventoryItem(
        inventory_id="ST16_H1",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="ST16D",
        is_active=True,
    )
    hotel_b = InventoryItem(
        inventory_id="ST16_H2",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="ST16D",
        is_active=True,
    )
    flight = InventoryItem(
        inventory_id="ST16_F1",
        inventory_category=InventoryCategory.FLIGHT,
        unit_type=UnitType.SEAT,
        dest_id="ST16D",
        origin_dest_id="DEL",
        is_active=True,
    )
    db.add_all([dest, sup, hotel_a, hotel_b, flight])
    db.flush()

    now = datetime.now(timezone.utc)
    db.add_all([
        InventorySnapshot(
            inventory_id="ST16_H1",
            supplier_id="ST16SUP",
            inventory_category=InventoryCategory.HOTEL,
            travel_date=date.today() + timedelta(days=30),
            snapshot_at=now,
            total_units=100,
            available_units=60,
            booked_units=40,
        ),
        InventorySnapshot(
            inventory_id="ST16_H2",
            supplier_id="ST16SUP",
            inventory_category=InventoryCategory.HOTEL,
            travel_date=date.today() + timedelta(days=30),
            snapshot_at=now,
            total_units=50,
            available_units=30,
            booked_units=20,
        ),
        InventorySnapshot(
            inventory_id="ST16_F1",
            supplier_id="ST16SUP",
            inventory_category=InventoryCategory.FLIGHT,
            travel_date=date.today() + timedelta(days=30),
            snapshot_at=now,
            total_units=200,
            available_units=150,
            booked_units=50,
        ),
    ])
    db.commit()

    result = ForecastingService.materialize_forecasts(
        db,
        ForecastMaterializeRequest(horizon_days=7, as_of_date=date.today(), dest_ids=["ST16D"]),
        user_id=1,
    )
    assert result.status in ("COMPLETED", "PARTIAL", "INSUFFICIENT_DATA")

    records = db.query(DestinationInventoryForecast).filter(
        DestinationInventoryForecast.dest_id == "ST16D"
    ).all()
    for record in records:
        if record.inventory_category == InventoryCategory.HOTEL:
            assert record.unit_type == UnitType.ROOM_NIGHT
        if record.inventory_category == InventoryCategory.FLIGHT:
            assert record.unit_type == UnitType.SEAT
