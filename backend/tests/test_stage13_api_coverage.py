from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from backend.app.core.config import get_settings
from backend.app.models.schema import (
    ApprovalStatus,
    Destination,
    FXContractDirection,
    FXContractStatus,
    FXForwardContract,
    FXRateSource,
    InventoryCategory,
    InventoryItem,
    MLModel,
    MLModelType,
    Notification,
    NotificationType,
    OfferStatus,
    OptimizationRun,
    ProcurementRecommendation,
    SettlementBatchStatus,
    SettlementNettingBatch,
    SolverStatus,
    Supplier,
    SupplierOffer,
    SupplierType,
    UnitType,
)
from backend.app.services.supplier_portal_service import SupplierPortalService


def _seed_stage13_catalog(db):
    dest = Destination(dest_id="GOA", name="Goa", city="Panaji", country="India", airport_code="GOI")
    supp = Supplier(
        supplier_id="SUP_S13",
        name="Stage 13 Resorts",
        supplier_type=SupplierType.HOTEL,
        fulfillment_rate=0.96,
        max_spend_share_cap=0.75,
        is_active=True,
    )
    inv = InventoryItem(
        inventory_id="INV_S13_1",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        dest_id="GOA",
    )
    db.add_all([dest, supp, inv])
    db.flush()

    offers = [
        SupplierOffer(
            offer_id=f"OFF_S13_{i}",
            supplier_id="SUP_S13",
            inventory_id="INV_S13_1",
            dest_id="GOA",
            inventory_category=InventoryCategory.HOTEL,
            unit_type=UnitType.ROOM_NIGHT,
            unit_cost_inr=Decimal("4000.00"),
            list_price_inr=Decimal("6000.00"),
            currency_code="INR",
            moq=2,
            max_capacity=100,
            valid_from=date(2026, 11, 1),
            valid_until=date(2026, 12, 20),
            travel_date=date(2026, 12, 25),
            status=OfferStatus.ACTIVE,
        )
        for i in range(1, 5)
    ]
    run = OptimizationRun(
        run_id="RUN_S13_1",
        cutoff_date=date(2026, 11, 25),
        total_budget_inr=Decimal("500000.00"),
        solver_status=SolverStatus.OPTIMAL,
    )
    db.add_all([*offers, run])
    db.flush()

    r1 = ProcurementRecommendation(
        run_id="RUN_S13_1", offer_id="OFF_S13_1", supplier_id="SUP_S13", dest_id="GOA",
        inventory_category=InventoryCategory.HOTEL, unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=5, unit_cost_inr=Decimal("4000.00"), total_spend_inr=Decimal("20000.00"),
        expected_unit_contribution_inr=Decimal("1200.00"), expected_total_contribution_inr=Decimal("6000.00"),
        sell_through_rate=0.80, moq_applied=2, capacity_available=100, rationale="S13-1",
        approval_status=ApprovalStatus.PENDING,
    )
    r2 = ProcurementRecommendation(
        run_id="RUN_S13_1", offer_id="OFF_S13_2", supplier_id="SUP_S13", dest_id="GOA",
        inventory_category=InventoryCategory.HOTEL, unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=4, unit_cost_inr=Decimal("4000.00"), total_spend_inr=Decimal("16000.00"),
        expected_unit_contribution_inr=Decimal("1200.00"), expected_total_contribution_inr=Decimal("4800.00"),
        sell_through_rate=0.80, moq_applied=2, capacity_available=100, rationale="S13-2",
        approval_status=ApprovalStatus.PENDING,
    )
    r3 = ProcurementRecommendation(
        run_id="RUN_S13_1", offer_id="OFF_S13_3", supplier_id="SUP_S13", dest_id="GOA",
        inventory_category=InventoryCategory.HOTEL, unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=3, unit_cost_inr=Decimal("4000.00"), total_spend_inr=Decimal("12000.00"),
        expected_unit_contribution_inr=Decimal("1200.00"), expected_total_contribution_inr=Decimal("3600.00"),
        sell_through_rate=0.80, moq_applied=2, capacity_available=100, rationale="S13-3",
        approval_status=ApprovalStatus.PENDING,
    )
    r4 = ProcurementRecommendation(
        run_id="RUN_S13_1", offer_id="OFF_S13_4", supplier_id="SUP_S13", dest_id="GOA",
        inventory_category=InventoryCategory.HOTEL, unit_type=UnitType.ROOM_NIGHT,
        recommended_qty=6, unit_cost_inr=Decimal("4000.00"), total_spend_inr=Decimal("24000.00"),
        expected_unit_contribution_inr=Decimal("1200.00"), expected_total_contribution_inr=Decimal("7200.00"),
        sell_through_rate=0.80, moq_applied=2, capacity_available=100, rationale="S13-4",
        approval_status=ApprovalStatus.PENDING,
    )
    m1 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v1.0",
        algorithm="LightGBM",
        artifact_dir="data/models/hotel_cancellation",
        metrics_json={"roc_auc": 0.91},
        training_cutoff_date=date(2026, 11, 1),
        is_champion=True,
        model_status="PROMOTED",
    )
    m2 = MLModel(
        model_type=MLModelType.HOTEL_CANCELLATION,
        version="v2.0",
        algorithm="LightGBM",
        artifact_dir="data/models/hotel_cancellation",
        metrics_json={"roc_auc": 0.93},
        training_cutoff_date=date(2026, 11, 20),
        is_champion=False,
        model_status="TRAINED",
    )
    notif = Notification(
        user_id=1,
        type=NotificationType.RUN_COMPLETED,
        title="Stage 13 Test Alert",
        message="Unread notification check",
        is_read=False,
    )
    db.add_all([r1, r2, r3, r4, m1, m2, notif])
    db.commit()
    return [r1.id, r2.id, r3.id, r4.id], m1.id, m2.id, notif.id


