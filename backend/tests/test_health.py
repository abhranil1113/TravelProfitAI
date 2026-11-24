from __future__ import annotations

import pytest


def test_root_and_v1_health(client, admin_headers):
    """Test Root /health, #168 GET /health, #169 /ready, #170 /version, #171 /champion-models."""
    # Root /health
    root_res = client.get("/health")
    assert root_res.status_code == 200
    assert root_res.json()["status"] == "ok"

    # #168 GET /api/v1/health
    v1_res = client.get("/api/v1/health")
    assert v1_res.status_code == 200
    assert v1_res.json()["status"] == "ok"

    # #169 GET /api/v1/health/ready
    ready_res = client.get("/api/v1/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] in ("ready", "degraded")

    # #170 GET /api/v1/health/version
    version_res = client.get("/api/v1/health/version")
    assert version_res.status_code == 200
    assert "version" in version_res.json()
    assert "environment" in version_res.json()

    # #171 GET /api/v1/health/champion-models (Admin only)
    champ_res = client.get("/api/v1/health/champion-models", headers=admin_headers)
    assert champ_res.status_code == 200
    assert "models" in champ_res.json()
