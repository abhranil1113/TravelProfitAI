from __future__ import annotations

import pytest


def test_supplier_offers_crud(client, admin_headers, pm_headers):
    """Test #48 to #54: Supplier offers lifecycle, bulk import, predictions, and expiration."""
    # Seed destination, supplier, and inventory item
    dest_res = client.post(
        "/api/v1/destinations",
        headers=admin_headers,
        json={"dest_id": "BLR", "dest_code": "BLR", "name": "Bangalore", "city": "Bangalore", "country": "India", "airport_code": "BLR", "tier": "T1"}
    )
    dest_id = dest_res.json()["id"]

    supp_res = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={"supplier_code": "SUP-BLR-01", "name": "Bangalore Luxury Suites", "supplier_type": "HOTEL", "status": "ACTIVE"}
    )
    supp_id = supp_res.json()["id"]

    item_res = client.post(
        "/api/v1/inventory-items",
        headers=admin_headers,
        json={
            "inventory_id": "INV-BLR-01",
            "category": "HOTEL",
            "unit_type": "ROOM_NIGHT",
            "dest_id": dest_id,
            "name": "Executive City Suite",
            "base_cost_inr": 6000.00,
            "total_capacity": 30,
            "available_units": 30,
        }
    )
    item_id = item_res.json()["id"]

    # 49. POST /supplier-offers (create offer)
    create_offer = client.post(
        "/api/v1/supplier-offers",
        headers=admin_headers,
        json={
            "supplier_id": supp_id,
            "inventory_item_id": item_id,
            "offer_price_inr": 5500.00,
            "min_quantity": 5,
            "max_quantity": 25,
            "available_units": 25,
            "valid_from": "2026-11-24",
            "valid_to": "2026-12-31",
            "currency": "INR",
            "status": "ACTIVE",
        }
    )
    assert create_offer.status_code == 201
    offer_id = create_offer.json()["id"]

    # 48. GET /supplier-offers (list)
    list_offers = client.get("/api/v1/supplier-offers", headers=pm_headers)
    assert list_offers.status_code == 200
    assert len(list_offers.json()["items"]) >= 1

    # 50. GET /supplier-offers/{offer_id} (detail)
    get_offer = client.get(f"/api/v1/supplier-offers/{offer_id}", headers=pm_headers)
    assert get_offer.status_code == 200
    assert get_offer.json()["supplier_id"] == supp_id

    # 51. PATCH /supplier-offers/{offer_id} (update)
    patch_offer = client.patch(
        f"/api/v1/supplier-offers/{offer_id}",
        headers=admin_headers,
        json={"offer_price_inr": 5200.00}
    )
    assert patch_offer.status_code == 200
    assert float(patch_offer.json()["offer_price_inr"]) == 5200.00

    # 54. GET /supplier-offers/{offer_id}/predictions
    pred_res = client.get(f"/api/v1/supplier-offers/{offer_id}/predictions", headers=pm_headers)
    assert pred_res.status_code == 200

    # 53. POST /supplier-offers/bulk-import
    bulk_res = client.post(
        "/api/v1/supplier-offers/bulk-import",
        headers=admin_headers,
        json={
            "offers": [
                {
                    "supplier_id": supp_id,
                    "inventory_item_id": item_id,
                    "offer_price_inr": 5100.00,
                    "min_quantity": 2,
                    "max_quantity": 10,
                    "available_units": 10,
                    "valid_from": "2026-12-01",
                    "valid_to": "2026-12-25",
                }
            ]
        }
    )
    assert bulk_res.status_code == 201
    assert bulk_res.json()["imported_count"] == 1

    # 52. POST /supplier-offers/{offer_id}/expire
    exp_res = client.post(f"/api/v1/supplier-offers/{offer_id}/expire", headers=admin_headers)
    assert exp_res.status_code == 200
    assert exp_res.json()["status"] == "EXPIRED"
