"""
Tests for EDA Report Generation Module
Verifies generation of all 10 reports and summary JSON.
"""

import pytest
import json
from pathlib import Path
from eda.config import REPORTS_DIR, FIGURES_DIR, TABLES_DIR
from eda.main import run_full_eda_pipeline


def test_full_pipeline_and_reports_generation():
    """Verify end-to-end pipeline execution and output verification."""
    result = run_full_eda_pipeline()
    assert result["status"] == "success"
    assert result["reports_generated"] == 10

    expected_reports = [
        "dataset_overview.md",
        "hotel_booking_analysis.md",
        "flight_operations_analysis.md",
        "flight_price_analysis.md",
        "customer_search_analysis.md",
        "supplier_inventory_analysis.md",
        "market_seasonality_analysis.md",
        "combined_business_insights.md",
        "modeling_readiness_assessment.md",
        "eda_summary.json",
    ]

    for rep in expected_reports:
        rep_path = REPORTS_DIR / rep
        assert rep_path.exists(), f"Report {rep} not found in {REPORTS_DIR}"
        assert rep_path.stat().st_size > 0, f"Report {rep} is empty"

    # Verify JSON structure
    json_path = REPORTS_DIR / "eda_summary.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["project"] == "TBO InventoryIQ"
    assert "kpis" in data
    assert "business_insights" in data
    assert "modeling_readiness" in data


def test_visualizations_exist():
    """Verify all critical figures exist and have non-zero size."""
    expected_figures = [
        "hotel_cancellation_by_lead_time.png",
        "hotel_adr_by_market_segment.png",
        "flight_price_by_days_left.png",
        "flight_price_economy_vs_business.png",
        "flight_delay_causes_breakdown.png",
        "flight_ontime_by_airline.png",
        "customer_search_conversion_funnel.png",
        "search_demand_by_destination.png",
        "inventory_utilization_distribution.png",
        "supplier_markup_and_margin_by_supplier.png",
        "market_seasonality_index_monthly.png",
        "cross_domain_demand_vs_supply_gap.png",
        "correlation_heatmap_hotel.png",
        "correlation_heatmap_flight_prices.png",
    ]

    for fig in expected_figures:
        fig_path = FIGURES_DIR / fig
        assert fig_path.exists(), f"Figure {fig} not found in {FIGURES_DIR}"
        assert fig_path.stat().st_size > 1000, f"Figure {fig} is unusually small"
