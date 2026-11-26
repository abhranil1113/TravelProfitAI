from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from backend.app.core.security import create_access_token
from backend.app.models.schema import (
    Destination,
    ExchangeRate,
    InventoryCategory,
    InventoryItem,
    MLModel,
    MLModelType,
    OfferStatus,
    OptimizationRun,
    ProcurementRecommendation,
    ApprovalStatus,
    SolverStatus,
    Supplier,
    SupplierOffer,
    SupplierType,
    UnitType,
)
from backend.app.services.supplier_portal_service import SupplierPortalService


def _seed_api_fixtures(db):
    dest = Destination(dest_id="BOM", name="Mumbai", city="Mumbai", country="India", airport_code="BOM")
    sup = Supplier(
        supplier_id="SUP_API_1",
        name="Mumbai Hotels Group",
        supplier_type=SupplierType.HOTEL,
        fulfillment_rate=0.95,
        max_spend_share_cap=0.80,
        is_active=True,
    )
    inv = InventoryItem(
        inventory_id="INV_BOM_1",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="BOM",
    )
    db.add_all([dest, sup, inv])
    db.flush()

    off = SupplierOffer(
        offer_id="OFF_BOM_1",
        supplier_id="SUP_API_1",
        inventory_id="INV_BOM_1",
        dest_id="BOM",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("5000.00"),
        list_price_inr=Decimal("7500.00"),
        currency_code="INR",
        moq=2,
        max_capacity=50,
        valid_from=date(2026, 11, 1),
        valid_until=date(2026, 12, 20),
        travel_date=date(2026, 12, 25),
        status=OfferStatus.ACTIVE,
    )
    fx = ExchangeRate(
        from_currency="USD",
        to_currency="INR",
        rate=Decimal("84.00000000"),
        as_of_date=date(2026, 11, 25),
        source="RBI",
    )
    run = OptimizationRun(
        run_id="RUN_API_1",
        cutoff_date=date(2026, 11, 25),
        total_budget_inr=Decimal("500000.00"),
        solver_status=SolverStatus.OPTIMAL,
    )
    db.add_all([off, fx, run])
    db.flush()
    rec = ProcurementRecommendation(
        run_id="RUN_API_1",
        offer_id="OFF_BOM_1",
        supplier_id="SUP_API_1",
        dest_id="BOM",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=10,
        unit_cost_inr=Decimal("5000.00"),
        total_spend_inr=Decimal("50000.00"),
        expected_unit_contribution_inr=Decimal("1500.00"),
        expected_total_contribution_inr=Decimal("15000.00"),
        sell_through_rate=0.85,
        moq_applied=2,
        capacity_available=50,
        rationale="API test",
        approval_status=ApprovalStatus.PENDING,
    )
    m = MLModel(
        model_type=MLModelType.FLIGHT_PRICE,
        version="v1.0",
        algorithm="LightGBM",
        artifact_dir="data/models/flight_price",
        metrics_json={"rmse": 120.0},
        training_cutoff_date=date(2026, 11, 1),
        is_champion=True,
        model_status="PROMOTED",
    )
    m_cand = MLModel(
        model_type=MLModelType.FLIGHT_PRICE,
        version="v2.0",
        algorithm="XGBoost",
        artifact_dir="data/models/flight_price",
        metrics_json={"rmse": 110.0},
        training_cutoff_date=date(2026, 11, 15),
        is_champion=False,
        model_status="TRAINED",
    )
    db.add_all([rec, m, m_cand])
    db.commit()
    return rec.id, m.id, m_cand.id