def test_openapi_docs_and_regression_fixes(client, db, admin_headers, analyst_headers, pm_headers, tmp_path, monkeypatch):
    """Covers docs routes, empty-catalog 400 fix, production token redaction, and string-ID filters."""
    # OpenAPI / Docs routes
    assert client.get("/api/v1/openapi.json").status_code == 200
    assert client.get("/api/v1/docs").status_code == 200
    assert client.get("/api/v1/redoc").status_code == 200

    # Empty catalog optimization trigger -> clean HTTP 400 (never 500 CurrencyMismatchError)
    empty_opt = client.post(
        "/api/v1/optimization-runs",
        headers=pm_headers,
        json={"optimization_mode": "JOINT", "total_budget_inr": 100000},
    )
    assert empty_opt.status_code == 400
    assert "no active supplier offers" in empty_opt.json()["detail"].lower()

    # Pipeline batch with real temp CSV -> SUCCESS + retry
    csv_file = tmp_path / "market_feed.csv"
    csv_file.write_text("col_a,col_b\n1,2\n1,2\n3,4\n", encoding="utf-8")
    p_res = client.post(
        "/api/v1/pipelines/batches",
        headers=admin_headers,
        json={"dataset_name": "custom_feed", "source_uri": str(csv_file)},
    )
    assert p_res.status_code == 201
    b_data = p_res.json()
    assert b_data["status"] == "SUCCESS"
    assert b_data["rows_ingested"] == 2
    assert b_data["rows_duplicates_removed"] == 1

    # force-password-reset redacts action_token in production
    from backend.app.api.v1 import users as users_router
    monkeypatch.setattr(users_router, "get_settings", lambda: type("ProdCfg", (), {"ENVIRONMENT": "production"})())
    fpr = client.post("/api/v1/users/3/force-password-reset", headers=admin_headers)
    assert fpr.status_code == 200
    assert fpr.json()["action_token"] is None

    # String-key filters on recommendations & purchase orders
    assert client.get("/api/v1/recommendations?supplier_id=SUP_S13", headers=analyst_headers).status_code == 200
    assert client.get("/api/v1/purchase-orders?supplier_id=SUP_S13", headers=pm_headers).status_code == 200
    assert client.get("/api/v1/ml/feature-sets?model_type=hotel_cancellation", headers=analyst_headers).status_code == 200


