from __future__ import annotations

import pytest


def test_budgets_and_ledger(client, admin_headers, pm_headers):
    """Test #97 to #105: Budget envelopes, activation, ledger trail, adjustment, and utilization."""
    # 98. POST /budgets (create draft budget)
    create_res = client.post(
        "/api/v1/budgets",
        headers=admin_headers,
        json={
            "budget_code": "BUD-Q1-2027-GLOBAL",
            "name": "Q1 2027 Global Procurement Envelope",
            "scope": "GLOBAL",
            "period_type": "QUARTERLY",
            "period_start": "2027-01-01",
            "period_end": "2027-03-31",
            "total_amount_inr": 50000000.00,
            "notes": "Initial Q1 envelope allocation",
        }
    )
    assert create_res.status_code == 201
    budget_id = create_res.json()["id"]
    assert create_res.json()["status"] == "DRAFT"

    # 97. GET /budgets (list)
    list_res = client.get("/api/v1/budgets", headers=pm_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 99. GET /budgets/{id} (detail)
    get_res = client.get(f"/api/v1/budgets/{budget_id}", headers=pm_headers)
    assert get_res.status_code == 200
    assert get_res.json()["budget_code"] == "BUD-Q1-2027-GLOBAL"

    # 100. PATCH /budgets/{id} (update DRAFT)
    patch_res = client.patch(
        f"/api/v1/budgets/{budget_id}",
        headers=admin_headers,
        json={"total_amount_inr": 60000000.00}
    )
    assert patch_res.status_code == 200
    assert float(patch_res.json()["total_amount_inr"]) == 60000000.00

    # 101. POST /budgets/{id}/activate (DRAFT -> ACTIVE)
    act_res = client.post(f"/api/v1/budgets/{budget_id}/activate", headers=admin_headers)
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "ACTIVE"

    # 103. POST /budgets/{id}/adjust (manual ledger adjustment)
    adj_res = client.post(
        f"/api/v1/budgets/{budget_id}/adjust",
        headers=admin_headers,
        json={
            "amount_inr": 5000000.00,
            "description": "Executive mid-quarter top-up",
            "idempotency_key": "topup-q1-2027-001",
        }
    )
    assert adj_res.status_code == 200
    assert float(adj_res.json()["total_amount_inr"]) == 65000000.00

    # 104. GET /budgets/{id}/ledger (audit ledger entries)
    ledger_res = client.get(f"/api/v1/budgets/{budget_id}/ledger", headers=pm_headers)
    assert ledger_res.status_code == 200
    assert len(ledger_res.json()) >= 2  # Activation ALLOCATION + ADJUSTMENT

    # 105. GET /budgets/{id}/utilization
    util_res = client.get(f"/api/v1/budgets/{budget_id}/utilization", headers=pm_headers)
    assert util_res.status_code == 200
    assert "utilization_rate" in util_res.json()
    assert float(util_res.json()["available_amount_inr"]) > 0

    # 102. POST /budgets/{id}/close (ACTIVE -> CLOSED)
    close_res = client.post(f"/api/v1/budgets/{budget_id}/close", headers=admin_headers)
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "CLOSED"
