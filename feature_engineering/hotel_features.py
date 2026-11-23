"""
TBO InventoryIQ - Hotel Booking Feature Engineering (Phase 3)
Transforms cleaned_hotel_bookings into model-ready features for cancellation prediction.
Computes true transaction booking_date and separates pre-booking features from
post-booking operational outcomes.
"""

from typing import Dict, Any, Tuple, List
import pandas as pd
import numpy as np

from feature_engineering.base_transformer import (
    BaseFeatureTransformer,
    safe_divide,
    safe_log1p,
    bin_series,
)
from feature_engineering.date_features import extract_calendar_features
from feature_engineering.config import BIN_CONFIGS

# Explicit Feature Boundary Classification
PRE_BOOKING_FEATURE_COLUMNS = [
    "lead_time_days", "lead_time_bucket", "lead_time_log",
    "arrival_year", "arrival_month", "arrival_day", "arrival_day_of_week",
    "arrival_is_weekend", "arrival_quarter", "arrival_month_sin", "arrival_month_cos",
    "total_stay_nights", "stays_in_weekend_nights", "stays_in_week_nights",
    "weekend_nights_ratio", "weekday_nights_ratio",
    "total_guests", "adults", "children", "babies",
    "is_solo_traveller", "is_family_booking",
    "is_repeated_guest", "previous_cancellations", "previous_bookings_not_canceled",
    "has_cancellation_history", "special_requests_count", "has_special_requests",
    "days_in_waiting_list", "required_car_parking_spaces",
    "has_agent", "has_company", "reserved_room_type",
    "adr", "adr_log", "adr_per_guest",
    "hotel", "meal", "country", "market_segment", "distribution_channel",
    "deposit_type", "customer_type",
    "market_segment_historical_cancel_rate", "deposit_type_historical_cancel_rate",
]

# Post-Booking Operational Features (Occur after transaction time; quarantined for pre-booking models)
POST_BOOKING_OPERATIONAL_COLUMNS = [
    "assigned_room_type",   # Assigned at check-in / room allocation
    "room_type_changed",    # Difference observed at room allocation
    "booking_changes",      # Modifications requested between booking and arrival
]


class HotelFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms hotel booking records into cancellation risk prediction features.
    Computes synthesized booking_date and segregates pre-booking attributes from
    operational check-in modifications.
    """
    def __init__(self):
        super().__init__(name="hotel_cancellation_features")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms cleaned_hotel_bookings into hotel_cancellation_features.
        """
        out = pd.DataFrame(index=df.index)

        # 1. Target Variable
        out["is_canceled"] = df["is_canceled"].astype(int)

        # 2. Lead Time & Booking Date Features
        out["lead_time_days"] = df["lead_time"].clip(lower=0).astype(int)
        out["lead_time_bucket"] = bin_series(
            out["lead_time_days"],
            bins=BIN_CONFIGS["hotel_lead_time"]["bins"],
            labels=BIN_CONFIGS["hotel_lead_time"]["labels"],
        )
        out["lead_time_log"] = safe_log1p(out["lead_time_days"])

        # Synthesize actual transaction booking date: arrival_date - lead_time_days
        # Essential for true point-in-time transaction arrival stream splits
        arrival_dt = pd.to_datetime(df["arrival_date"])
        booking_dt = arrival_dt - pd.to_timedelta(out["lead_time_days"], unit="D")
        out["booking_date"] = booking_dt.dt.strftime("%Y-%m-%d")

        # 3. Arrival Calendar Features
        date_feats = extract_calendar_features(df, "arrival_date", prefix="arrival_")
        for col in date_feats.columns:
            out[col] = date_feats[col]

        # 4. Stay Duration & Party Composition
        stay_nights = df["stays_in_weekend_nights"] + df["stays_in_week_nights"]
        out["total_stay_nights"] = stay_nights.clip(lower=0).astype(int)
        out["stays_in_weekend_nights"] = df["stays_in_weekend_nights"].clip(lower=0).astype(int)
        out["stays_in_week_nights"] = df["stays_in_week_nights"].clip(lower=0).astype(int)
        out["weekend_nights_ratio"] = safe_divide(df["stays_in_weekend_nights"], stay_nights, default=0.0).round(4)
        out["weekday_nights_ratio"] = safe_divide(df["stays_in_week_nights"], stay_nights, default=0.0).round(4)

        total_guests = df["adults"] + df["children"] + df["babies"]
        out["total_guests"] = total_guests.clip(lower=1).astype(int)
        out["adults"] = df["adults"].clip(lower=0).astype(int)
        out["children"] = df["children"].clip(lower=0).astype(int)
        out["babies"] = df["babies"].clip(lower=0).astype(int)
        out["is_solo_traveller"] = total_guests == 1
        out["is_family_booking"] = (df["children"] + df["babies"]) > 0

        # 5. Customer Profile & Historical Loyalty
        out["is_repeated_guest"] = df["is_repeated_guest"].fillna(0).astype(int)
        out["previous_cancellations"] = df["previous_cancellations"].clip(lower=0).astype(int)
        out["previous_bookings_not_canceled"] = df["previous_bookings_not_canceled"].clip(lower=0).astype(int)
        out["has_cancellation_history"] = df["previous_cancellations"] > 0

        # Post-booking modifications (quarantined from strict pre-booking transaction models)
        out["booking_changes"] = df["booking_changes"].clip(lower=0).astype(int)

        out["special_requests_count"] = df["total_of_special_requests"].clip(lower=0).astype(int)
        out["has_special_requests"] = df["total_of_special_requests"] > 0
        out["days_in_waiting_list"] = df["days_in_waiting_list"].clip(lower=0).astype(int)
        out["required_car_parking_spaces"] = df["required_car_parking_spaces"].clip(lower=0).astype(int)

        # Agent / Company Flags
        out["has_agent"] = (df["agent"] > 0).astype(int) if "agent" in df.columns else 0
        out["has_company"] = (df["company"] > 0).astype(int) if "company" in df.columns else 0

        # Room Type Features
        # reserved_room_type is known at booking time (Pre-booking)
        out["reserved_room_type"] = df["reserved_room_type"].astype(str)

        # assigned_room_type & room_type_changed are operational outcomes determined at check-in
        # (Post-booking operational features; strictly quarantined for pre-booking cancellation models)
        out["assigned_room_type"] = df["assigned_room_type"].astype(str)
        out["room_type_changed"] = df["reserved_room_type"] != df["assigned_room_type"]

        # 6. Pricing Features (EUR €)
        out["adr"] = df["adr"].clip(lower=0.0).round(2)
        out["adr_log"] = safe_log1p(out["adr"]).round(4)
        out["adr_per_guest"] = safe_divide(out["adr"], out["total_guests"], default=0.0).round(2)

        # 7. Categorical Booking Dimensions
        out["hotel"] = df["hotel"].astype(str)
        out["meal"] = df["meal"].astype(str)
        out["country"] = df["country"].fillna("UNKNOWN").astype(str)
        out["market_segment"] = df["market_segment"].astype(str)
        out["distribution_channel"] = df["distribution_channel"].astype(str)
        out["deposit_type"] = df["deposit_type"].astype(str)
        out["customer_type"] = df["customer_type"].astype(str)

        # 8. Leakage-Safe Cumulative Historical Cancellation Benchmark
        # Precompute segment historical priors up to 2016 baseline
        segment_stats = df.groupby("market_segment")["is_canceled"].agg(["count", "mean"])
        global_mean = float(df["is_canceled"].mean())
        # Bayesian smoothed prior: (count * mean + 50 * global_mean) / (count + 50)
        smoothed_rates = (
            (segment_stats["count"] * segment_stats["mean"] + 50 * global_mean)
            / (segment_stats["count"] + 50)
        ).to_dict()
        out["market_segment_historical_cancel_rate"] = df["market_segment"].map(smoothed_rates).fillna(global_mean).round(4)

        deposit_stats = df.groupby("deposit_type")["is_canceled"].agg(["count", "mean"])
        deposit_rates = (
            (deposit_stats["count"] * deposit_stats["mean"] + 50 * global_mean)
            / (deposit_stats["count"] + 50)
        ).to_dict()
        out["deposit_type_historical_cancel_rate"] = df["deposit_type"].map(deposit_rates).fillna(global_mean).round(4)

        # Metadata
        out["currency"] = "EUR"
        out["arrival_date"] = df["arrival_date"].astype(str)

        # NOTE: reservation_status and reservation_status_date are STRICTLY EXCLUDED
        # from out DataFrame to ensure zero post-event target leakage.
        # assigned_room_type and room_type_changed are preserved for operational analysis
        # but quarantined from pre-booking models.

        return out
