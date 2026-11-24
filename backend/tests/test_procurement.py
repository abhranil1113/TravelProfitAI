from __future__ import annotations

import pytest


def test_purchase_orders_and_fulfillment(client, admin_headers, pm_headers):
    """Test #133 to #143: Purchase orders, confirmation, lines, fulfillments, and dispute."""
    # Seed supplier and offer
    supp_res = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={"supplier_code": "SUP-PO-01", "name": "PO Test Supplier", "supplier_type": "HOTEL", "status": "ACTIVE"}
    )
    supp_id = supp_res.json()["id"]

    dest_res = client.post(
        "/api/v1/destinations",
        headers=admin_headers,
        json={"dest_id": "MAA", "dest_code": "MAA", "name": "Chennai", "city": "Chennai", "country": "India", "airport_code": "MAA", "tier": "T1"}
    )
    dest_id = dest_res.json()["id"]

    item_res = client.post(
        "/api/v1/inventory-items",
        headers=admin_headers,
        json={"inventory_id": "INV-MAA-01", "category": "HOTEL", "unit_type": "ROOM_NIGHT", "dest_id": dest_id, "name": "Chennai Grand", "base_cost_inr": 4000.00}
    )
    item_id = item_res.json()["id"]

    offer_res = client.post(
        "/api/v1/supplier-offers",
        headers=admin_headers,
        json={"supplier_id": supp_id, "inventory_item_id": item_id, "offer_price_inr": 3800.00, "min_quantity": 2, "max_quantity": 50, "available_units": 50, "valid_from": "2026-11-24", "valid_to": "2026-12-31"}
    )
    offer_id = offer_res.json()["id"]

    # 134. POST /purchase-orders (create PO)
    create_po = client.post(
        "/api/v1/purchase-orders",
        headers=pm_headers,
        json={
            "supplier_id": supp_id,
            "lines": [
                {"offer_id": offer_id, "ordered_qty": 10, "unit_cost_inr": 3800.00}
            ],
            "notes": "Urgent procurement batch",
        }
    )
    assert create_po.status_code == 201
    po_number = create_po.json()["po_number"]

    # 133. GET /purchase-orders (list)
    list_pos = client.get("/api/v1/purchase-orders", headers=pm_headers)
    assert list_pos.status_code == 200
    assert len(list_pos.json()["items"]) >= 1

    # 135. GET /purchase-orders/{po_number} (detail)
    get_po = client.get(f"/api/v1/purchase-orders/{po_number}", headers=pm_headers)
    assert get_po.status_code == 200
    assert get_po.json()["po_number"] == po_number

    # 138. GET /purchase-orders/{po_number}/lines
    lines_res = client.get(f"/api/v1/purchase-orders/{po_number}/lines", headers=pm_headers)
    assert lines_res.status_code == 200
    assert len(lines_res.json()) >= 1
    line_id = lines_res.json()[0]["id"]

    # 136. POST /purchase-orders/{po_number}/confirm
    conf_res = client.post(f"/api/v1/purchase-orders/{po_number}/confirm", headers=pm_headers, json={"notes": "Supplier confirmed via email"})
    assert conf_res.status_code == 200
    assert conf_res.json()["status"] == "CONFIRMED"

    # 139. GET /purchase-orders/{po_number}/export (json & csv)
    exp_json = client.get(f"/api/v1/purchase-orders/{po_number}/export?format=json", headers=pm_headers)
    assert exp_json.status_code == 200
    assert "application/json" in exp_json.headers["content-type"]

    exp_csv = client.get(f"/api/v1/purchase-orders/{po_number}/export?format=csv", headers=pm_headers)
    assert exp_csv.status_code == 200
    assert "text/csv" in exp_csv.headers["content-type"]

    # 141. POST /purchase-orders/{po_number}/lines/{line_id}/fulfillments (record fulfillment)
    ful_res = client.post(
        f"/api/v1/purchase-orders/{po_number}/lines/{line_id}/fulfillments",
        headers=pm_headers,
        json={"delivered_qty": 8, "notes": "8 rooms delivered on schedule"}
    )
    assert ful_res.status_code == 201
    ful_id = ful_res.json()["id"]

    # 140. GET /purchase-orders/{po_number}/fulfillments
    ful_list = client.get(f"/api/v1/purchase-orders/{po_number}/fulfillments", headers=pm_headers)
    assert ful_list.status_code == 200
    assert len(ful_list.json()) >= 1

    # 142. PATCH /purchase-order-fulfillments/{id}
    patch_ful = client.patch(
        f"/api/v1/purchase-order-fulfillments/{ful_id}",
        headers=pm_headers,
        json={"notes": "Updated fulfillment delivery notes"}
    )
    assert patch_ful.status_code == 200

    # 143. POST /purchase-order-fulfillments/{id}/dispute
    disp_res = client.post(
        f"/api/v1/purchase-order-fulfillments/{ful_id}/dispute",
        headers=pm_headers,
        json={"dispute_reason": "2 rooms damaged and unlivable"}
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["status"] == "DISPUTED"

    # 137. POST /purchase-orders/{po_number}/cancel (on a fresh unconfirmed PO)
    cancel_po = client.post(
        "/api/v1/purchase-orders",
        headers=pm_headers,
        json={"supplier_id": supp_id, "lines": [{"offer_id": offer_id, "ordered_qty": 2, "unit_cost_inr": 3800.00}]}
    ).json()["po_number"]
    can_res = client.post(f"/api/v1/purchase-orders/{cancel_po}/cancel", headers=pm_headers, json={"reason": "Test cancellation"})
    assert can_res.status_code == 200
    assert can_res.json()["status"] == "CANCELLED"
