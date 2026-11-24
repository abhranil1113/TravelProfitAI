from __future__ import annotations

import pytest


def test_destination_crud_and_metrics(client, admin_headers, pm_headers):
    """Test #20 to #26: Destination CRUD, metrics, and search velocity."""
    # 21. POST /destinations (create)
    create_res = client.post(
        "/api/v1/destinations",
        headers=admin_headers,
        json={"dest_id": "GOA", "dest_code": "GOA", "name": "Goa Beachfront", "city": "Goa", "country": "India", "airport_code": "GOI", "tier": "T1"}
    )
    assert create_res.status_code == 201
    dest_data = create_res.json()
    assert dest_data["dest_code"] == "GOA"

    # 20. GET /destinations (list)
    list_res = client.get("/api/v1/destinations", headers=pm_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) >= 1

    # 22. GET /destinations/{dest_id} (detail)
    get_res = client.get("/api/v1/destinations/GOA", headers=pm_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Goa Beachfront"

    # 23. PATCH /destinations/{dest_id} (update)
    patch_res = client.patch(
        "/api/v1/destinations/GOA",
        headers=admin_headers,
        json={"name": "Goa Luxury Resort Strip"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Goa Luxury Resort Strip"

    # 25. GET /destinations/{dest_id}/daily-metrics
    metrics_res = client.get("/api/v1/destinations/GOA/daily-metrics", headers=pm_headers)
    assert metrics_res.status_code == 200
    assert "metrics" in metrics_res.json()

    # 26. GET /destinations/{dest_id}/search-velocity
    velo_res = client.get("/api/v1/destinations/GOA/search-velocity", headers=pm_headers)
    assert velo_res.status_code == 200
    assert "velocity_score" in velo_res.json()

    # 24. DELETE /destinations/{dest_id}
    del_res = client.delete("/api/v1/destinations/GOA", headers=admin_headers)
    assert del_res.status_code == 204
