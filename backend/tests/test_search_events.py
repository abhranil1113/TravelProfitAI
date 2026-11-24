from __future__ import annotations

import pytest


def test_search_events_and_funnel(client, admin_headers, pm_headers):
    """Test #163 to #165, #180: Search events ingestion, velocity, and conversion funnel analytics."""
    # 180. POST /search-events/bulk (ingest search events)
    bulk_res = client.post(
        "/api/v1/search-events/bulk",
        headers=admin_headers,
        json={
            "events": [
                {
                    "dest_id": "GOA",
                    "origin_dest_id": "DEL",
                    "search_timestamp": "2026-11-24T10:00:00Z",
                    "check_in_date": "2026-12-10",
                    "check_out_date": "2026-12-15",
                    "inventory_category": "HOTEL",
                    "stay_duration_nights": 5,
                    "converted": True,
                    "conversion_value_inr": 25000.00,
                },
                {
                    "dest_id": "GOA",
                    "origin_dest_id": "BOM",
                    "search_timestamp": "2026-11-24T10:05:00Z",
                    "check_in_date": "2026-12-12",
                    "check_out_date": "2026-12-14",
                    "inventory_category": "HOTEL",
                    "stay_duration_nights": 2,
                    "converted": False,
                }
            ]
        }
    )
    assert bulk_res.status_code == 201
    assert bulk_res.json()["inserted_count"] == 2

    # 163. GET /search-events (list)
    list_res = client.get("/api/v1/search-events", headers=pm_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) >= 2

    # 164. GET /search-events/analytics/velocity
    velo_res = client.get("/api/v1/search-events/analytics/velocity?dest_id=GOA", headers=pm_headers)
    assert velo_res.status_code == 200
    assert "hourly_velocity" in velo_res.json()

    # 165. GET /search-events/analytics/funnel
    funnel_res = client.get("/api/v1/search-events/analytics/funnel?dest_id=GOA", headers=pm_headers)
    assert funnel_res.status_code == 200
    assert "total_searches" in funnel_res.json()
    assert "conversions" in funnel_res.json()
