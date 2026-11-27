from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from data_pipeline.validation.validation_report import run_and_save_validation_reports
from eda.kpi_calculations import compute_supplier_kpis
from feature_engineering.aggregation import build_destination_demand_supply_indicators
from ml_engine.config import MLEngineConfig
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.monitoring.data_drift import DataDriftDetector
from ml_engine.price_prediction.price_prediction_service import PricePredictionService
from optimization.config import FinancialAssumptions, OptimizationConfig
from optimization.economics.flight_economics import FlightEconomicsCalculator
from optimization.economics.hotel_economics import HotelEconomicsCalculator
from optimization.predictions.hotel_cancellation import HotelCancellationService
from optimization.predictions.inventory_forecasting import InventoryForecastingService
from optimization.predictions.model_registry import ModelRegistry
from backend.app.services.risk_service import _compute_empirical_var_cvar


def test_hotel_4_outcome_economics_exact_math():
    """Independently validates Hotel 4-outcome expected profit math against HotelEconomicsCalculator."""
    assump = FinancialAssumptions(
        hotel_base_sell_through=0.80,
        hotel_customer_refund_rate=0.80,
        hotel_supplier_refund_rate_cancel=0.85,
        hotel_supplier_refund_rate_unsold=0.0,
        hotel_room_resale_probability=0.40,
        hotel_resale_discount_factor=0.90,
    )
    calc = HotelEconomicsCalculator(assump)

    c_h, p_h = 3000.0, 4800.0
    theta, c_prob = 0.75, 0.25

    res = calc.calculate_expected_contribution(
        purchase_cost=c_h,
        selling_price=p_h,
        cancellation_prob=c_prob,
        is_supplier_refundable=True,
        sell_through_prob=theta,
    )

    # Independent 4-outcome hand calculation:
    p_unsold = 1.0 - theta
    p_comp = theta * (1.0 - c_prob)
    p_resold = theta * c_prob * 0.40
    p_unresold = theta * c_prob * (1.0 - 0.40)

    rev_unsold = 0.0 * c_h
    rev_comp = p_h
    rev_resold = (1.0 - 0.80) * p_h + 0.90 * p_h
    rev_unresold = (1.0 - 0.80) * p_h + 0.85 * c_h
    expected_gross = (p_unsold * rev_unsold) + (p_comp * rev_comp) + (p_resold * rev_resold) + (p_unresold * rev_unresold)
    expected_net = expected_gross - c_h

    assert math.isclose(res["p_unsold"] + res["p_completed"] + res["p_cancelled_resold"] + res["p_cancelled_unresold"], 1.0, rel_tol=1e-9)
    assert math.isclose(res["expected_gross_revenue"], expected_gross, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(res["expected_net_contribution"], expected_net, rel_tol=1e-9, abs_tol=1e-9)


def test_flight_spoilage_salvage_and_breakeven_math():
    """Independently validates Flight spoilage/salvage profit and breakeven sell-through threshold."""
    assump = FinancialAssumptions(flight_unsold_penalty=150.0, flight_salvage_rate_optional=0.10)
    calc = FlightEconomicsCalculator(assump, use_optional_salvage=True)

    c_f, p_f, theta = 4000.0, 5600.0, 0.70
    res = calc.calculate_expected_contribution(
        purchase_cost=c_f,
        contract_selling_price=p_f,
        sell_through=theta,
    )
    salvage = 0.10 * c_f
    expected_gross = (theta * p_f) + ((1.0 - theta) * (salvage - 150.0))
    expected_net = expected_gross - c_f
    theta_star = (c_f + 150.0 - salvage) / (p_f - salvage + 150.0)

    assert math.isclose(res["expected_net_contribution"], expected_net, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(calc.calculate_breakeven_sell_through(c_f, p_f), theta_star, rel_tol=1e-9, abs_tol=1e-9)


def test_empirical_var_cvar_rockafellar_uryasev():
    """Independently verifies discrete weighted VaR and CVaR calculation."""
    losses = [100.0, 200.0, 500.0, 1000.0]
    weights = [0.50, 0.30, 0.15, 0.05]
    alpha = 0.90

    var_calc, cvar_calc = _compute_empirical_var_cvar(losses, weights, alpha=alpha)
    # Cumulative probabilities: 100->0.50, 200->0.80, 500->0.95 (>=0.90 => VaR=500)
    # Tail excess: E[max(0, L - 500)] = 0.05 * 500 = 25 -> CVaR = 500 + 25 / 0.10 = 750.0
    assert var_calc == 500.0
    assert cvar_calc == 750.0
    assert cvar_calc >= var_calc


def test_psi_formula_exactness():
    """Independently computes PSI against DataDriftDetector.calculate_psi."""
    rng = np.random.default_rng(42)
    b = rng.normal(0.0, 1.0, size=200)
    t = rng.normal(1.2, 1.0, size=200)

    # Identical distributions -> near zero PSI
    assert DataDriftDetector.calculate_psi(b, b) < 0.01

    psi_detector = DataDriftDetector.calculate_psi(b, t, num_buckets=10, epsilon=1e-4)
    bins = np.unique(np.percentile(b, np.linspace(0, 100, 11))).copy()
    bins[0], bins[-1] = -np.inf, np.inf
    bp = (np.histogram(b, bins=bins)[0] / len(b)) + 1e-4
    tp = (np.histogram(t, bins=bins)[0] / len(t)) + 1e-4
    psi_manual = round(max(0.0, float(np.sum((tp - bp) * np.log(tp / bp)))), 4)
    assert psi_detector == psi_manual
    assert psi_detector >= 0.25  # Severe shift expected for +1.2 sigma


def test_ml_preprocessing_and_kpi_remediation_fixes(tmp_path):
    """Verifies airline/IATA city normalization, inventory indicator encoding, margin math, and validation report stages."""
    reg = ModelArtifactRegistry(config=MLEngineConfig(base_model_dir="data/models"))
    price_svc = PricePredictionService(reg)
    # Both space & underscore airline names + IATA airport codes work cleanly
    pred_iata = price_svc.predict_market_price({
        "airline": "Air_India", "source_city": "DEL", "destination_city": "BOM",
        "days_left": 10, "duration_hours": 2.2, "class": "Economy", "stops_count": 0,
    })
    pred_city = price_svc.predict_market_price({
        "airline": "Air India", "source_city": "Delhi", "destination_city": "Mumbai",
        "days_left": 10, "duration_hours": 2.2, "class": "Economy", "stops_count": 0,
    })
    assert pred_iata is not None and pred_city is not None
    assert math.isclose(pred_iata, pred_city, rel_tol=1e-9)

    # Inventory forecasting handles derived bucket + bool normalization cleanly
    inv_svc = InventoryForecastingService(ModelRegistry(), OptimizationConfig(run_id="S13_INV", optimization_timestamp="2026-06-01"))
    inv_pred = inv_svc.predict_future_available_quantity({
        "inventory_id": "HOT005", "inventory_type": "HOTEL", "supplier_id": "SUP003",
        "destination_id": "DEST001", "unit_type": "ROOM_NIGHT", "travel_date": "2026-06-24",
        "snapshot_date": "2026-06-01", "total_capacity": 100, "booked_quantity": 40,
        "available_quantity": 60, "high_occupancy_indicator": "FALSE",
    })
    assert inv_pred is not None and inv_pred >= 0.0

    # HotelCancellationService rejects partial payloads without booking fields (zero-fabrication)
    hc_svc = HotelCancellationService(ModelRegistry(), OptimizationConfig(run_id="S13_HC", optimization_timestamp="2026-06-01"))
    assert hc_svc.predict_cohort_cancellation_probability({"travel_date": "2026-07-01", "selling_price": 4500.0}) is None

    # EDA & Feature Engineering compute real margin_pct when precomputed column omitted
    supp_df = pd.DataFrame([
        {
            "offer_id": "O1", "supplier_id": "S1", "inventory_id": "I1", "origin_id": None,
            "destination_id": "DEL", "inventory_type": "HOTEL", "purchase_cost": 800.0,
            "selling_price": 1000.0, "refundable": 1, "available_quantity": 20,
            "minimum_purchase_qty": 2, "offer_valid_until": "2026-06-10", "travel_date": "2026-06-15",
        },
        {
            "offer_id": "O2", "supplier_id": "S1", "inventory_id": "I1", "origin_id": None,
            "destination_id": "DEL", "inventory_type": "HOTEL", "purchase_cost": 600.0,
            "selling_price": 1000.0, "refundable": 0, "available_quantity": 20,
            "minimum_purchase_qty": 2, "offer_valid_until": "2026-06-10", "travel_date": "2026-06-15",
        },
    ])
    kpis = compute_supplier_kpis(supp_df)
    assert math.isclose(kpis["supplier_breakdown"][0]["avg_margin_pct"], 30.0, rel_tol=1e-6)

    searches_df = pd.DataFrame([{"search_id": "SR1", "destination_id": "DEL", "inventory_type": "HOTEL", "travellers_count": 2, "search_price": 1000.0}])
    inv_df = pd.DataFrame([{"inventory_id": "I1", "destination_id": "DEL", "inventory_type": "HOTEL", "travel_date": "2026-06-15", "snapshot_date": "2026-06-01", "total_capacity": 10, "booked_quantity": 2, "available_quantity": 8}])
    pressure = build_destination_demand_supply_indicators(searches_df, inv_df, supp_df)
    assert math.isclose(float(pressure.loc[0, "avg_supplier_margin_pct"]), 30.0, rel_tol=1e-6)

    # validation_report records processed stage in duplicates, business_rules, and outliers
    raw_d = {"supplier_offers": supp_df}
    proc_d = {"supplier_offers": supp_df.drop_duplicates()}
    rep = run_and_save_validation_reports(raw_d, processed_datasets=proc_d, output_dir=tmp_path)
    assert "processed" in set(rep["duplicates"]["stage"])
    assert "processed" in set(rep["outliers"]["stage"])
