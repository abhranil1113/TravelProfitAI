from __future__ import annotations

import pytest


def test_pipelines_and_quality(client, admin_headers, pm_headers, worker_headers):
    """Test #64 to #69: Ingestion batches, quality reports, and retry triggers."""
    # 65. POST /pipelines/batches (create batch)
    create_batch = client.post(
        "/api/v1/pipelines/batches",
        headers=admin_headers,
        json={
            "source_type": "SUPPLIER_FEED",
            "source_name": "hotel_beds_daily_feed",
            "file_path": "data/feeds/hotelbeds_20261124.csv",
            "record_count": 500,
        }
    )
    assert create_batch.status_code == 201
    batch_uid = create_batch.json()["batch_uid"]

    # 64. GET /pipelines/batches (list batches)
    list_batches = client.get("/api/v1/pipelines/batches", headers=pm_headers)
    assert list_batches.status_code == 200
    assert len(list_batches.json()["items"]) >= 1

    # 69. GET /pipelines/quality-summary
    summary_res = client.get("/api/v1/pipelines/quality-summary", headers=pm_headers)
    assert summary_res.status_code == 200

    # 66. GET /pipelines/batches/{batch_uid} (detail)
    get_batch = client.get(f"/api/v1/pipelines/batches/{batch_uid}", headers=pm_headers)
    assert get_batch.status_code == 200
    assert get_batch.json()["batch_uid"] == batch_uid

    # 67. GET /pipelines/batches/{batch_uid}/quality-reports
    quality_res = client.get(f"/api/v1/pipelines/batches/{batch_uid}/quality-reports", headers=pm_headers)
    assert quality_res.status_code == 200

    # 68. POST /pipelines/batches/{batch_uid}/retry
    retry_res = client.post(f"/api/v1/pipelines/batches/{batch_uid}/retry", headers=admin_headers)
    assert retry_res.status_code == 200
