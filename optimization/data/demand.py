"""
optimization/data/demand.py

Demand preparation and funnel conversion service.
Converts search forecasts to justified room-night and seat demand bounds
using historical observations strictly prior to T_opt.
"""

from typing import Dict, Tuple, Any, Optional
import pandas as pd
import numpy as np


class DemandService:
    """Prepares aggregate destination demand bounds with zero-denominator protection."""

    def __init__(self,
                 searches_prior_df: pd.DataFrame,
                 assumed_stay_duration: float = 2.0,
                 demand_scenario_multiplier: float = 1.0):
        self.searches_prior_df = searches_prior_df
        self.assumed_stay_duration = assumed_stay_duration
        self.demand_scenario_multiplier = demand_scenario_multiplier
        self.funnel_metrics = self._calculate_historical_funnel_metrics()

    def _calculate_historical_funnel_metrics(self) -> Dict[Tuple[str, str], Dict[str, float]]:
        """
        Calculates conversion rates and party sizes strictly from prior searches.
        Key: (destination_id, inventory_type) -> {conversion_rate, avg_party_size, avg_rooms}
        """
        metrics = {}
        if self.searches_prior_df.empty:
            return metrics

        grouped = self.searches_prior_df.groupby(["destination_id", "inventory_type"])
        for (dest, itype), group in grouped:
            total_searches = len(group)
            completed_bookings = int(group["booking_completed"].sum())
            conversion_rate = completed_bookings / max(1, total_searches)

            rooms_series = group["rooms_count"].dropna() if "rooms_count" in group.columns else pd.Series(dtype=float)
            travellers_series = group["travellers_count"].dropna() if "travellers_count" in group.columns else pd.Series(dtype=float)

            avg_travellers = float(travellers_series.mean()) if not travellers_series.empty else 2.0
            avg_rooms = float(rooms_series.mean()) if not rooms_series.empty else 1.0

            metrics[(dest, itype)] = {
                "conversion_rate": conversion_rate,
                "avg_travellers": max(1.0, avg_travellers),
                "avg_rooms": max(1.0, avg_rooms),
                "total_historical_searches": total_searches,
                "historical_bookings": completed_bookings,
            }
        return metrics

    def get_aggregate_demand_bound(self,
                                   destination_id: str,
                                   inventory_type: str,
                                   predicted_search_volume: float) -> int:
        """
        Calculates the aggregate destination procurement demand ceiling.
        Units:
            HOTEL: room-nights
            FLIGHT: seats
        """
        if predicted_search_volume <= 0:
            return 0

        key = (destination_id, inventory_type)
        funnel = self.funnel_metrics.get(key)
        
        if not funnel:
            # Fallback if this destination had 0 prior searches
            conversion_rate = 0.15
            avg_travellers = 2.0
            avg_rooms = 1.0
        else:
            conversion_rate = funnel["conversion_rate"]
            avg_travellers = funnel["avg_travellers"]
            avg_rooms = funnel["avg_rooms"]

        if conversion_rate <= 0:
            return 0

        if inventory_type.upper() == "HOTEL":
            raw_demand = (predicted_search_volume *
                          conversion_rate *
                          avg_rooms *
                          self.assumed_stay_duration *
                          self.demand_scenario_multiplier)
        else:  # FLIGHT
            raw_demand = (predicted_search_volume *
                          conversion_rate *
                          avg_travellers *
                          self.demand_scenario_multiplier)

        # Truncate to conservative integer bound (no artificial MOQ floor)
        return int(np.floor(raw_demand))
