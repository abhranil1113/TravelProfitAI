from __future__ import annotations

import pytest


def test_audit_logs(client, admin_headers, pm_headers):
    """Test #166 and #167: Security audit logs listing and detail inspection."""
    # 166. GET /audit-logs (Admin only - PM forbidden)
    pm_res = client.get("/api/v1/audit-logs", headers=pm_headers)
    assert pm_res.status_code == 403

    admin_res = client.get("/api/v1/audit-logs", headers=admin_headers)
    assert admin_res.status_code == 200
    assert "items" in admin_res.json()
    assert admin_res.json()["total"] >= 0

    # If audit logs exist, test detail
    if admin_res.json()["total"] > 0:
        log_id = admin_res.json()["items"][0]["id"]
        # 167. GET /audit-logs/{id}
        detail_res = client.get(f"/api/v1/audit-logs/{log_id}", headers=admin_headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["id"] == log_id