def test_uncovered_recommendations_and_notifications_routes(client, db, admin_headers, pm_headers, analyst_headers):
    """Covers recommendations individual/bulk approve/reject, stress-tests list, and notifications/{id}/read."""
    rec_ids, _, _, notif_id = _seed_stage13_catalog(db)

    # Individual approve/reject (Analyst forbidden)
    assert client.post(f"/api/v1/recommendations/{rec_ids[0]}/approve", headers=analyst_headers, json={}).status_code == 403
    assert client.post(f"/api/v1/recommendations/{rec_ids[0]}/approve", headers=pm_headers, json={"decision_notes": "Single OK"}).status_code == 200
    assert client.post(f"/api/v1/recommendations/{rec_ids[1]}/reject", headers=pm_headers, json={"decision_notes": "Single Rej"}).status_code == 200

    # Bulk approve/reject
    bulk_ok = client.post(
        "/api/v1/optimization-runs/RUN_S13_1/recommendations/bulk-approve",
        headers=pm_headers,
        json={"recommendation_ids": [rec_ids[2]], "decision_notes": "Bulk OK"},
    )
    assert bulk_ok.status_code == 200
    assert bulk_ok.json()["updated_count"] == 1

    bulk_rej = client.post(
        "/api/v1/optimization-runs/RUN_S13_1/recommendations/bulk-reject",
        headers=pm_headers,
        json={"recommendation_ids": [rec_ids[3]], "decision_notes": "Bulk Rej"},
    )
    assert bulk_rej.status_code == 200
    assert bulk_rej.json()["updated_count"] == 1

    # Optimization run stress-tests GET
    st_list = client.get("/api/v1/optimization-runs/RUN_S13_1/stress-tests", headers=analyst_headers)
    assert st_list.status_code == 200
    assert isinstance(st_list.json(), list)

    # Notification mark read
    assert client.post(f"/api/v1/notifications/{notif_id}/read", headers=admin_headers).status_code == 200
    assert client.post("/api/v1/notifications/999999/read", headers=admin_headers).status_code == 404


def test_uncovered_domain1_and_domain2_routes(client, db, admin_headers, analyst_headers, pm_headers, worker_headers):
    """Covers GET/PATCH/DELETE /risk/scenarios/{id} and uncovered /mlops/* routes."""
    _, m1_id, m2_id, _ = _seed_stage13_catalog(db)

    # Domain 1: Risk scenarios CRUD
    sc = client.post(
        "/api/v1/risk/scenarios",
        headers=admin_headers,
        json={
            "scenario_code": "S13_SCEN_1",
            "name": "FX Spike 10%",
            "scenario_type": "FX_SHOCK",
            "probability_weight": 0.5,
            "demand_multiplier": 0.9,
            "cancellation_delta": 0.05,
            "fx_shock_pct": 0.10,
            "supplier_capacity_multiplier": 1.0,
        },
    ).json()
    sid = sc["id"]
    assert client.get(f"/api/v1/risk/scenarios/{sid}", headers=analyst_headers).status_code == 200
    assert client.get("/api/v1/risk/scenarios/999999", headers=analyst_headers).status_code == 404
    assert client.patch(f"/api/v1/risk/scenarios/{sid}", headers=pm_headers, json={"name": "Forbidden"}).status_code == 403
    upd = client.patch(f"/api/v1/risk/scenarios/{sid}", headers=admin_headers, json={"name": "FX Spike Updated", "probability_weight": 0.6})
    assert upd.status_code == 200
    assert upd.json()["name"] == "FX Spike Updated"
    d_res = client.delete(f"/api/v1/risk/scenarios/{sid}", headers=admin_headers)
    assert d_res.status_code == 200
    assert d_res.json()["is_active"] is False

    # Domain 2: Feature freshness check (worker only)
    ff_payload = {
        "feature_group_name": "hotel_booking_features",
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
        "sla_threshold_seconds": 3600,
        "record_count": 1000,
    }
    assert client.post("/api/v1/mlops/feature-freshness/check", headers=admin_headers, json=ff_payload).status_code == 403
    assert client.post("/api/v1/mlops/feature-freshness/check", headers=worker_headers, json=ff_payload).status_code == 201

    # Deployment create + PATCH + shadow predictions POST/GET
    dep = client.post(
        "/api/v1/mlops/deployments",
        headers=admin_headers,
        json={"model_id": m2_id, "deployment_mode": "SHADOW", "traffic_percentage": 0.0},
    )
    assert dep.status_code == 201
    dep_id = dep.json()["id"]
    assert client.patch(f"/api/v1/mlops/deployments/{dep_id}", headers=analyst_headers, json={"notes": "no"}).status_code == 403
    assert client.patch(f"/api/v1/mlops/deployments/{dep_id}", headers=admin_headers, json={"notes": "Updated shadow config"}).status_code == 200

    sh_log = client.post(
        f"/api/v1/mlops/deployments/{dep_id}/shadow-predictions",
        headers=admin_headers,
        json={"entity_id": "OFF_S13_1", "features": {"lead_time": 12}, "champion_prediction": 0.22, "candidate_prediction": 0.19},
    )
    assert sh_log.status_code == 201
    assert len(client.get(f"/api/v1/mlops/deployments/{dep_id}/shadow-predictions", headers=admin_headers).json()) == 1

    # Governed promotion, rollback, and monitoring history
    prom = client.post(
        f"/api/v1/mlops/models/{m2_id}/promote",
        headers=admin_headers,
        json={"reason": "Higher ROC-AUC in shadow validation", "require_no_severe_drift": True},
    )
    assert prom.status_code == 200
    assert prom.json()["is_champion"] is True

    rb = client.post(
        f"/api/v1/mlops/models/{m2_id}/rollback",
        headers=admin_headers,
        json={"target_model_id": m1_id, "reason": "Stage 13 rollback check"},
    )
    assert rb.status_code == 200
    assert rb.json()["id"] == m1_id
    assert rb.json()["is_champion"] is True

    hist = client.get("/api/v1/mlops/history", headers=analyst_headers)
    assert hist.status_code == 200
    assert len(hist.json()) >= 2


