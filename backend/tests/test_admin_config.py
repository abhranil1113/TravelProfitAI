from __future__ import annotations

import pytest


def test_admin_config_and_templates(client, admin_headers, pm_headers, analyst_headers):
    """Test #88 to #96: Platform optimization config profiles and templates."""
    # 88. GET /admin/platform-config (active profile)
    active_res = client.get("/api/v1/admin/platform-config", headers=analyst_headers)
    assert active_res.status_code == 200
    assert "default_total_budget_inr" in active_res.json()

    # 89. GET /admin/platform-config/history
    hist_res = client.get("/api/v1/admin/platform-config/history", headers=admin_headers)
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1

    # 90. POST /admin/platform-config (create draft)
    draft_res = client.post(
        "/api/v1/admin/platform-config",
        headers=admin_headers,
        json={
            "profile_name": "Q1 2027 Aggressive Growth Profile",
            "default_total_budget_inr": 150000000.00,
            "max_supplier_share": 0.45,
            "max_destination_share": 0.35,
        }
    )
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["id"]
    assert draft_res.json()["status"] == "DRAFT"

    # 91. PATCH /admin/platform-config/{id} (update draft)
    patch_res = client.patch(
        f"/api/v1/admin/platform-config/{draft_id}",
        headers=admin_headers,
        json={"max_supplier_share": 0.40}
    )
    assert patch_res.status_code == 200
    assert float(patch_res.json()["max_supplier_share"]) == 0.40

    # 92. POST /admin/platform-config/{id}/activate (activate draft)
    act_res = client.post(f"/api/v1/admin/platform-config/{draft_id}/activate", headers=admin_headers)
    assert act_res.status_code == 200
    assert act_res.json()["is_active"] is True
    assert act_res.json()["status"] == "ACTIVE"

    # 94. POST /admin/config-templates (create template)
    tmpl_res = client.post(
        "/api/v1/admin/config-templates",
        headers=admin_headers,
        json={
            "template_name": "High Yield Peak Season Template",
            "default_mode": "JOINT",
            "default_solver_backend": "SCIP",
            "default_budget_inr": 80000000.00,
        }
    )
    assert tmpl_res.status_code == 201
    tmpl_id = tmpl_res.json()["id"]

    # 93. GET /admin/config-templates (list templates)
    tmpls_res = client.get("/api/v1/admin/config-templates", headers=pm_headers)
    assert tmpls_res.status_code == 200
    assert len(tmpls_res.json()) >= 1

    # 95. PATCH /admin/config-templates/{id} (update template)
    patch_tmpl = client.patch(
        f"/api/v1/admin/config-templates/{tmpl_id}",
        headers=admin_headers,
        json={"description": "Updated high yield template"}
    )
    assert patch_tmpl.status_code == 200
    assert patch_tmpl.json()["description"] == "Updated high yield template"

    # 96. DELETE /admin/config-templates/{id} (delete template)
    del_tmpl = client.delete(f"/api/v1/admin/config-templates/{tmpl_id}", headers=admin_headers)
    assert del_tmpl.status_code == 204
