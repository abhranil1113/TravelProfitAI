from __future__ import annotations

import pytest


def test_reports_and_schedules(client, admin_headers, pm_headers):
    """Test #144 to #154: Report generation, download, regeneration, and cron schedules."""
    # 145. POST /reports (create on-demand report)
    rep_res = client.post(
        "/api/v1/reports",
        headers=pm_headers,
        json={
            "title": "Monthly Procurement Audit Report",
            "report_type": "OPTIMIZATION_SUMMARY",
            "report_format": "PDF",
        }
    )
    assert rep_res.status_code == 201
    report_id = rep_res.json()["report_id"]

    # 144. GET /reports (list)
    rep_list = client.get("/api/v1/reports", headers=pm_headers)
    assert rep_list.status_code == 200
    assert len(rep_list.json()["items"]) >= 1

    # 146. GET /reports/{report_id} (detail)
    get_rep = client.get(f"/api/v1/reports/{report_id}", headers=pm_headers)
    assert get_rep.status_code == 200
    assert get_rep.json()["report_id"] == report_id

    # 147. GET /reports/{report_id}/download
    dl_res = client.get(f"/api/v1/reports/{report_id}/download", headers=pm_headers)
    assert dl_res.status_code == 200
    assert "attachment" in dl_res.headers.get("content-disposition", "")

    # 148. POST /reports/{report_id}/regenerate
    regen_res = client.post(f"/api/v1/reports/{report_id}/regenerate", headers=pm_headers)
    assert regen_res.status_code == 200
    assert regen_res.json()["status"] == "COMPLETED"

    # 151. POST /report-schedules (create schedule)
    sched_res = client.post(
        "/api/v1/report-schedules",
        headers=admin_headers,
        json={
            "report_type": "OPTIMIZATION_SUMMARY",
            "report_format": "PDF",
            "cron_expression": "0 8 * * 1",
            "is_enabled": True,
        }
    )
    assert sched_res.status_code == 201
    sched_id = sched_res.json()["id"]

    # 150. GET /report-schedules (list schedules)
    sched_list = client.get("/api/v1/report-schedules", headers=admin_headers)
    assert sched_list.status_code == 200
    assert len(sched_list.json()["items"]) >= 1

    # 152. PATCH /report-schedules/{id}
    patch_sched = client.patch(
        f"/api/v1/report-schedules/{sched_id}",
        headers=admin_headers,
        json={"cron_expression": "0 9 * * 1"}
    )
    assert patch_sched.status_code == 200
    assert patch_sched.json()["cron_expression"] == "0 9 * * 1"

    # 153. POST /report-schedules/{id}/enable (toggle)
    toggle_sched = client.post(f"/api/v1/report-schedules/{sched_id}/enable", headers=admin_headers)
    assert toggle_sched.status_code == 200
    assert toggle_sched.json()["is_enabled"] is False

    # 154. DELETE /report-schedules/{id}
    del_sched = client.delete(f"/api/v1/report-schedules/{sched_id}", headers=admin_headers)
    assert del_sched.status_code == 204

    # 149. DELETE /reports/{report_id}
    del_rep = client.delete(f"/api/v1/reports/{report_id}", headers=admin_headers)
    assert del_rep.status_code == 204
