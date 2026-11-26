"""
ml_engine/risk_prediction/risk_prediction_service.py

Production risk prediction service for hotel cancellation and flight spoilage.
Enforces genuine feature availability: returns UNSUPPORTED for wholesale offers lacking booking cohorts.
Correctly handles model feature contracts: detects when an artifact requires legacy target-leakage
features unavailable at legitimate inference time and safely rejects prediction.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError, FeatureValidationError
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.preprocessing.preprocess_hotel import HotelFeaturePreprocessor
from ml_engine.risk_prediction.flight_risk_model import FlightRiskModel
from ml_engine.schemas import PredictionTask, PredictionRequest, PredictionResult, InferenceStatus

logger = logging.getLogger(__name__)


class RiskPredictionService:
    """Service predicting booking cancellation probability and inventory risk."""

    TASK_NAME = PredictionTask.HOTEL_CANCELLATION.value
    DECISION_THRESHOLD = 0.25
    LEAKAGE_FEATURE_NAMES = {
        "market_segment_historical_cancel_rate",
        "deposit_type_historical_cancel_rate",
    }

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
        Scores booking cancellation probability using the approved model.
        Returns None if booking context is absent or if the model requires unavailable target-leakage features.
        """
        if not self.has_passenger_booking_context(raw_record):
            logger.info("Observation lacks individual booking context. Model scoring skipped.")
            return None

        # Check whether the loaded artifact requires legacy target-leakage features
        missing_leakage_features = [
            f for f in self.LEAKAGE_FEATURE_NAMES
            if f in self.expected_features and (f not in raw_record or raw_record[f] is None)
        ]
        if missing_leakage_features:
            logger.warning(
                "Active model artifact requires legacy target-leakage features %s that are unavailable "
                "at legitimate prediction time. Scoring aborted to prevent leakage. Promotion of 45-feature model required.",
                missing_leakage_features
            )
            return None

        try:
            feat_dict = HotelFeaturePreprocessor.build_features(raw_record)
        except FeatureValidationError as fve:
            logger.info("Hotel cancellation scoring skipped due to feature validation error: %s", fve)
            return None

        # Ensure all expected features are present in the built vector
        missing_in_vector = [f for f in self.expected_features if f not in feat_dict]
        if missing_in_vector:
            logger.warning("Feature vector missing features expected by model: %s", missing_in_vector)
            return None

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
        """
        PredictionRouter adapter implementing the unified prediction interface.
        Returns UNSUPPORTED when passenger booking context is incomplete or when the active model
        requires legacy target-leakage features that cannot legitimately be supplied.
        """
        if not self.has_passenger_booking_context(request.features):
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                prediction_type="MODEL",
                model_name=self.metadata.get("model_name"),
                model_version=self.metadata.get("saved_timestamp"),
                artifact_checksum=self.metadata.get("_artifact_sha256"),
                checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
                is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
                error_message="Observation lacks required passenger booking context fields (adults, stay nights, market segment).",
                metadata={"checksum_trust_source": self.metadata.get("_checksum_trust_source")},
            )

        # Check for legacy leakage feature requirement
        missing_leakage = [
            f for f in self.LEAKAGE_FEATURE_NAMES
            if f in self.expected_features and (f not in request.features or request.features[f] is None)
        ]
        if missing_leakage:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                prediction_type="MODEL",
                model_name=self.metadata.get("model_name"),
                model_version=self.metadata.get("saved_timestamp"),
                artifact_checksum=self.metadata.get("_artifact_sha256"),
                checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
                is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
                error_message=(
                    f"Active hotel cancellation artifact requires legacy target-leakage features {missing_leakage} "
                    "that are unavailable at legitimate prediction time. Promotion of leakage-free 45-feature candidate is required."
                ),
                metadata={"checksum_trust_source": self.metadata.get("_checksum_trust_source")},
            )

        prob = self.predict_cancellation_probability(request.features)
        if prob is None:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                prediction_type="MODEL",
                model_name=self.metadata.get("model_name"),
                model_version=self.metadata.get("saved_timestamp"),
                artifact_checksum=self.metadata.get("_artifact_sha256"),
                checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
                is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
                error_message="Unable to score hotel cancellation risk with provided features.",
                metadata={"checksum_trust_source": self.metadata.get("_checksum_trust_source")},
            )

        label = "WILL_CANCEL" if prob >= self.DECISION_THRESHOLD else "RETAINED"
        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS,
            prediction=prob,
            prediction_type="MODEL",
            prediction_label=label,
            confidence_score=prob if prob >= 0.5 else (1.0 - prob),
            probabilities={"cancelled": prob, "retained": 1.0 - prob},
            model_name=self.metadata.get("model_name"),
            model_version=self.metadata.get("saved_timestamp"),
            artifact_checksum=self.metadata.get("_artifact_sha256"),
            checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
            is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
            metadata={
                "threshold": self.DECISION_THRESHOLD,
                "target_column": "is_canceled",
                "checksum_trust_source": self.metadata.get("_checksum_trust_source"),
            },
        )
