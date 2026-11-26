"""
ml_engine/risk_prediction/risk_prediction_service.py

Production risk prediction service for hotel cancellation and flight spoilage.
Enforces genuine feature availability: returns None for wholesale offers lacking booking cohorts.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.preprocessing.preprocess_hotel import HotelFeaturePreprocessor
from ml_engine.risk_prediction.flight_risk_model import FlightRiskModel
from ml_engine.schemas import PredictionTask, PredictionRequest, PredictionResult, InferenceStatus

logger = logging.getLogger(__name__)


class RiskPredictionService:
    """Service predicting booking cancellation probability and inventory risk."""

    TASK_NAME = PredictionTask.HOTEL_CANCELLATION.value
    DECISION_THRESHOLD = 0.25

    def __init__(self, registry: ModelArtifactRegistry):
        self.registry = registry
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [])
        self.flight_risk = FlightRiskModel()

    def has_passenger_booking_context(self, raw_record: Dict[str, Any]) -> bool:
        """
        Confirms genuine booking features exist.
        Wholesale offers lack passenger booking details.
        """
        return HotelFeaturePreprocessor.has_required_booking_context(raw_record)

    def predict_cancellation_probability(self, raw_record: Dict[str, Any]) -> Optional[float]:
        """
        Scores booking cancellation probability using the 47-feature model.
        Returns None if booking context is absent.
        """
        if not self.has_passenger_booking_context(raw_record):
            logger.info("Observation lacks individual booking context. Model scoring skipped.")
            return None

        feat_dict = HotelFeaturePreprocessor.build_features(raw_record)
        row_df = pd.DataFrame([feat_dict])[self.expected_features]

        try:
            X_trans = self.preprocessor.transform(row_df) if self.preprocessor is not None else row_df
            if hasattr(self.estimator, "predict_proba"):
                raw_prob = self.estimator.predict_proba(X_trans)
                p_cancel = float(raw_prob[0, 1]) if raw_prob.shape[1] > 1 else float(raw_prob[0, 0])
            else:
                raw_pred = self.estimator.predict(X_trans)
                p_cancel = float(raw_pred[0])

            p_cancel = float(np.clip(p_cancel, 0.0, 1.0))
            return p_cancel
        except Exception as exc:
            logger.error("Hotel cancellation inference failed: %s", exc)
            raise ModelInferenceError(f"Hotel cancellation scoring failed: {exc}") from exc

    def handle_prediction_request(self, request: PredictionRequest) -> PredictionResult:
        """PredictionRouter adapter implementing the unified prediction interface."""
        if not self.has_passenger_booking_context(request.features):
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                model_name=self.metadata.get("model_name"),
                error_message="Observation lacks required passenger booking context fields.",
            )

        prob = self.predict_cancellation_probability(request.features)
        if prob is None:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                model_name=self.metadata.get("model_name"),
            )

        label = "WILL_CANCEL" if prob >= self.DECISION_THRESHOLD else "RETAINED"
        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS,
            prediction=prob,
            prediction_label=label,
            confidence_score=prob if prob >= 0.5 else (1.0 - prob),
            probabilities={"cancelled": prob, "retained": 1.0 - prob},
            model_name=self.metadata.get("model_name"),
            metadata={"threshold": self.DECISION_THRESHOLD, "target_column": "is_canceled"},
        )
