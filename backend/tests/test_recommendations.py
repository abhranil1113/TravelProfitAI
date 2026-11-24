from __future__ import annotations

import pytest


def test_recommendations_and_rejections(client, admin_headers, pm_headers, analyst_headers):
    """Test #124 to #132, #178: Recommendation details, bulk actions, exports, and rejections."""
    # 178. GET /recommendations (global list)
    global_recs = client.get("/api/v1/recommendations", headers=pm_headers)
    assert global_recs.status_code == 200
    assert "items" in global_recs.json()

    # 124. GET /optimization-runs/{run_id}/recommendations
    run_recs = client.get("/api/v1/optimization-runs/opt_dummy_run_001/recommendations", headers=pm_headers)
    assert run_recs.status_code == 200

    # 130. GET /optimization-runs/{run_id}/recommendations/export (csv & json)
    export_csv = client.get("/api/v1/optimization-runs/opt_dummy_run_001/recommendations/export?format=csv", headers=pm_headers)
    assert export_csv.status_code == 200
    assert "text/csv" in export_csv.headers["content-type"]

    export_json = client.get("/api/v1/optimization-runs/opt_dummy_run_001/recommendations/export?format=json", headers=pm_headers)
    assert export_json.status_code == 200
    assert "application/json" in export_json.headers["content-type"]

    # 131. GET /optimization-runs/{run_id}/rejections
    rejections_res = client.get("/api/v1/optimization-runs/opt_dummy_run_001/rejections", headers=pm_headers)
    assert rejections_res.status_code == 200

    # 132. GET /optimization-runs/{run_id}/rejections/summary
    summary_res = client.get("/api/v1/optimization-runs/opt_dummy_run_001/rejections/summary", headers=pm_headers)
    assert summary_res.status_code == 200
    assert "breakdown" in summary_res.json()
