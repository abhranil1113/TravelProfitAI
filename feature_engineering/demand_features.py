"""
TBO InventoryIQ - Market Seasonality & Macro Demand Feature Engineering (Phase 3)
Builds destination-level seasonality indices, event uplift features,
and weather indicators from market_seasonal_signals.
Corrects composite demand scoring with configurable weights and explicit normalization.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from feature_engineering.base_transformer import (
    BaseFeatureTransformer,
    bin_series,
)
from feature_engineering.date_features import extract_calendar_features
from feature_engineering.config import BIN_CONFIGS


@dataclass
class CompositeDemandScoreConfig:
    """
    Configurable weights, penalties, and thresholds for the prototype composite seasonal score.
    Documented as prototype heuristic assumptions subject to empirical tuning in Phase 4.
    """
    base_weight: float = 0.70              # Weight applied to normalized demand index (contributes up to 70 pts)
    event_bonus: float = 20.0              # Uplift added when holiday, festival, or event is active (20 pts)
    rain_penalty: float = 10.0             # Dampening penalty for heavy precipitation (10 pts)
    heavy_rain_threshold_mm: float = 50.0  # Rainfall threshold (mm) triggering weather dampening
    demand_scale_factor: float = 100.0     # Multiplier to normalize [0.0, 1.0] demand_index to 100-pt scale


class MarketDemandFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms seasonal and environmental signals into destination demand features.
    """
    def __init__(self, score_config: Optional[CompositeDemandScoreConfig] = None):
        super().__init__(name="market_demand_features")
        self.score_config = score_config or CompositeDemandScoreConfig()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # 1. Identifiers & Entity Attributes
        out["signal_id"] = df["signal_id"].astype(str)
        out["destination_id"] = df["destination_id"].astype(str)
        out["travel_date"] = df["travel_date"].astype(str)
        out["season_type"] = df["season_type"].astype(str)

        # 2. Calendar Features
        date_feats = extract_calendar_features(df, "travel_date", prefix="travel_")
        for col in date_feats.columns:
            out[col] = date_feats[col]

        # 3. Macro Events & Festival Uplifts
        holidays = df["holiday_indicator"].fillna(False).astype(bool)
        festivals = df["festival_indicator"].fillna(False).astype(bool)
        events = df["event_indicator"].fillna(False).astype(bool)

        out["holiday_indicator"] = holidays
        out["festival_indicator"] = festivals
        out["event_indicator"] = events
        out["has_special_event"] = holidays | festivals | events

        # 4. Weather & Environmental Features
        temp = pd.to_numeric(df["temperature"], errors="coerce").fillna(25.0).round(1)
        rain = pd.to_numeric(df["rainfall_mm"], errors="coerce").fillna(0.0).clip(lower=0.0).round(1)
        out["temperature_celsius"] = temp
        out["rainfall_mm"] = rain
        out["is_heavy_rain"] = rain > self.score_config.heavy_rain_threshold_mm

        # 5. Demand Index Normalization & Tiering
        # The source demand_index in market_seasonal_signals is bounded in [0.0, 1.0]
        # (observed min=0.06, max=0.99). We explicitly preserve the original [0, 1] index
        # and construct a 100-pt normalized scale (handling both [0, 1] and [0, 100] inputs).
        demand_num = pd.to_numeric(df["demand_index"], errors="coerce").fillna(0.5)
        if (demand_num > 1.0).any():
            # Input passed on 0-100 scale; normalize down to [0, 1]
            demand_scaled = demand_num.clip(lower=0.0, upper=100.0)
            demand_raw = demand_scaled / self.score_config.demand_scale_factor
        else:
            demand_raw = demand_num.clip(lower=0.0, upper=1.0)
            demand_scaled = demand_raw * self.score_config.demand_scale_factor

        out["demand_index"] = demand_raw.round(4)
        out["demand_index_scaled_100"] = demand_scaled.round(2)

        out["demand_tier"] = bin_series(
            out["demand_index_scaled_100"],
            bins=BIN_CONFIGS["market_demand_index"]["bins"],
            labels=BIN_CONFIGS["market_demand_index"]["labels"],
        )

        # 6. Corrected & Configurable Composite Seasonal Score (0 to 100 Scale)
        # Formula: clip(base_weight * demand_scaled + event_bonus * has_event - rain_penalty * is_heavy_rain, 0, 100)
        cfg = self.score_config
        composite_score = (
            cfg.base_weight * out["demand_index_scaled_100"]
            + cfg.event_bonus * out["has_special_event"].astype(int)
            - cfg.rain_penalty * out["is_heavy_rain"].astype(int)
        ).clip(lower=0.0, upper=100.0).round(2)

        out["composite_seasonal_demand_score"] = composite_score
        out["unit"] = "INDEX"

        return out
