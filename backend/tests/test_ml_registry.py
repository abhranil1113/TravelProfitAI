from __future__ import annotations

import pytest


def test_ml_registry_and_training(client, admin_headers, analyst_headers):
    """Test #70 to #81: Feature sets, ML model registry, promotion, retiring, and training runs."""
    # 71. POST /ml/feature-sets (create feature set)
    fs_res = client.post(
        "/api/v1/ml/feature-sets",
        headers=analyst_headers,
        json={
            "name": "hotel_cancellation_features_v2",
            "version": "v2.0",
            "model_type": "hotel_cancellation",
            "parquet_path": "data/features/cancellation_v2.parquet",
            "num_rows": 15000,
            "num_features": 24,
            "column_names": ["lead_time", "star_rating", "price_diff", "historical_cancel_rate"],
        }
    )
    assert fs_res.status_code == 201
    fs_id = fs_res.json()["id"]

    # 70. GET /ml/feature-sets (list)
    fs_list = client.get("/api/v1/ml/feature-sets", headers=analyst_headers)
    assert fs_list.status_code == 200
    assert len(fs_list.json()) >= 1

    # 72. GET /ml/feature-sets/{id} (detail)
    fs_get = client.get(f"/api/v1/ml/feature-sets/{fs_id}", headers=analyst_headers)
    assert fs_get.status_code == 200
    assert fs_get.json()["name"] == "hotel_cancellation_features_v2"

    # 78. POST /ml/training-runs (trigger training)
    train_res = client.post(
        "/api/v1/ml/training-runs",
        headers=analyst_headers,
        json={
            "model_type": "hotel_cancellation",
            "feature_set_id": fs_id,
            "algorithm": "LightGBM",
            "cv_folds": 5,
        }
    )
    assert train_res.status_code == 201
    run_id = train_res.json()["id"]

    # 77. GET /ml/training-runs (list)
    runs_list = client.get("/api/v1/ml/training-runs", headers=analyst_headers)
    assert runs_list.status_code == 200
    assert len(runs_list.json()["items"]) >= 1

    # 79. GET /ml/training-runs/{id} (detail)
    run_get = client.get(f"/api/v1/ml/training-runs/{run_id}", headers=analyst_headers)
    assert run_get.status_code == 200
    assert run_get.json()["id"] == run_id

    # 80. POST /ml/training-runs/{id}/cancel
    cancel_res = client.post(f"/api/v1/ml/training-runs/{run_id}/cancel", headers=admin_headers)
    assert cancel_res.status_code == 200

    # 74. GET /ml/models/champions
    champs = client.get("/api/v1/ml/models/champions", headers=analyst_headers)
    assert champs.status_code == 200

    # 73. GET /ml/models (list)
    models_res = client.get("/api/v1/ml/models", headers=analyst_headers)
    assert models_res.status_code == 200

    # If any models exist, test detail, promote, retire
    if models_res.json()["total"] > 0:
        mid = models_res.json()["items"][0]["id"]
        # 75. GET /ml/models/{id}
        m_get = client.get(f"/api/v1/ml/models/{mid}", headers=analyst_headers)
        assert m_get.status_code == 200

        # 76. POST /ml/models/{id}/promote
        m_prom = client.post(f"/api/v1/ml/models/{mid}/promote", headers=admin_headers)
        assert m_prom.status_code == 200

        # 81. POST /ml/models/{id}/retire
        m_ret = client.post(f"/api/v1/ml/models/{mid}/retire", headers=admin_headers)
        assert m_ret.status_code == 200
