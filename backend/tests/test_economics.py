from __future__ import annotations

import pytest


def test_economics_simulation(client, pm_headers):
    """Test #177: POST /economics/simulate."""
    # Hotel simulation
    hotel_res = client.post(
        "/api/v1/economics/simulate",
        headers=pm_headers,
        json={
            "inventory_category": "HOTEL",
            "unit_cost_inr": 5000.00,
            "expected_sale_price_inr": 7000.00,
            "demand_quantity": 20,
            "cancellation_probability": 0.15,
            "salvage_rate_pct": 0.10,
        }
    )
    assert hotel_res.status_code == 200
    h_data = hotel_res.json()
    assert float(h_data["expected_unit_contribution_inr"]) > 0
    assert float(h_data["expected_net_profit_inr"]) > 0
    assert "risk_assessment" in h_data

    # Flight simulation
    flight_res = client.post(
        "/api/v1/economics/simulate",
        headers=pm_headers,
        json={
            "inventory_category": "FLIGHT",
            "unit_cost_inr": 6000.00,
            "expected_sale_price_inr": 8500.00,
            "demand_quantity": 15,
            "cancellation_probability": 0.08,
            "salvage_rate_pct": 0.15,
        }
    )
    assert flight_res.status_code == 200
    f_data = flight_res.json()
    assert float(f_data["expected_unit_contribution_inr"]) > 0
