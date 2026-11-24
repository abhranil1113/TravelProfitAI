from __future__ import annotations

import pytest


def test_analytics_dashboard_and_scorecards(client, admin_headers, pm_headers, analyst_headers):
    """Test #172 to #175: Analytics executive dashboard, profitability, cancellation risk, and supplier scorecard."""
    # 172. GET /analytics/dashboard
    dash_res = client.get("/api/v1/analytics/dashboard", headers=pm_headers)
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert "total_spend_inr" in dash
    assert "total_expected_profit_inr" in dash
    assert "portfolio_roi_pct" in dash

    # 173. GET /analytics/profitability
    prof_res = client.get("/api/v1/analytics/profitability", headers=analyst_headers)
    assert prof_res.status_code == 200
    assert "destination_profitability" in prof_res.json()
    assert "supplier_profitability" in prof_res.json()

    # 174. GET /analytics/cancellation-and-pricing
    risk_res = client.get("/api/v1/analytics/cancellation-and-pricing", headers=analyst_headers)
    assert risk_res.status_code == 200
    assert "average_hotel_cancellation_rate" in risk_res.json()
    assert "price_elasticity_summary" in risk_res.json()

    # 175. GET /analytics/suppliers/scorecard
    score_res = client.get("/api/v1/analytics/suppliers/scorecard", headers=analyst_headers)
    assert score_res.status_code == 200
    assert "items" in score_res.json()
