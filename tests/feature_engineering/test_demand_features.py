"""
Tests for Market Seasonality & Macro Demand Feature Engineering Module
Includes boundary tests, event bonuses, weather penalties, and configurable scoring.
"""

import pytest
import pandas as pd
import numpy as np
from feature_engineering.demand_features import (
    MarketDemandFeatureTransformer,
    CompositeDemandScoreConfig,
)


def test_market_demand_transformer():
    test_signals = pd.DataFrame({
        "signal_id": ["SIG_1", "SIG_2"],
        "destination_id": ["GOA", "DEL"],
        "travel_date": ["2026-07-15", "2026-08-10"],
        "month": [7, 8],
        "season_type": ["Monsoon", "Monsoon"],
        "holiday_indicator": [False, True],
        "festival_indicator": [False, True],
        "event_indicator": [False, False],
        "temperature": [28.5, 34.0],
        "rainfall_mm": [120.0, 15.0],
        "demand_index": [0.55, 0.85],
    })

    transformer = MarketDemandFeatureTransformer()
    feats = transformer.transform(test_signals)

    assert len(feats) == 2
    assert "demand_tier" in feats.columns
    assert "composite_seasonal_demand_score" in feats.columns
    assert "has_special_event" in feats.columns
    assert "is_heavy_rain" in feats.columns

    # SIG_1: rainfall 120 > 50 -> is_heavy_rain is True, has_special_event is False
    assert feats.loc[0, "is_heavy_rain"] == True
    assert feats.loc[0, "has_special_event"] == False
    assert feats.loc[0, "demand_tier"] == "Medium"

    # SIG_2: festival & holiday -> has_special_event is True, demand_tier High
    assert feats.loc[1, "has_special_event"] == True
    assert feats.loc[1, "demand_tier"] == "High"
    assert feats.loc[1, "composite_seasonal_demand_score"] > 60.0


def test_demand_boundary_conditions():
    # Test boundary demand_index values 0.0 and 1.0
    boundary_df = pd.DataFrame({
        "signal_id": ["SIG_MIN", "SIG_MAX"],
        "destination_id": ["JAI", "BOM"],
        "travel_date": ["2026-01-10", "2026-12-25"],
        "season_type": ["Winter", "Winter"],
        "holiday_indicator": [False, False],
        "festival_indicator": [False, False],
        "event_indicator": [False, False],
        "temperature": [20.0, 25.0],
        "rainfall_mm": [0.0, 0.0],
        "demand_index": [0.0, 1.0],
    })

    transformer = MarketDemandFeatureTransformer()
    feats = transformer.transform(boundary_df)

    assert feats.loc[0, "demand_index"] == 0.0
    assert feats.loc[0, "demand_index_scaled_100"] == 0.0
    assert feats.loc[0, "demand_tier"] == "Low"
    assert feats.loc[0, "composite_seasonal_demand_score"] == 0.0

    assert feats.loc[1, "demand_index"] == 1.0
    assert feats.loc[1, "demand_index_scaled_100"] == 100.0
    assert feats.loc[1, "demand_tier"] == "Extreme_Peak"
    # Base weight 0.70 * 100 = 70.0
    assert feats.loc[1, "composite_seasonal_demand_score"] == 70.0


def test_demand_event_and_rain_effects():
    # Test event bonus (+20) and rain penalty (-10)
    effects_df = pd.DataFrame({
        "signal_id": ["BASE", "WITH_EVENT", "WITH_RAIN", "EVENT_AND_RAIN"],
        "destination_id": ["GOA"] * 4,
        "travel_date": ["2026-05-01"] * 4,
        "season_type": ["Summer"] * 4,
        "holiday_indicator": [False, True, False, True],
        "festival_indicator": [False, False, False, False],
        "event_indicator": [False, False, False, False],
        "temperature": [30.0] * 4,
        "rainfall_mm": [10.0, 10.0, 80.0, 80.0],  # 80 mm > 50 mm heavy rain
        "demand_index": [0.50] * 4,               # 50 scaled -> base = 35.0 pts
    })

    transformer = MarketDemandFeatureTransformer()
    feats = transformer.transform(effects_df)

    # Base: 0.70 * 50 = 35.0
    assert feats.loc[0, "composite_seasonal_demand_score"] == 35.0
    # With event (+20): 35 + 20 = 55.0
    assert feats.loc[1, "composite_seasonal_demand_score"] == 55.0
    # With rain (-10): 35 - 10 = 25.0
    assert feats.loc[2, "composite_seasonal_demand_score"] == 25.0
    # Event and rain: 35 + 20 - 10 = 45.0
    assert feats.loc[3, "composite_seasonal_demand_score"] == 45.0


def test_demand_missing_values_and_clipping():
    missing_df = pd.DataFrame({
        "signal_id": ["SIG_NAN"],
        "destination_id": ["UNKNOWN"],
        "travel_date": ["2026-09-01"],
        "season_type": ["Autumn"],
        "holiday_indicator": [None],
        "festival_indicator": [None],
        "event_indicator": [None],
        "temperature": [np.nan],
        "rainfall_mm": [np.nan],
        "demand_index": [np.nan],
    })

    transformer = MarketDemandFeatureTransformer()
    feats = transformer.transform(missing_df)

    # Imputed demand_index is 0.5 -> scaled 50.0
    assert feats.loc[0, "demand_index"] == 0.5
    assert feats.loc[0, "demand_index_scaled_100"] == 50.0
    assert feats.loc[0, "temperature_celsius"] == 25.0
    assert feats.loc[0, "rainfall_mm"] == 0.0
    assert feats.loc[0, "has_special_event"] == False
    assert feats.loc[0, "is_heavy_rain"] == False
    assert 0.0 <= feats.loc[0, "composite_seasonal_demand_score"] <= 100.0


def test_configurable_score_weights():
    # Custom config with 80% base weight, 15 pts event, 5 pts rain
    custom_cfg = CompositeDemandScoreConfig(
        base_weight=0.80,
        event_bonus=15.0,
        rain_penalty=5.0,
        heavy_rain_threshold_mm=30.0,
    )
    custom_df = pd.DataFrame({
        "signal_id": ["SIG_CUSTOM"],
        "destination_id": ["DEL"],
        "travel_date": ["2026-10-01"],
        "season_type": ["Autumn"],
        "holiday_indicator": [True],
        "festival_indicator": [False],
        "event_indicator": [False],
        "temperature": [28.0],
        "rainfall_mm": [40.0],   # > 30 mm threshold -> triggers heavy rain
        "demand_index": [0.60],  # 60 scaled * 0.80 = 48.0
    })

    transformer = MarketDemandFeatureTransformer(score_config=custom_cfg)
    feats = transformer.transform(custom_df)

    # 48.0 (base) + 15.0 (event) - 5.0 (rain) = 58.0
    assert feats.loc[0, "composite_seasonal_demand_score"] == 58.0
