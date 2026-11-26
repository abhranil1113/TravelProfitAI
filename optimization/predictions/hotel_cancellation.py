"""
optimization/predictions/hotel_cancellation.py

Hotel cancellation inference service.
Evaluates guest cancellation risk only when genuine booking features are present.
Strictly prohibits fabricated guest cohorts, synthetic country assignments, and quarantined leakage features.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from optimization.predictions.model_registry import ModelRegistry
from optimization.config import OptimizationConfig
from optimization.exceptions import ModelInferenceError

logger = logging.getLogger(__name__)


class HotelCancellationService:
    """Infers cancellation probabilities using approved model when genuine features exist."""

    TASK_NAME = "hotel_cancellation"

    # Core booking features that must be genuinely available to score passenger cancellation
    REQUIRED_BOOKING_FIELDS = [
        "adults", "stays_in_weekend_nights", "stays_in_week_nights",
        "market_segment", "customer_type", "deposit_type"
    ]

    def __init__(self, registry: ModelRegistry, config: OptimizationConfig):
        self.registry = registry
        self.config = config
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [])

    def has_predictable_features(self, offer_record: Dict[str, Any]) -> bool:
        """
        Checks whether the offer/booking record contains genuine reservation-level attributes.
        Wholesale inventory offers typically lack passenger booking details.
        """
        return all(field in offer_record and offer_record[field] is not None for field in self.REQUIRED_BOOKING_FIELDS)

    def predict_cohort_cancellation_probability(self, offer_record: Dict[str, Any]) -> Optional[float]:
        """
        Predicts cancellation probability ONLY when valid, genuine booking features are available.
        If required passenger cohort data is absent (e.g. bulk wholesale supplier offer),
        returns None rather than fabricating synthetic customer attributes.
        """
        if not self.has_predictable_features(offer_record):
            # Explicitly return None: wholesale contract offers do not possess individual guest reservations
            return None

        # Build feature vector from authentic offer/booking fields only
        try:
            row_dict = {}
            for feat in self.expected_features:
                if feat in offer_record:
                    row_dict[feat] = offer_record[feat]
                else:
                    # Missing model feature - cannot reliably score
                    logger.warning("Missing required feature '%s' in booking record. Prediction unsupported.", feat)
                    return None

            row_df = pd.DataFrame([row_dict])[self.expected_features]
            X_trans = self.preprocessor.transform(row_df) if self.preprocessor is not None else row_df
            prob_raw = float(self.estimator.predict_proba(X_trans)[0, 1])

            # Apply Bayesian shrinkage against prior if configured
            lam = getattr(self.config.risk, "bayesian_shrinkage_lambda", 0.70)
            prior = getattr(self.config.risk, "hotel_default_cancellation_prior", 0.20)
            calibrated_prob = float(lam * prob_raw + (1.0 - lam) * prior)
            min_p = getattr(self.config.risk, "min_cancellation_prob", 0.01)
            max_p = getattr(self.config.risk, "max_cancellation_prob", 0.99)
            return float(np.clip(calibrated_prob, min_p, max_p))
        except Exception as exc:
            logger.error("Hotel cancellation scoring failed: %s", exc)
            raise ModelInferenceError(f"Hotel cancellation scoring failed: {exc}") from exc

