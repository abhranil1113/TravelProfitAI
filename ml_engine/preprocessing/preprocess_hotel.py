"""
ml_engine/preprocessing/preprocess_hotel.py

Domain feature preprocessing for hotel cancellation risk prediction.
Derives ratios, seasonal indicators, and log ADR required by the 47-feature model.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd


class HotelFeaturePreprocessor:
    """Constructs the canonical 47 features required by the hotel cancellation LightGBM model."""

    # Fields that must be genuinely provided by a booking record
    REQUIRED_BOOKING_FIELDS = [
        "adults", "stays_in_weekend_nights", "stays_in_week_nights",
        "market_segment", "customer_type", "deposit_type"
    ]

    @staticmethod
    def has_required_booking_context(raw_record: Dict[str, Any]) -> bool:
        """Checks if the observation possesses passenger booking fields."""
        return all(f in raw_record and raw_record[f] is not None for f in HotelFeaturePreprocessor.REQUIRED_BOOKING_FIELDS)

    @staticmethod
    def build_features(raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds the complete 47-feature dictionary for hotel cancellation risk.
        """
        lead_time = float(raw_record.get("lead_time_days", raw_record.get("lead_time", 30)))
        w_nights = float(raw_record.get("stays_in_weekend_nights", 0))
        d_nights = float(raw_record.get("stays_in_week_nights", 2))
        total_stay = max(1.0, w_nights + d_nights)

        adults = float(raw_record.get("adults", 2))
        children = float(raw_record.get("children", 0))
        babies = float(raw_record.get("babies", 0))
        total_guests = max(1.0, adults + children + babies)

        adr = float(raw_record.get("adr", raw_record.get("price", 100.0)))

        arrival_date_str = str(raw_record.get("arrival_date", raw_record.get("travel_date", "2026-06-15")))
        try:
            arr_dt = pd.to_datetime(arrival_date_str)
        except Exception:
            arr_dt = pd.to_datetime("2026-06-15")

        # Bucket lead time
        if lead_time <= 7:
            lt_bucket = "0-7 days"
        elif lead_time <= 30:
            lt_bucket = "8-30 days"
        elif lead_time <= 90:
            lt_bucket = "31-90 days"
        elif lead_time <= 180:
            lt_bucket = "91-180 days"
        else:
            lt_bucket = "181+ days"

        mkt_seg = str(raw_record.get("market_segment", "Online TA"))
        dep_type = str(raw_record.get("deposit_type", "No Deposit"))

        return {
            "lead_time_days": lead_time,
            "lead_time_bucket": lt_bucket,
            "lead_time_log": float(np.log1p(max(0.0, lead_time))),
            "arrival_year": int(arr_dt.year),
            "arrival_month": int(arr_dt.month),
            "arrival_day": int(arr_dt.day),
            "arrival_day_of_week": int(arr_dt.dayofweek),
            "arrival_week_of_year": int(arr_dt.isocalendar().week),
            "arrival_quarter": int(arr_dt.quarter),
            "arrival_is_weekend": int(arr_dt.dayofweek >= 5),
            "arrival_is_peak_season": int(arr_dt.month in (6, 7, 8, 12)),
            "arrival_is_month_start": int(arr_dt.day <= 5),
            "arrival_is_month_end": int(arr_dt.day >= 25),
            "total_stay_nights": total_stay,
            "stays_in_weekend_nights": w_nights,
            "stays_in_week_nights": d_nights,
            "weekend_nights_ratio": float(w_nights / total_stay),
            "weekday_nights_ratio": float(d_nights / total_stay),
            "total_guests": total_guests,
            "adults": adults,
            "children": children,
            "babies": babies,
            "is_solo_traveller": int(total_guests == 1),
            "is_family_booking": int(children > 0 or babies > 0 or adults >= 3),
            "is_repeated_guest": int(raw_record.get("is_repeated_guest", 0)),
            "previous_cancellations": float(raw_record.get("previous_cancellations", 0)),
            "previous_bookings_not_canceled": float(raw_record.get("previous_bookings_not_canceled", 0)),
            "has_cancellation_history": int(float(raw_record.get("previous_cancellations", 0)) > 0),
            "special_requests_count": float(raw_record.get("total_of_special_requests", 0)),
            "has_special_requests": int(float(raw_record.get("total_of_special_requests", 0)) > 0),
            "days_in_waiting_list": float(raw_record.get("days_in_waiting_list", 0)),
            "required_car_parking_spaces": float(raw_record.get("required_car_parking_spaces", 0)),
            "has_agent": int(raw_record.get("agent") is not None and str(raw_record.get("agent")) != "NULL"),
            "has_company": int(raw_record.get("company") is not None and str(raw_record.get("company")) != "NULL"),
            "reserved_room_type": str(raw_record.get("reserved_room_type", "A")),
            "adr": adr,
            "adr_log": float(np.log1p(max(0.0, adr))),
            "adr_per_guest": float(adr / total_guests),
            "hotel": str(raw_record.get("hotel", "City Hotel")),
            "meal": str(raw_record.get("meal", "BB")),
            "country": str(raw_record.get("country", "PRT")),
            "market_segment": mkt_seg,
            "distribution_channel": str(raw_record.get("distribution_channel", "TA/TO")),
            "deposit_type": dep_type,
            "customer_type": str(raw_record.get("customer_type", "Transient")),
            "market_segment_historical_cancel_rate": 0.35,
            "deposit_type_historical_cancel_rate": 0.28,
        }
