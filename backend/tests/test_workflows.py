from __future__ import annotations

import pytest


def test_workflow_a_supplier_and_inventory(client, admin_headers, pm_headers):
    """Workflow A: Supplier & Inventory end-to-end integration."""
    # 1. Create supplier
    supp = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={"supplier_code": "WF-A-SUP-01", "name": "Workflow A Hotels", "supplier_type": "HOTEL", "status": "ACTIVE"}
    ).json()
    supp_id = supp["id"]

    # 2. Add supplier contact
    contact = client.post(
        f"/api/v1/suppliers/{supp_id}/contacts",
        headers=admin_headers,
        json={"contact_name": "Anita Desai", "email": "anita@wfa.com", "is_primary": True}
    ).json()
    assert contact["is_primary"] is True

    # 3. Create destination & inventory item
    dest = client.post(
        "/api/v1/destinations",
        headers=admin_headers,
        json={"dest_id": "JAI", "dest_code": "JAI", "name": "Jaipur", "city": "Jaipur", "country": "India", "airport_code": "JAI", "tier": "T1"}
    ).json()
    dest_id = dest["id"]

    item = client.post(
        "/api/v1/inventory-items",
        headers=admin_headers,
        json={"inventory_id": "INV-JAI-01", "category": "HOTEL", "unit_type": "ROOM_NIGHT", "dest_id": dest_id, "name": "Jaipur Palace Suite", "base_cost_inr": 9000.00}
    ).json()
    item_id = item["id"]

    # 4. Create inventory snapshot
    snap = client.post(
        "/api/v1/inventory-snapshots",
        headers=admin_headers,
        json={"inventory_item_id": item_id, "snapshot_date": "2026-11-24", "available_capacity": 20, "booked_units": 5}
    ).json()
    assert snap["available_capacity"] == 20

    # 5. Create supplier offer
    offer = client.post(
        "/api/v1/supplier-offers",
        headers=admin_headers,
        json={"supplier_id": supp_id, "inventory_item_id": item_id, "offer_price_inr": 8500.00, "min_quantity": 2, "max_quantity": 15, "available_units": 15, "valid_from": "2026-11-24", "valid_to": "2026-12-31"}
    ).json()
    offer_id = offer["id"]

    # 6. Retrieve offers
    offers_list = client.get(f"/api/v1/suppliers/{supp_id}/offers", headers=pm_headers).json()
    items = offers_list["items"] if isinstance(offers_list, dict) else offers_list
    assert len(items) >= 1


def test_workflow_b_reference_and_ml(client, admin_headers, pm_headers, analyst_headers):
    """Workflow B: Reference Data, Pipelines, and ML Model Registry."""
    # 1. Market signals
    sig = client.post(
        "/api/v1/market-signals",
        headers=admin_headers,
        json={"dest_id": "DEL", "signal_type": "FESTIVAL", "signal_value": 1.25, "headline": "Diwali Tourist Surge"}
    ).json()
    assert sig["dest_id"] == "DEL"

    # 2. Pipeline batch
    batch = client.post(
        "/api/v1/pipelines/batches",
        headers=admin_headers,
        json={"source_type": "MARKET_RATES", "source_name": "exchange_feed", "file_path": "data/rates.csv", "record_count": 100}
    ).json()
    assert batch["status"] == "PENDING"

    # 3. Feature set & predictions
    fs = client.post(
        "/api/v1/ml/feature-sets",
        headers=analyst_headers,
        json={"name": "wf_b_features", "version": "v1.0", "model_type": "flight_price", "parquet_path": "data/flights.parquet", "num_rows": 5000, "num_features": 12, "column_names": ["route", "dow"]}
    ).json()
    assert fs["name"] == "wf_b_features"


def test_workflow_c_optimization_and_procurement(client, seeded_optimization_db, admin_headers, pm_headers):
    """Workflow C: Budget activation, MILP Optimization, Approval, and PO Generation."""
    # 1. Create and activate budget
    budget = client.post(
        "/api/v1/budgets",
        headers=admin_headers,
        json={"budget_code": "BUD-WF-C-01", "name": "Workflow C Budget", "scope": "GLOBAL", "period_type": "MONTHLY", "period_start": "2026-12-01", "period_end": "2026-12-31", "total_amount_inr": 20000000.00}
    ).json()
    budget_id = budget["id"]
    client.post(f"/api/v1/budgets/{budget_id}/activate", headers=admin_headers)

    # 2. Trigger optimization run
    run = client.post(
        "/api/v1/optimization-runs",
        headers=pm_headers,
        json={"optimization_mode": "JOINT", "budget_id": budget_id, "total_budget_inr": 20000000.00, "solver_backend": "SCIP"}
    ).json()
    run_id = run["run_id"]

    # 3. Check status & scorecard
    status = client.get(f"/api/v1/optimization-runs/{run_id}/status", headers=pm_headers).json()
    assert status["is_optimal"] is True

    scorecard = client.get(f"/api/v1/optimization-runs/{run_id}/scorecard", headers=pm_headers).json()
    assert float(scorecard["total_spend_inr"]) > 0

    # 4. Approve run
    approved = client.post(f"/api/v1/optimization-runs/{run_id}/approve", headers=pm_headers, json={"decision_notes": "All checks passed"}).json()
    assert approved["approval_status"] == "APPROVED"

    # 5. Generate purchase orders
    pos = client.post(f"/api/v1/optimization-runs/{run_id}/purchase-orders/generate", headers=pm_headers).json()
    assert "purchase_orders_created" in pos


def test_workflow_d_reports_and_analytics(client, admin_headers, pm_headers, worker_headers):
    """Workflow D: Search Events, Analytics, Reports, and Notifications."""
    # 1. Ingest search events
    events = client.post(
        "/api/v1/search-events/bulk",
        headers=worker_headers,
        json={"events": [{"dest_id": "DEL", "inventory_category": "HOTEL", "stay_duration_nights": 3, "converted": True, "conversion_value_inr": 15000.00}]}
    ).json()
    assert events["inserted_count"] == 1

    # 2. Analytics overview
    dash = client.get("/api/v1/analytics/dashboard", headers=pm_headers).json()
    assert "total_spend_inr" in dash

    # 3. Create report
    report = client.post(
        "/api/v1/reports",
        headers=pm_headers,
        json={"title": "Workflow D Executive Report", "report_type": "OPTIMIZATION_SUMMARY", "report_format": "PDF"}
    ).json()
    assert report["status"] == "COMPLETED"

    # 4. Notifications
    unread = client.get("/api/v1/notifications/unread-count", headers=pm_headers).json()
    assert "unread_count" in unread
