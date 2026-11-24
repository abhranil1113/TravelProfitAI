from __future__ import annotations

import pytest


def test_reference_data_and_signals(client, admin_headers, pm_headers):
    """Test #55 to #63: Market signals, exchange rates, and segment baselines."""
    # 56. POST /market-signals (create)
    sig_res = client.post(
        "/api/v1/market-signals",
        headers=admin_headers,
        json={
            "dest_id": "BOM",
            "signal_type": "DEMAND_SURGE",
            "signal_value": 1.45,
            "confidence": 0.88,
            "headline": "Cricket World Cup Quarterfinals in Mumbai",
            "is_active": True,
        }
    )
    assert sig_res.status_code == 201
    sig_id = sig_res.json()["id"]

    # 55. GET /market-signals (list)
    list_sig = client.get("/api/v1/market-signals", headers=pm_headers)
    assert list_sig.status_code == 200
    assert len(list_sig.json()["items"]) >= 1

    # 57. PATCH /market-signals/{id} (update)
    patch_sig = client.patch(
        f"/api/v1/market-signals/{sig_id}",
        headers=admin_headers,
        json={"signal_value": 1.60}
    )
    assert patch_sig.status_code == 200
    assert float(patch_sig.json()["signal_value"]) == 1.60

    # 60. POST /exchange-rates (create rate)
    rate_res = client.post(
        "/api/v1/exchange-rates",
        headers=admin_headers,
        json={
            "source_currency": "USD",
            "target_currency": "INR",
            "rate": 83.50,
            "rate_date": "2026-11-24",
        }
    )
    assert rate_res.status_code == 201

    # 59. GET /exchange-rates (list)
    rates_list = client.get("/api/v1/exchange-rates", headers=pm_headers)
    assert rates_list.status_code == 200
    assert len(rates_list.json()["items"]) >= 1

    # 61. GET /exchange-rates/latest
    latest_res = client.get("/api/v1/exchange-rates/latest?source_currency=USD&target_currency=INR", headers=pm_headers)
    assert latest_res.status_code == 200
    assert float(latest_res.json()["rate"]) == 83.50

    # 63. PUT /market-segment-baselines/{segment_name}
    base_put = client.put(
        "/api/v1/market-segment-baselines/LEISURE_BEACH",
        headers=admin_headers,
        json={
            "inventory_category": "HOTEL",
            "avg_base_price_inr": 7200.00,
            "avg_cancellation_rate": 0.18,
            "typical_lead_time_days": 14,
        }
    )
    assert base_put.status_code == 200

    # 62. GET /market-segment-baselines
    base_list = client.get("/api/v1/market-segment-baselines", headers=pm_headers)
    assert base_list.status_code == 200
    assert len(base_list.json()) >= 1

    # 58. DELETE /market-signals/{id}
    del_sig = client.delete(f"/api/v1/market-signals/{sig_id}", headers=admin_headers)
    assert del_sig.status_code in (200, 204)
