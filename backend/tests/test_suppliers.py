from __future__ import annotations

import pytest


def test_suppliers_and_contacts_crud(client, admin_headers, pm_headers):
    """Test #27 to #39: Supplier CRUD, contacts, snapshots, and related queries."""
    # 28. POST /suppliers (create)
    create_res = client.post(
        "/api/v1/suppliers",
        headers=admin_headers,
        json={
            "supplier_code": "SUP-TEST-001",
            "name": "Global Grand Resorts",
            "supplier_type": "HOTEL",
            "status": "ACTIVE",
            "country": "India",
            "city": "Mumbai",
            "lead_time_days": 7,
            "cancellation_lead_time_days": 2,
        }
    )
    assert create_res.status_code == 201
    supp_id = create_res.json()["id"]

    # 27. GET /suppliers (list)
    list_res = client.get("/api/v1/suppliers", headers=pm_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) >= 1

    # 29. GET /suppliers/{supplier_id} (detail)
    get_res = client.get(f"/api/v1/suppliers/{supp_id}", headers=pm_headers)
    assert get_res.status_code == 200
    assert get_res.json()["supplier_code"] == "SUP-TEST-001"

    # 30. PATCH /suppliers/{supplier_id} (update)
    patch_res = client.patch(
        f"/api/v1/suppliers/{supp_id}",
        headers=admin_headers,
        json={"name": "Global Luxury Resorts & Spas"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Global Luxury Resorts & Spas"

    # 32. POST /suppliers/{supplier_id}/contacts (create contact)
    contact_res = client.post(
        f"/api/v1/suppliers/{supp_id}/contacts",
        headers=admin_headers,
        json={
            "contact_name": "Rajesh Kumar",
            "email": "rajesh@grandresorts.com",
            "phone": "+919876543210",
            "designation": "Key Account Manager",
            "is_primary": True,
        }
    )
    assert contact_res.status_code == 201
    contact_id = contact_res.json()["id"]

    # 31. GET /suppliers/{supplier_id}/contacts (list contacts)
    contacts_list = client.get(f"/api/v1/suppliers/{supp_id}/contacts", headers=pm_headers)
    assert contacts_list.status_code == 200
    assert len(contacts_list.json()) >= 1

    # 33. PATCH /supplier-contacts/{id} (update contact)
    patch_contact = client.patch(
        f"/api/v1/supplier-contacts/{contact_id}",
        headers=admin_headers,
        json={"designation": "Director of Sales"}
    )
    assert patch_contact.status_code == 200
    assert patch_contact.json()["designation"] == "Director of Sales"

    # 35. POST /supplier-contacts/{id}/set-primary
    set_primary = client.post(f"/api/v1/supplier-contacts/{contact_id}/set-primary", headers=admin_headers)
    assert set_primary.status_code == 200
    assert set_primary.json()["is_primary"] is True

    # 36. GET /suppliers/{supplier_id}/offers
    offers_res = client.get(f"/api/v1/suppliers/{supp_id}/offers", headers=pm_headers)
    assert offers_res.status_code == 200

    # 37. GET /suppliers/{supplier_id}/performance-snapshots
    perf_res = client.get(f"/api/v1/suppliers/{supp_id}/performance-snapshots", headers=pm_headers)
    assert perf_res.status_code == 200

    # 38. GET /suppliers/{supplier_id}/purchase-orders
    pos_res = client.get(f"/api/v1/suppliers/{supp_id}/purchase-orders", headers=pm_headers)
    assert pos_res.status_code == 200

    # 34. DELETE /supplier-contacts/{id}
    del_contact = client.delete(f"/api/v1/supplier-contacts/{contact_id}", headers=admin_headers)
    assert del_contact.status_code == 204

    # 39. DELETE /suppliers/{supplier_id} (soft-delete / status=INACTIVE)
    del_supp = client.delete(f"/api/v1/suppliers/{supp_id}", headers=admin_headers)
    assert del_supp.status_code == 200
    assert del_supp.json()["status"] == "INACTIVE"