def test_authentication_failures_missing_invalid_expired_inactive(client):
    # Missing token -> 401
    assert client.get("/api/v1/risk/scenarios").status_code == 401
    # Invalid token -> 401
    assert client.get("/api/v1/risk/scenarios", headers={"Authorization": "Bearer invalid.jwt.token"}).status_code == 401
    # Expired token -> 401
    expired = create_access_token(subject="1", role="ADMIN", expires_delta=timedelta(minutes=-5))
    assert client.get("/api/v1/risk/scenarios", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    # Deactivated user -> 403
    inactive_tok = create_access_token(subject="4", role="ANALYST")
    assert client.get("/api/v1/risk/scenarios", headers={"Authorization": f"Bearer {inactive_tok}"}).status_code == 403


def test_domain1_risk_and_cvar_rbac(client, db, admin_headers, pm_headers, analyst_headers):
    _seed_api_fixtures(db)

    # Admin configures scenarios; PM & Analyst cannot (403)
    payload = {
        "scenario_code": "API_SHOCK_1",
        "name": "API Demand Shock",
        "scenario_type": "DEMAND_SHOCK",
        "probability_weight": 0.4,
        "demand_multiplier": 0.8,
        "cancellation_delta": 0.1,
        "fx_shock_pct": 0.05,
        "supplier_capacity_multiplier": 0.9,
    }
    assert client.post("/api/v1/risk/scenarios", headers=pm_headers, json=payload).status_code == 403
    assert client.post("/api/v1/risk/scenarios", headers=analyst_headers, json=payload).status_code == 403
    r_create = client.post("/api/v1/risk/scenarios", headers=admin_headers, json=payload)
    assert r_create.status_code == 201
    s1_id = r_create.json()["id"]

    s2_id = client.post(
        "/api/v1/risk/scenarios",
        headers=admin_headers,
        json={**payload, "scenario_code": "API_SHOCK_2", "probability_weight": 0.6, "demand_multiplier": 1.1},
    ).json()["id"]

    # All 3 roles can view scenarios and portfolio risk summary
    for hdrs in (admin_headers, pm_headers, analyst_headers):
        assert client.get("/api/v1/risk/scenarios", headers=hdrs).status_code == 200
        assert client.get("/api/v1/risk/portfolio-summary", headers=hdrs).status_code == 200

    # PM can run stress test & CVaR optimization; Analyst cannot (403)
    assert client.post(
        "/api/v1/optimization-runs/RUN_API_1/stress-test",
        headers=analyst_headers,
        json={"scenario_ids": [s1_id]},
    ).status_code == 403
    st_res = client.post(
        "/api/v1/optimization-runs/RUN_API_1/stress-test",
        headers=pm_headers,
        json={"scenario_ids": [s1_id, s2_id]},
    )
    assert st_res.status_code == 201
    assert st_res.json()["tests_executed"] == 2

    assert client.post(
        "/api/v1/optimization-runs/cvar",
        headers=analyst_headers,
        json={"scenario_ids": [s1_id, s2_id], "total_budget_inr": 200000},
    ).status_code == 403
    cvar_res = client.post(
        "/api/v1/optimization-runs/cvar",
        headers=pm_headers,
        json={"scenario_ids": [s1_id, s2_id], "total_budget_inr": 200000, "min_availability_target_pct": 70.0, "min_demand_fulfillment_pct": 50.0},
    )
    assert cvar_res.status_code == 201
    cvar_run_id = cvar_res.json()["run_id"]

    # Analyst can view risk-adjusted comparison
    cmp_res = client.get(
        f"/api/v1/optimization-runs/RUN_API_1/risk-adjusted-comparison?compare_run_ids={cvar_run_id}",
        headers=analyst_headers,
    )
    assert cmp_res.status_code == 200
    assert len(cmp_res.json()["compared_runs"]) == 2


def test_domain2_mlops_rbac_and_worker_token(client, db, admin_headers, pm_headers, analyst_headers, worker_headers):
    _, m_id, m_cand_id = _seed_api_fixtures(db)

    # Drift computation requires monitoring service X-Worker-Token ONLY (Admin/Analyst/PM JWTs rejected!)
    drift_payload = {
        "model_id": m_id,
        "baseline_window_start": "2026-10-01",
        "baseline_window_end": "2026-10-31",
        "target_window_start": "2026-11-01",
        "target_window_end": "2026-11-25",
        "baseline_features": {"price": [100, 102, 104, 98, 99, 101, 103, 105, 97, 100, 102, 101]},
        "target_features": {"price": [150, 155, 160, 148, 152, 158, 162, 149, 154, 157, 159, 153]},
    }
    assert client.post("/api/v1/mlops/drift/compute", headers=admin_headers, json=drift_payload).status_code == 403
    assert client.post("/api/v1/mlops/drift/compute", headers=analyst_headers, json=drift_payload).status_code == 403
    assert client.post("/api/v1/mlops/drift/compute", headers=worker_headers, json=drift_payload).status_code == 201

    # View drift: Admin & Analyst YES, PM NO (403)
    assert client.get("/api/v1/mlops/drift", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/mlops/drift", headers=analyst_headers).status_code == 200
    assert client.get("/api/v1/mlops/drift", headers=pm_headers).status_code == 403

    # View feature freshness: all 3 roles YES
    for hdrs in (admin_headers, analyst_headers, pm_headers):
        assert client.get("/api/v1/mlops/feature-freshness", headers=hdrs).status_code == 200

    # Deployments & retraining triggers: Admin ONLY
    dep_payload = {"model_id": m_cand_id, "deployment_mode": "SHADOW", "traffic_percentage": 0.0}
    assert client.post("/api/v1/mlops/deployments", headers=analyst_headers, json=dep_payload).status_code == 403
    assert client.post("/api/v1/mlops/deployments", headers=pm_headers, json=dep_payload).status_code == 403
    assert client.post("/api/v1/mlops/deployments", headers=admin_headers, json=dep_payload).status_code == 201

    trig_payload = {"model_type": "flight_price", "trigger_metric": "PSI", "threshold_value": 0.25, "auto_trigger_training": True}
    assert client.put("/api/v1/mlops/retraining-triggers", headers=analyst_headers, json=trig_payload).status_code == 403
    assert client.put("/api/v1/mlops/retraining-triggers", headers=admin_headers, json=trig_payload).status_code == 200


def test_domain3_supplier_portal_machine_auth_isolation_and_rbac(client, db, admin_headers, pm_headers, analyst_headers):
    SupplierPortalService.reset_rate_limits()
    _seed_api_fixtures(db)

    # Second supplier for cross-supplier isolation check
    db.add(Supplier(supplier_id="SUP_OTHER", name="Other Supplier", supplier_type=SupplierType.HOTEL))
    db.add(SupplierOffer(
        offer_id="OFF_OTHER_1",
        supplier_id="SUP_OTHER",
        dest_id="BOM",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("3000.00"),
        list_price_inr=Decimal("5000.00"),
        currency_code="INR",
        moq=1,
        max_capacity=20,
        valid_from=date(2026, 11, 1),
        valid_until=date(2026, 12, 20),
        travel_date=date(2026, 12, 25),
    ))
    db.commit()

    # Credentials: Admin only
    cred_req = {"supplier_id": "SUP_API_1", "label": "Portal Key"}
    assert client.post("/api/v1/supplier-portal/credentials", headers=pm_headers, json=cred_req).status_code == 403
    assert client.post("/api/v1/supplier-portal/credentials", headers=analyst_headers, json=cred_req).status_code == 403
    cred_res = client.post("/api/v1/supplier-portal/credentials", headers=admin_headers, json=cred_req)
    assert cred_res.status_code == 201
    raw_secret = cred_res.json()["raw_api_secret"]

    # Human JWT CANNOT call supplier machine push endpoint (401 missing X-Supplier-Key)
    push_body = {
        "idempotency_key": "API_PUSH_1",
        "offers": [{
            "offer_id": "OFF_BOM_1",
            "dest_id": "BOM",
            "inventory_category": "HOTEL",
            "unit_type": "ROOM_NIGHT",
            "unit_cost": "4900.00",
            "list_price": "7500.00",
            "currency_code": "INR",
            "moq": 2,
            "max_capacity": 60,
            "valid_from": "2026-11-01",
            "valid_until": "2026-12-20",
            "travel_date": "2026-12-25",
        }],
    }
    assert client.post("/api/v1/supplier-portal/rates/push", headers=admin_headers, json=push_body).status_code == 401

    # Machine credential pushes successfully
    sup_headers = {"X-Supplier-Key": raw_secret}
    p_res = client.post("/api/v1/supplier-portal/rates/push", headers=sup_headers, json=push_body)
    assert p_res.status_code == 201
    assert p_res.json()["offers_upserted"] == 1

    # Cross-supplier isolation: SUP_API_1 cannot mutate SUP_OTHER's offer
    iso_body = {
        "idempotency_key": "API_PUSH_ISO",
        "offers": [{**push_body["offers"][0], "offer_id": "OFF_OTHER_1"}],
    }
    iso_res = client.post("/api/v1/supplier-portal/rates/push", headers=sup_headers, json=iso_body)
    assert iso_res.status_code == 201
    assert iso_res.json()["offers_rejected"] == 1

    # Sync logs: Admin & PM YES, Analyst NO (403)
    assert client.get("/api/v1/supplier-portal/sync-logs", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/supplier-portal/sync-logs", headers=pm_headers).status_code == 200
    assert client.get("/api/v1/supplier-portal/sync-logs", headers=analyst_headers).status_code == 403

    # Onboarding: Admin only + invalid stage transition check
    assert client.post("/api/v1/supplier-portal/onboarding", headers=pm_headers, json={"supplier_id": "SUP_API_1"}).status_code == 403
    onb = client.post("/api/v1/supplier-portal/onboarding", headers=admin_headers, json={"supplier_id": "SUP_API_1"})
    assert onb.status_code == 201
    onb_id = onb.json()["id"]
    # Skipping straight to APPROVED from INITIATED must fail (400)
    assert client.post(
        f"/api/v1/supplier-portal/onboarding/{onb_id}/advance",
        headers=admin_headers,
        json={"target_stage": "APPROVED"},
    ).status_code == 400


def test_domain4_treasury_rbac(client, db, admin_headers, pm_headers, analyst_headers):
    _seed_api_fixtures(db)

    fx_req = {
        "base_currency": "USD",
        "quote_currency": "INR",
        "direction": "BUY_BASE_SELL_QUOTE",
        "notional_amount_base": "10000.00",
        "contracted_forward_rate": "84.50",
        "trade_date": "2026-11-25",
        "maturity_date": "2026-12-25",
        "counterparty": "SBI FX Desk",
    }
    assert client.post("/api/v1/treasury/fx-contracts", headers=pm_headers, json=fx_req).status_code == 403
    assert client.post("/api/v1/treasury/fx-contracts", headers=analyst_headers, json=fx_req).status_code == 403
    fx_res = client.post("/api/v1/treasury/fx-contracts", headers=admin_headers, json=fx_req)
    assert fx_res.status_code == 201
    cid = fx_res.json()["id"]

    # Execution requires Admin
    assert client.post(f"/api/v1/treasury/fx-contracts/{cid}/execute", headers=pm_headers, json={}).status_code == 403
    assert client.post(f"/api/v1/treasury/fx-contracts/{cid}/execute", headers=admin_headers, json={}).status_code == 200

    # View currency exposure: all 3 roles
    for hdrs in (admin_headers, pm_headers, analyst_headers):
        assert client.get("/api/v1/treasury/exposure", headers=hdrs).status_code == 200

    # Margin rules: Admin manage; PM & Admin evaluate
    rule_req = {
        "rule_code": "USD_MIN_MARGIN",
        "name": "USD Margin Floor",
        "currency_code": "USD",
        "min_gross_margin_pct": 12.0,
        "max_fx_drawdown_pct": 8.0,
    }
    assert client.post("/api/v1/treasury/margin-rules", headers=pm_headers, json=rule_req).status_code == 403
    assert client.post("/api/v1/treasury/margin-rules", headers=admin_headers, json=rule_req).status_code == 201

    eval_req = {"currency_code": "USD", "purchase_cost_base": "1000.00", "selling_price_inr": "100000.00", "fx_shock_pct": 0.05}
    assert client.post("/api/v1/treasury/margin-impact/evaluate", headers=analyst_headers, json=eval_req).status_code == 403
    assert client.post("/api/v1/treasury/margin-impact/evaluate", headers=pm_headers, json=eval_req).status_code == 200


def test_domain5_policy_compliance_rbac_and_workflow_blocking(client, db, admin_headers, pm_headers, analyst_headers):
    rec_id, _, _ = _seed_api_fixtures(db)

    # Rule: BLOCK recommendation approvals when total_spend_inr > 25000
    rule_req = {
        "rule_code": "REC_CAP_25K",
        "name": "Block High-Spend Recommendation",
        "scope": "RECOMMENDATION_APPROVAL",
        "outcome": "BLOCK",
        "condition_json": {"field": "total_spend_inr", "operator": "gt", "value": 25000},
    }
    assert client.post("/api/v1/policy/rules", headers=pm_headers, json=rule_req).status_code == 403
    assert client.post("/api/v1/policy/rules", headers=analyst_headers, json=rule_req).status_code == 403
    r_res = client.post("/api/v1/policy/rules", headers=admin_headers, json=rule_req)
    assert r_res.status_code == 201
    rule_id = r_res.json()["id"]

    # Recommendation approval is BLOCKED (403) by policy engine!
    appr_fail = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        headers=pm_headers,
        json={"decision_notes": "Attempt without exception"},
    )
    assert appr_fail.status_code == 403

    # PM submits exception; Analyst cannot submit (403); PM cannot approve (403)
    exc_req = {
        "rule_id": rule_id,
        "entity_type": "procurement_recommendations",
        "entity_id": str(rec_id),
        "justification": "Strategic Mumbai peak allocation",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
    }
    assert client.post("/api/v1/policy/exceptions", headers=analyst_headers, json=exc_req).status_code == 403
    exc_res = client.post("/api/v1/policy/exceptions", headers=pm_headers, json=exc_req)
    assert exc_res.status_code == 201
    exc_id = exc_res.json()["id"]

    assert client.post(
        f"/api/v1/policy/exceptions/{exc_id}/approve",
        headers=pm_headers,
        json={"review_notes": "Self-approve forbidden"},
    ).status_code == 403

    # Admin approves exception -> now recommendation approval succeeds!
    assert client.post(
        f"/api/v1/policy/exceptions/{exc_id}/approve",
        headers=admin_headers,
        json={"review_notes": "Approved by risk committee"},
    ).status_code == 200

    appr_ok = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        headers=pm_headers,
        json={"decision_notes": "Approved with policy waiver"},
    )
    assert appr_ok.status_code == 200
    assert appr_ok.json()["approval_status"] == "APPROVED"

    # Compliance audit: Admin runs, all 3 roles can view
    assert client.post("/api/v1/compliance/audits", headers=pm_headers, json={"audit_scope": "ALL"}).status_code == 403
    assert client.post("/api/v1/compliance/audits", headers=admin_headers, json={"audit_scope": "ALL"}).status_code == 201
    for hdrs in (admin_headers, pm_headers, analyst_headers):
        assert client.get("/api/v1/compliance/audits", headers=hdrs).status_code == 200


def test_po_policy_enforcement_and_netting_state_transitions(client, db, admin_headers, pm_headers):
    _seed_api_fixtures(db)

    # Policy rule blocking PO creation above 20000 INR
    client.post(
        "/api/v1/policy/rules",
        headers=admin_headers,
        json={
            "rule_code": "PO_CREATE_CAP_20K",
            "name": "Block PO > 20k",
            "scope": "PURCHASE_ORDER_CREATE",
            "outcome": "BLOCK",
            "condition_json": {"field": "total_amount_inr", "operator": "gt", "value": 20000},
        },
    )

    # PO for 5 * 5000 = 25000 -> BLOCKED (403)
    po_blocked = client.post(
        "/api/v1/purchase-orders",
        headers=pm_headers,
        json={
            "supplier_id": "SUP_API_1",
            "lines": [{"offer_id": "OFF_BOM_1", "ordered_qty": 5, "unit_cost_inr": "5000.00"}],
        },
    )
    assert po_blocked.status_code == 403

    # PO for 2 * 5000 = 10000 -> ALLOWED (201)
    po_ok = client.post(
        "/api/v1/purchase-orders",
        headers=pm_headers,
        json={
            "supplier_id": "SUP_API_1",
            "lines": [{"offer_id": "OFF_BOM_1", "ordered_qty": 2, "unit_cost_inr": "5000.00"}],
        },
    )
    assert po_ok.status_code == 201
    po_num = po_ok.json()["po_number"]
    assert client.post(f"/api/v1/purchase-orders/{po_num}/confirm", headers=pm_headers, json={}).status_code == 200

    # Netting batch lifecycle + invalid state transition (settle before approve -> 400)
    net_res = client.post(
        "/api/v1/supplier-portal/settlement-netting",
        headers=pm_headers,
        json={
            "supplier_id": "SUP_API_1",
            "period_start": (date.today() - timedelta(days=1)).isoformat(),
            "period_end": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert net_res.status_code == 201
    batch_id = net_res.json()["id"]
    assert Decimal(net_res.json()["gross_payable_inr"]) == Decimal("10000.00")

    assert client.post(f"/api/v1/supplier-portal/settlement-netting/{batch_id}/settle", headers=pm_headers).status_code == 400
    assert client.post(f"/api/v1/supplier-portal/settlement-netting/{batch_id}/approve", headers=pm_headers).status_code == 200
    assert client.post(f"/api/v1/supplier-portal/settlement-netting/{batch_id}/settle", headers=pm_headers).status_code == 200


def test_stage12_api_exception_sod_and_expired_fx_rejection(client, db, admin_headers, pm_headers):
    from backend.app.models.schema import FXContractDirection, FXContractStatus, FXForwardContract, FXRateSource

    _seed_api_fixtures(db)

    # Admin submits exception -> Admin self-approval must return 403 (SoD enforcement)
    rule_res = client.post(
        "/api/v1/policy/rules",
        headers=admin_headers,
        json={
            "rule_code": "API_SOD_RULE",
            "name": "SoD Test Rule",
            "scope": "RECOMMENDATION_APPROVAL",
            "outcome": "BLOCK",
            "condition_json": {"field": "recommended_qty", "operator": "gt", "value": 100},
        },
    )
    assert rule_res.status_code == 201
    exc_res = client.post(
        "/api/v1/policy/exceptions",
        headers=admin_headers,
        json={
            "rule_id": rule_res.json()["id"],
            "entity_type": "procurement_recommendations",
            "entity_id": "555",
            "justification": "Self approval test for separation of duties",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
    )
    assert exc_res.status_code == 201
    self_appr = client.post(
        f"/api/v1/policy/exceptions/{exc_res.json()['id']}/approve",
        headers=admin_headers,
        json={"review_notes": "Trying self approve"},
    )
    assert self_appr.status_code == 403

    # Expired FX forward execution must return 400
    exp_fwd = FXForwardContract(
        contract_number="FX-API-EXP-1",
        base_currency="EUR",
        quote_currency="INR",
        direction=FXContractDirection.BUY_BASE_SELL_QUOTE,
        notional_amount_base=Decimal("1000.00"),
        contracted_forward_rate=Decimal("90.50000000"),
        spot_rate_at_booking=Decimal("90.00000000"),
        rate_source=FXRateSource.RBI,
        trade_date=date.today() - timedelta(days=20),
        maturity_date=date.today() - timedelta(days=1),
        valuation_timestamp=datetime.now(timezone.utc),
        counterparty="HDFC",
        status=FXContractStatus.DRAFT,
        created_by_user_id=1,
    )
    db.add(exp_fwd)
    db.commit()
    assert client.post(
        f"/api/v1/treasury/fx-contracts/{exp_fwd.id}/execute",
        headers=admin_headers,
        json={"approval_notes": "Should fail"},
    ).status_code == 400
