from __future__ import annotations

import pytest


def test_list_users_rbac(client, admin_headers, pm_headers):
    """Test #11 GET /users - list users (Admin only)."""
    # PM forbidden
    res_pm = client.get("/api/v1/users", headers=pm_headers)
    assert res_pm.status_code == 403

    # Admin authorized
    res_admin = client.get("/api/v1/users", headers=admin_headers)
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert "items" in data
    assert data["total"] >= 4


def test_create_and_get_user(client, admin_headers):
    """Test #12 POST /users and #13 GET /users/{id}."""
    # Create user
    create_res = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": "finance@inventoryiq.com", "full_name": "Finance Head", "password": "FinancePass123!", "role": "PROCUREMENT_MANAGER"}
    )
    assert create_res.status_code == 201
    user_id = create_res.json()["id"]

    # Get user by id
    get_res = client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["email"] == "finance@inventoryiq.com"


def test_update_user(client, admin_headers):
    """Test #14 PATCH /users/{id}."""
    res = client.patch(
        "/api/v1/users/3",
        headers=admin_headers,
        json={"full_name": "Senior Analyst"}
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Senior Analyst"


def test_deactivate_and_reactivate_user(client, admin_headers):
    """Test #16 POST /users/{id}/deactivate and #17 POST /users/{id}/reactivate."""
    # Deactivate
    deact_res = client.post("/api/v1/users/3/deactivate", headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # Reactivate
    react_res = client.post("/api/v1/users/3/reactivate", headers=admin_headers)
    assert react_res.status_code == 200
    assert react_res.json()["is_active"] is True


def test_unlock_user(client, admin_headers):
    """Test #18 POST /users/{id}/unlock."""
    res = client.post("/api/v1/users/4/unlock", headers=admin_headers)
    assert res.status_code == 200


def test_force_password_reset(client, admin_headers):
    """Test #19 POST /users/{id}/force-password-reset."""
    res = client.post("/api/v1/users/3/force-password-reset", headers=admin_headers)
    assert res.status_code == 200


def test_delete_user(client, admin_headers):
    """Test #15 DELETE /users/{id}."""
    # Create temp user to delete
    create_res = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": "temp@inventoryiq.com", "full_name": "Temp User", "password": "TempPass123!", "role": "ANALYST"}
    )
    user_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert del_res.status_code in (200, 204)
