from __future__ import annotations

import pytest


def test_forecasts_and_predictions(client, admin_headers, pm_headers):
    """Test #82 to #87: Offer predictions, demand & inventory forecasts, and chart analytics."""
    # 82. GET /predictions/offers
    preds_res = client.get("/api/v1/predictions/offers", headers=pm_headers)
    assert preds_res.status_code == 200

    # 83. POST /predictions/offers/generate
    gen_res = client.post("/api/v1/predictions/offers/generate", headers=admin_headers, json={"offer_ids": [1, 2]})
    assert gen_res.status_code == 200

    # 84. GET /forecasts/demand
    demand_res = client.get("/api/v1/forecasts/demand", headers=pm_headers)
    assert demand_res.status_code == 200

    # Seed BOM destination
    client.post(
        "/api/v1/destinations",
        headers=admin_headers,
        json={"dest_id": "BOM", "name": "Mumbai", "city": "Mumbai", "country": "India"},
    )

    # 85. GET /forecasts/demand/{dest_id}/chart
    chart_res = client.get("/api/v1/forecasts/demand/BOM/chart", headers=pm_headers)
    assert chart_res.status_code == 200
    assert "time_series" in chart_res.json()

    # 86. GET /forecasts/inventory
    inv_res = client.get("/api/v1/forecasts/inventory", headers=pm_headers)
    assert inv_res.status_code == 200

    # 87. POST /forecasts/materialize
    mat_res = client.post("/api/v1/forecasts/materialize", headers=admin_headers, json={"horizon_days": 30})
    assert mat_res.status_code == 200
    assert "task_id" in mat_res.json()
