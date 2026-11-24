"""
optimization/predictions/hotel_cancellation.py

Hotel cancellation inference service.
Implements the Representative Booking Cohort builder and prototype EUR ADR scaling.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from optimization.predictions.model_registry import ModelRegistry
from optimization.config import OptimizationConfig
from optimization.exceptions import ModelInferenceError


class HotelCancellationService:
    """Infers experimental cancellation probabilities using Phase 4 LightGBM model."""

    TASK_NAME = "hotel_cancellation"

    def __init__(self, registry: ModelRegistry, config: OptimizationConfig):
        self.registry = registry
        self.config = config
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [])

    def predict_cohort_cancellation_probability(self, offer_record: Dict[str, Any]) -> float:
        """
        Builds a representative booking cohort vector from offer fields and scores it.
        Applies Bayesian shrinkage against destination prior.
        """
        travel_date_ts = pd.to_datetime(offer_record["travel_date"])
        opt_ts = pd.to_datetime(self.config.optimization_timestamp)
        lead_time_days = max(0, (travel_date_ts - opt_ts).days)

        # Prototype EUR ADR scaling
        raw_price = float(offer_record["selling_price"])
        stay_duration = self.config.financial.hotel_assumed_stay_duration
        fx_rate = self.config.financial.prototype_eur_to_inr_rate
        scaled_adr_eur = (raw_price / stay_duration) / fx_rate

        if lead_time_days <= 7:
            bucket = "0-7d"
        elif lead_time_days <= 30:
            bucket = "8-30d"
        elif lead_time_days <= 90:
            bucket = "31-90d"
        elif lead_time_days <= 180:
            bucket = "91-180d"
        elif lead_time_days <= 365:
            bucket = "181-365d"
        else:
            bucket = "365d+"

        # Representative booking cohort row (matching exact 47 features)
        cohort_dict = {
            "lead_time_days": int(lead_time_days),
            "lead_time_bucket": bucket,
            "lead_time_log": float(np.log1p(lead_time_days)),
            "arrival_year": int(travel_date_ts.year),
            "arrival_month": int(travel_date_ts.month),
            "arrival_day": int(travel_date_ts.day),
            "arrival_day_of_week": int(travel_date_ts.dayofweek),
            "arrival_week_of_year": int(travel_date_ts.isocalendar().week),
            "arrival_quarter": int(travel_date_ts.quarter),
            "arrival_is_weekend": bool(travel_date_ts.dayofweek >= 5),
            "arrival_is_peak_season": bool(travel_date_ts.month in [6, 7, 8, 12]),
            "arrival_is_month_start": bool(travel_date_ts.day <= 5),
            "arrival_is_month_end": bool(travel_date_ts.is_month_end),
            "total_stay_nights": int(stay_duration),
            "stays_in_weekend_nights": 1 if travel_date_ts.dayofweek >= 5 else 0,
            "stays_in_week_nights": max(0, int(stay_duration) - (1 if travel_date_ts.dayofweek >= 5 else 0)),
            "weekend_nights_ratio": 0.5,
            "weekday_nights_ratio": 0.5,
            "total_guests": 2,
            "adults": 2,
            "children": 0,
            "babies": 0,
            "is_solo_traveller": False,
            "is_family_booking": False,
            "is_repeated_guest": 0,
            "previous_cancellations": 0,
            "previous_bookings_not_canceled": 0,
            "has_cancellation_history": False,
            "special_requests_count": 0,
            "has_special_requests": False,
            "days_in_waiting_list": 0,
            "required_car_parking_spaces": 0,
            "has_agent": True,
            "has_company": False,
            "reserved_room_type": "A",
            "adr": scaled_adr_eur,
            "adr_log": float(np.log1p(max(0.0, scaled_adr_eur))),
            "adr_per_guest": scaled_adr_eur / 2.0,
            "hotel": "City Hotel",
            "meal": "BB",
            "country": "PRT",
            "market_segment": "Online TA",
            "distribution_channel": "TA/TO",
            "deposit_type": "No Deposit",
            "customer_type": "Transient",
            "market_segment_historical_cancel_rate": 0.35,
            "deposit_type_historical_cancel_rate": 0.28,
        }

        # Build single-row DataFrame aligned to expected features
        row_df = pd.DataFrame([cohort_dict])[self.expected_features]

        try:
            X_trans = self.preprocessor.transform(row_df)
            prob_raw = float(self.estimator.predict_proba(X_trans)[0, 1])
        except Exception as e:
            raise ModelInferenceError(f"Hotel cancellation model inference failed: {str(e)}")

        # Apply Bayesian shrinkage against prior
        lam = self.config.risk.bayesian_shrinkage_lambda
        prior = self.config.risk.hotel_default_cancellation_prior
        calibrated_prob = float(lam * prob_raw + (1.0 - lam) * prior)
        min_p = getattr(self.config.risk, "min_cancellation_prob", 0.01)
        max_p = getattr(self.config.risk, "max_cancellation_prob", 0.99)
        return float(np.clip(calibrated_prob, min_p, max_p))
