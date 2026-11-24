from __future__ import annotations

import pytest


def test_inventory_and_snapshots(client, admin_headers, pm_headers):
    """Test #40 to #47: Inventory items, snapshots, and bulk ingestion."""
    # First seed a destination
    dest_res = client.post(
        "/api/v1/destinations",
        headers=admin_headers,
        json={"dest_id": "DEL", "dest_code": "DEL", "name": "New Delhi", "city": "Delhi", "country": "India", "airport_code": "DEL", "tier": "T1"}
    )
    dest_id = dest_res.json()["id"]

    # 41. POST /inventory-items (create)
    item_res = client.post(
        "/api/v1/inventory-items",
        headers=admin_headers,
        json={
            "inventory_id": "INV-DEL-HTL-001",
            "category": "HOTEL",
            "unit_type": "ROOM_NIGHT",
            "dest_id": dest_id,
            "name": "The Oberoi New Delhi Deluxe Room",
            "base_cost_inr": 8500.00,
            "published_price_inr": 12000.00,
            "total_capacity": 50,
            "available_units": 45,
            "status": "ACTIVE",
        }
    )
    assert item_res.status_code == 201
    item_data = item_res.json()
    item_id = item_data["id"]

    # 40. GET /inventory-items (list)
    list_res = client.get("/api/v1/inventory-items", headers=pm_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) >= 1

    # 42. GET /inventory-items/{inventory_id} (detail)
    get_res = client.get(f"/api/v1/inventory-items/{item_id}", headers=pm_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "The Oberoi New Delhi Deluxe Room"

    # 43. PATCH /inventory-items/{inventory_id} (update)
    patch_res = client.patch(
        f"/api/v1/inventory-items/{item_id}",
        headers=admin_headers,
        json={"published_price_inr": 13500.00}
    )
    assert patch_res.status_code == 200
    assert float(patch_res.json()["published_price_inr"]) == 13500.00

    # 45. POST /inventory-snapshots (single snapshot)
    snap_res = client.post(
        "/api/v1/inventory-snapshots",
        headers=admin_headers,
        json={
            "inventory_item_id": item_id,
            "snapshot_date": "2026-11-24",
            "available_capacity": 42,
            "booked_units": 8,
            "current_competitor_price_inr": 13000.00,
        }
    )
    assert snap_res.status_code == 201

    # 46. POST /inventory-snapshots/bulk (bulk snapshot)
    bulk_res = client.post(
        "/api/v1/inventory-snapshots/bulk",
        headers=admin_headers,
        json={
            "snapshots": [
                {
                    "inventory_item_id": item_id,
                    "snapshot_date": "2026-11-25",
                    "available_capacity": 40,
                    "booked_units": 10,
                }
            ]
        }
    )
    assert bulk_res.status_code == 201

    # 44. GET /inventory-items/{inventory_id}/snapshots
    hist_res = client.get(f"/api/v1/inventory-items/{item_id}/snapshots", headers=pm_headers)
    assert hist_res.status_code == 200
    assert len(hist_res.json()["items"]) >= 1

    # 47. GET /inventory-items/{inventory_id}/offers
    item_offers = client.get(f"/api/v1/inventory-items/{item_id}/offers", headers=pm_headers)
    assert item_offers.status_code == 200
