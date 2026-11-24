from __future__ import annotations

import pytest


def test_optimization_runs_lifecycle(client, admin_headers, pm_headers, analyst_headers):
    """Test #106 to #123, #176, #179: Optimization runs, baselines, risk, sensitivity, and artifacts."""
    # 106. POST /optimization-runs (trigger run)
    run_res = client.post(
        "/api/v1/optimization-runs",
        headers=pm_headers,
        json={
            "optimization_mode": "JOINT",
            "total_budget_inr": 10000000.00,
            "max_supplier_share": 0.40,
            "max_destination_share": 0.35,
            "solver_backend": "SCIP",
            "scenario_name": "Test Q1 Run",
        }
    )
    assert run_res.status_code == 201
    run_id = run_res.json()["run_id"]
    assert run_res.json()["pipeline_status"] in ("SUCCESS", "OPTIMAL", "RUNNING")

    # 108. GET /optimization-runs (list)
    list_runs = client.get("/api/v1/optimization-runs", headers=pm_headers)
    assert list_runs.status_code == 200
    assert list_runs.json()["total"] >= 1

    # 109. GET /optimization-runs/{run_id} (detail)
    get_run = client.get(f"/api/v1/optimization-runs/{run_id}", headers=pm_headers)
    assert get_run.status_code == 200
    assert get_run.json()["run_id"] == run_id

    # 110. GET /optimization-runs/{run_id}/status
    status_res = client.get(f"/api/v1/optimization-runs/{run_id}/status", headers=pm_headers)
    assert status_res.status_code == 200
    assert "pipeline_status" in status_res.json()

    # 111. GET /optimization-runs/{run_id}/stream (SSE stream)
    stream_res = client.get(f"/api/v1/optimization-runs/{run_id}/stream", headers=pm_headers)
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]

    # 116. GET /optimization-runs/{run_id}/scorecard
    scorecard_res = client.get(f"/api/v1/optimization-runs/{run_id}/scorecard", headers=pm_headers)
    assert scorecard_res.status_code == 200
    assert "expected_net_profit_inr" in scorecard_res.json()

    # 117. GET /optimization-runs/{run_id}/baselines
    base_res = client.get(f"/api/v1/optimization-runs/{run_id}/baselines", headers=pm_headers)
    assert base_res.status_code == 200
    assert len(base_res.json()) >= 1

    # 118. GET /optimization-runs/{run_id}/risk-metrics
    risk_res = client.get(f"/api/v1/optimization-runs/{run_id}/risk-metrics", headers=pm_headers)
    assert risk_res.status_code == 200
    assert "supplier_hhi" in risk_res.json()

    # 119. GET /optimization-runs/{run_id}/constraints
    cons_res = client.get(f"/api/v1/optimization-runs/{run_id}/constraints", headers=analyst_headers)
    assert cons_res.status_code == 200
    assert len(cons_res.json()) >= 1

    # 120. GET /optimization-runs/{run_id}/sensitivity
    sens_res = client.get(f"/api/v1/optimization-runs/{run_id}/sensitivity", headers=pm_headers)
    assert sens_res.status_code == 200

    # 176. POST /optimization-runs/{run_id}/sensitivity
    sweep_res = client.post(
        f"/api/v1/optimization-runs/{run_id}/sensitivity",
        headers=pm_headers,
        json={"sweep_parameter": "total_budget_inr", "variation_pcts": [-0.10, 0.0, 0.10]}
    )
    assert sweep_res.status_code == 200
    assert len(sweep_res.json()) >= 3

    # 121. GET /optimization-runs/{run_id}/artifacts
    art_res = client.get(f"/api/v1/optimization-runs/{run_id}/artifacts", headers=pm_headers)
    assert art_res.status_code == 200
    assert len(art_res.json()) >= 1
    art_filename = art_res.json()[0]["filename"]

    # 122. GET /optimization-runs/{run_id}/artifacts/{filename}
    art_dl = client.get(f"/api/v1/optimization-runs/{run_id}/artifacts/{art_filename}", headers=pm_headers)
    assert art_dl.status_code == 200

    # 107. POST /optimization-runs/compare
    cmp_res = client.post(
        "/api/v1/optimization-runs/compare",
        headers=pm_headers,
        json={"run_ids": [run_id, run_id]}
    )
    assert cmp_res.status_code == 200

    # 123. GET /optimization-runs/compare/{comparison_group_id}
    cmp_get = client.get("/api/v1/optimization-runs/compare/cmp_test_01", headers=pm_headers)
    assert cmp_get.status_code == 200

    # 114. POST /optimization-runs/{run_id}/approve
    appr_res = client.post(
        f"/api/v1/optimization-runs/{run_id}/approve",
        headers=pm_headers,
        json={"decision_notes": "Approved by Procurement Director"}
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["approval_status"] == "APPROVED"

    # 179. POST /optimization-runs/{run_id}/purchase-orders/generate
    po_gen = client.post(f"/api/v1/optimization-runs/{run_id}/purchase-orders/generate", headers=pm_headers)
    assert po_gen.status_code == 200
    assert "purchase_orders_created" in po_gen.json()

    # 113. POST /optimization-runs/{run_id}/retry
    retry_res = client.post(f"/api/v1/optimization-runs/{run_id}/retry", headers=pm_headers)
    assert retry_res.status_code == 201

    # 112. POST /optimization-runs/{run_id}/cancel (on a new pending run)
    new_run = client.post(
        "/api/v1/optimization-runs",
        headers=pm_headers,
        json={"optimization_mode": "HOTEL_ONLY", "total_budget_inr": 5000000.00}
    ).json()["run_id"]
    # 115. POST /optimization-runs/{run_id}/reject
    rej_res = client.post(
        f"/api/v1/optimization-runs/{new_run}/reject",
        headers=pm_headers,
        json={"decision_notes": "Rejected due to budget constraints"}
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["approval_status"] == "REJECTED"
