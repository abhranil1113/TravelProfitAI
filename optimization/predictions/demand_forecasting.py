"""
optimization/predictions/demand_forecasting.py

Demand forecasting inference service using Phase 4 Naive baseline champion model.
Predicts future 7-day search volume panel observations.
"""

from typing import Dict, Any, List
import pandas as pd
from optimization.predictions.model_registry import ModelRegistry
from optimization.config import OptimizationConfig


class DemandForecastingService:
    """Predicts future search volumes for destination and inventory type."""

    TASK_NAME = "demand_forecasting"

    def __init__(self, registry: ModelRegistry, config: OptimizationConfig, customer_searches_df: pd.DataFrame):
        self.registry = registry
        self.config = config
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.searches_df = customer_searches_df
        self._panel_cache: Dict[tuple, float] = self._build_historical_search_volume_panel()

    def _build_historical_search_volume_panel(self) -> Dict[tuple, float]:
        """Builds recent historical average search volume per (destination_id, inventory_type)."""
        cache = {}
        if self.searches_df.empty:
            return cache

        opt_ts = pd.to_datetime(self.config.optimization_timestamp)
        df = self.searches_df.copy()
        df["search_dt"] = pd.to_datetime(df["search_date"])
        prior_df = df[df["search_dt"] < opt_ts]

        if prior_df.empty:
            return cache

        # Compute average 7-day search volume over the last 30 days prior to T_opt
        recent_cutoff = opt_ts - pd.Timedelta(days=30)
        recent_df = prior_df[prior_df["search_dt"] >= recent_cutoff]
        if recent_df.empty:
            recent_df = prior_df

        grouped = recent_df.groupby(["destination_id", "inventory_type"]).size()
        for (dest, itype), count in grouped.items():
            # Normalized to weekly rate
            weekly_rate = float(count) * (7.0 / max(1.0, (opt_ts - recent_cutoff).days))
            cache[(dest, itype)] = max(1.0, weekly_rate)

        return cache

    def predict_future_search_volume(self, destination_id: str, inventory_type: str) -> float:
        """
        Returns predicted 7-day search volume.
        """
        key = (destination_id, inventory_type)
        if key in self._panel_cache:
            return self._panel_cache[key]
        return 10.0  # Safe default baseline