def test_uncovered_domain3_domain4_domain5_routes(client, db, admin_headers, pm_headers, analyst_headers):
    """Covers remaining uncovered endpoints in Supplier Portal, Treasury FX, and Policy Engine."""
    SupplierPortalService.reset_rate_limits()
    _seed_stage13_catalog(db)

    # Domain 3: Credential rotate/revoke, /me/sync-logs, tier-verification, onboarding advance
    cred = client.post("/api/v1/supplier-portal/credentials", headers=admin_headers, json={"supplier_id": "SUP_S13", "label": "Primary"}).json()
    cid = cred["id"]
    raw_secret = cred["raw_api_secret"]

    rot = client.post(f"/api/v1/supplier-portal/credentials/{cid}/rotate", headers=admin_headers)
    assert rot.status_code == 200
    new_secret = rot.json()["raw_api_secret"]
    new_cid = rot.json()["id"]
    assert new_secret != raw_secret

    # Old rotated secret rejected; new secret sees /me/sync-logs
    assert client.get("/api/v1/supplier-portal/me/sync-logs", headers={"X-Supplier-Key": raw_secret}).status_code == 401
    assert client.get("/api/v1/supplier-portal/me/sync-logs", headers={"X-Supplier-Key": new_secret}).status_code == 200
    assert client.post(f"/api/v1/supplier-portal/credentials/{new_cid}/revoke", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/supplier-portal/me/sync-logs", headers={"X-Supplier-Key": new_secret}).status_code == 401

    tier_upd = client.put(
        "/api/v1/supplier-portal/suppliers/SUP_S13/tier-verification",
        headers=admin_headers,
        json={"tier": "TIER_1_STRATEGIC", "verification_status": "VERIFIED", "risk_score": 0.125, "sla_response_hours": 4},
    )
    assert tier_upd.status_code == 200
    assert client.get("/api/v1/supplier-portal/suppliers/SUP_S13/tier-verification", headers=pm_headers).json()["tier"] == "TIER_1_STRATEGIC"

    onb = client.post("/api/v1/supplier-portal/onboarding", headers=admin_headers, json={"supplier_id": "SUP_S13"}).json()
    adv = client.post(
        f"/api/v1/supplier-portal/onboarding/{onb['id']}/advance",
        headers=admin_headers,
        json={"target_stage": "DOCUMENT_REVIEW", "notes": "Docs submitted"},
    )
    assert adv.status_code == 200
    assert adv.json()["stage"] == "DOCUMENT_REVIEW"

    # Domain 4: FX execute/settle/cancel, exposure/snapshot, hedge-effectiveness, margin-rules PATCH, alerts GET/acknowledge
    from backend.app.models.schema import ExchangeRate
    db.add(ExchangeRate(from_currency="USD", to_currency="INR", rate=Decimal("84.00"), as_of_date=date.today(), source="RBI"))
    db.commit()

    fx_c1 = client.post(
        "/api/v1/treasury/fx-contracts",
        headers=admin_headers,
        json={
            "base_currency": "USD", "quote_currency": "INR", "direction": "BUY_BASE_SELL_QUOTE",
            "notional_amount_base": "5000.00", "contracted_forward_rate": "84.50",
            "trade_date": date.today().isoformat(), "maturity_date": (date.today() + timedelta(days=30)).isoformat(),
            "counterparty": "ICICI Treasury",
        },
    ).json()["id"]
    assert client.post(f"/api/v1/treasury/fx-contracts/{fx_c1}/execute", headers=admin_headers, json={"approval_notes": "Exec"}).status_code == 200
    assert client.post(f"/api/v1/treasury/fx-contracts/{fx_c1}/settle", headers=admin_headers).status_code == 200

    fx_c2 = client.post(
        "/api/v1/treasury/fx-contracts",
        headers=admin_headers,
        json={
            "base_currency": "USD", "quote_currency": "INR", "direction": "BUY_BASE_SELL_QUOTE",
            "notional_amount_base": "2000.00", "contracted_forward_rate": "85.00",
            "trade_date": date.today().isoformat(), "maturity_date": (date.today() + timedelta(days=30)).isoformat(),
            "counterparty": "Axis FX",
        },
    ).json()["id"]
    assert client.post(f"/api/v1/treasury/fx-contracts/{fx_c2}/cancel", headers=admin_headers).status_code == 200

    snap = client.post("/api/v1/treasury/exposure/snapshot?currency_code=USD&target_currency=INR", headers=analyst_headers)
    assert snap.status_code == 201

    he = client.post(
        "/api/v1/treasury/hedge-effectiveness",
        headers=admin_headers,
        json={"contract_id": fx_c1, "measurement_date": date.today().isoformat(), "hedged_item_fv_change_inr": "-1000.00"},
    )
    assert he.status_code == 201
    assert len(client.get(f"/api/v1/treasury/hedge-effectiveness?contract_id={fx_c1}", headers=analyst_headers).json()) == 1

    mrule = client.post(
        "/api/v1/treasury/margin-rules",
        headers=admin_headers,
        json={"rule_code": "USD_S13_FLOOR", "name": "Floor", "currency_code": "USD", "min_gross_margin_pct": 25.0, "max_fx_drawdown_pct": 2.0},
    ).json()["id"]
    assert client.patch(f"/api/v1/treasury/margin-rules/{mrule}", headers=admin_headers, json={"name": "Strict Floor"}).status_code == 200

    # Trigger breach alert via margin-impact evaluation
    client.post(
        "/api/v1/treasury/margin-impact/evaluate",
        headers=pm_headers,
        json={"currency_code": "USD", "purchase_cost_base": "1000.00", "selling_price_inr": "86000.00", "fx_shock_pct": 0.10},
    )
    alerts = client.get("/api/v1/treasury/alerts", headers=analyst_headers).json()
    assert len(alerts) >= 1
    assert client.post(f"/api/v1/treasury/alerts/{alerts[0]['id']}/acknowledge", headers=pm_headers).json()["is_acknowledged"] is True

    # Domain 5: GET/PATCH /policy/rules/{id}, POST /evaluate, GET /evaluations, POST /exceptions/{id}/reject
    pr = client.post(
        "/api/v1/policy/rules",
        headers=admin_headers,
        json={
            "rule_code": "S13_POL_1", "name": "S13 Cap", "scope": "PURCHASE_ORDER_CREATE",
            "outcome": "WARN", "condition_json": {"field": "total_amount_inr", "operator": "gt", "value": 10000},
        },
    ).json()["id"]
    assert client.get(f"/api/v1/policy/rules/{pr}", headers=analyst_headers).status_code == 200
    assert client.patch(
        f"/api/v1/policy/rules/{pr}",
        headers=admin_headers,
        json={"name": "S13 Cap v2", "condition_json": {"field": "total_amount_inr", "operator": "gt", "value": 15000}},
    ).json()["active_version_number"] == 2

    ev = client.post(
        "/api/v1/policy/evaluate",
        headers=pm_headers,
        json={"scope": "PURCHASE_ORDER_CREATE", "entity_type": "purchase_orders", "entity_id": "PO-SIM-1", "context": {"total_amount_inr": 20000}, "persist_history": True},
    )
    assert ev.status_code == 200
    assert len(client.get("/api/v1/policy/evaluations", headers=analyst_headers).json()) >= 1

    exc = client.post(
        "/api/v1/policy/exceptions",
        headers=pm_headers,
        json={
            "rule_id": pr, "entity_type": "purchase_orders", "entity_id": "PO-SIM-2",
            "justification": "Testing exception rejection", "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
    ).json()["id"]
    rej_exc = client.post(f"/api/v1/policy/exceptions/{exc}/reject", headers=admin_headers, json={"review_notes": "Rejected by compliance"})
    assert rej_exc.status_code == 200
    assert rej_exc.json()["status"] == "REJECTED"
