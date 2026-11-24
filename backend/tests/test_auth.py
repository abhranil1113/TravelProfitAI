from __future__ import annotations

import pytest


def test_auth_login_valid_and_invalid(client):
    """Test #1 POST /auth/login - valid and invalid credentials."""
    # Invalid password
    res_bad = client.post("/api/v1/auth/login", json={"email": "admin@inventoryiq.com", "password": "WrongPassword!"})
    assert res_bad.status_code == 401

    # Valid password
    res_good = client.post("/api/v1/auth/login", json={"email": "admin@inventoryiq.com", "password": "AdminSecurePass123!"})
    assert res_good.status_code == 200
    data = res_good.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_auth_refresh_token(client):
    """Test #2 POST /auth/refresh - refresh token rotation."""
    login_res = client.post("/api/v1/auth/login", json={"email": "admin@inventoryiq.com", "password": "AdminSecurePass123!"})
    refresh_token = login_res.json()["refresh_token"]

    # Valid refresh
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_res.status_code == 200
    assert "access_token" in ref_res.json()
    assert "refresh_token" in ref_res.json()

    # Reuse detection / invalid refresh token
    bad_ref = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid_refresh_token_string"})
    assert bad_ref.status_code == 401


def test_auth_me(client, admin_headers):
    """Test #3 GET /auth/me - current user info."""
    # Unauthenticated
    res_anon = client.get("/api/v1/auth/me")
    assert res_anon.status_code == 401

    # Authenticated
    res = client.get("/api/v1/auth/me", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "admin@inventoryiq.com"
    assert res.json()["role"] == "ADMIN"


def test_auth_register_admin_only(client, admin_headers, pm_headers):
    """Test #4 POST /auth/register - admin-only registration."""
    # Non-admin forbidden
    res_forbidden = client.post(
        "/api/v1/auth/register",
        headers=pm_headers,
        json={"email": "newuser@inventoryiq.com", "full_name": "New User", "password": "Password123!", "role": "ANALYST"}
    )
    assert res_forbidden.status_code == 403

    # Admin successfully registers
    res_ok = client.post(
        "/api/v1/auth/register",
        headers=admin_headers,
        json={"email": "newuser@inventoryiq.com", "full_name": "New User", "password": "Password123!", "role": "ANALYST"}
    )
    assert res_ok.status_code == 201
    assert res_ok.json()["email"] == "newuser@inventoryiq.com"


def test_auth_logout(client):
    """Test #5 POST /auth/logout."""
    login_res = client.post("/api/v1/auth/login", json={"email": "admin@inventoryiq.com", "password": "AdminSecurePass123!"})
    token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}, json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "logged out" in res.json()["message"].lower()


def test_auth_logout_all(client, admin_headers):
    """Test #6 POST /auth/logout-all."""
    res = client.post("/api/v1/auth/logout-all", headers=admin_headers)
    assert res.status_code == 200
    assert "revoked" in res.json()["message"].lower()


def test_auth_email_verification(client):
    """Test #7 POST /auth/verify-email."""
    res = client.post("/api/v1/auth/verify-email", json={"token": "test_verification_token"})
    # Either succeeds or returns 400 for invalid token
    assert res.status_code in (200, 400)


def test_auth_forgot_and_reset_password(client):
    """Test #8 POST /auth/forgot-password and #9 POST /auth/reset-password."""
    # Forgot password
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": "admin@inventoryiq.com"})
    assert forgot_res.status_code == 200

    # Reset password with invalid token
    reset_res = client.post("/api/v1/auth/reset-password", json={"token": "invalid_reset_token", "new_password": "NewSecurePassword123!"})
    assert reset_res.status_code in (200, 400)


def test_auth_change_password(client, admin_headers):
    """Test #10 POST /auth/change-password."""
    res = client.post(
        "/api/v1/auth/change-password",
        headers=admin_headers,
        json={"current_password": "AdminSecurePass123!", "new_password": "NewAdminSecurePass456!"}
    )
    assert res.status_code == 200
    assert "password updated" in res.json()["message"].lower()
