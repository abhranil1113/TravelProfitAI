"""
TBO InventoryIQ - Customer Search Demand Feature Engineering (Phase 3)
Builds features from search events capturing intent, budget points, lead time,
party sizing, and conversion funnel outcomes.
"""

import pandas as pd
import numpy as np

from feature_engineering.base_transformer import (
    BaseFeatureTransformer,
    safe_divide,
    safe_log1p,
    safe_date_diff_days,
    bin_series,
)
from feature_engineering.date_features import extract_calendar_features
from feature_engineering.config import BIN_CONFIGS


class CustomerSearchFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms customer search events into demand and conversion features.
    """
    def __init__(self):
        super().__init__(name="customer_demand_features")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # 1. Identifiers & Entity Attributes
        out["search_id"] = df["search_id"].astype(str)
        out["user_id"] = df["user_id"].astype(str)
        out["destination_id"] = df["destination_id"].astype(str)
        out["origin_id"] = df["origin_id"].astype(str)
        out["inventory_type"] = df["inventory_type"].astype(str)

        # 2. Search & Travel Calendar Features
        search_dates = extract_calendar_features(df, "search_date", prefix="search_")
        for col in search_dates.columns:
            out[col] = search_dates[col]

        travel_dates = extract_calendar_features(df, "travel_date", prefix="travel_")
        for col in travel_dates.columns:
            out[col] = travel_dates[col]

        # 3. Search-to-Travel Lead Time
        if "search_lead_days" in df.columns:
            lead_days = df["search_lead_days"].clip(lower=0)
        else:
            lead_days = safe_date_diff_days(df["travel_date"], df["search_date"]).clip(lower=0).fillna(0)

        out["search_lead_days"] = lead_days.astype(int)
        out["search_lead_bucket"] = bin_series(
            out["search_lead_days"],
            bins=BIN_CONFIGS["search_lead_time"]["bins"],
            labels=BIN_CONFIGS["search_lead_time"]["labels"],
        )
        out["search_lead_log"] = safe_log1p(out["search_lead_days"]).round(4)

        # 4. Search Party & Accommodation Scope
        travellers = df["travellers_count"].clip(lower=1).astype(int)
        rooms = df["rooms_count"].fillna(1).clip(lower=1).astype(int)
        out["travellers_count"] = travellers
        out["rooms_count"] = rooms
        out["travellers_per_room"] = safe_divide(travellers, rooms, default=1.0).round(2)
        out["is_group_search"] = travellers >= 4

        # 5. Price & Budget Points (INR ₹)
        prices = df["search_price"].clip(lower=0.0).round(2)
        out["search_price_inr"] = prices
        out["search_price_log"] = safe_log1p(prices).round(4)
        out["search_price_per_traveller_inr"] = safe_divide(prices, travellers, default=0.0).round(2)
        out["currency"] = "INR"

        # 6. Funnel Outcomes (Analytical conversion metrics - Quarantined for demand prediction)
        out["clicked"] = df["clicked"].astype(bool)
        out["booking_completed"] = df["booking_completed"].astype(bool)
        out["has_funnel_anomaly"] = (out["booking_completed"] == True) & (out["clicked"] == False)

        return out
