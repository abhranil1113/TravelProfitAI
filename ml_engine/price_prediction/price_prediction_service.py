"""
ml_engine/price_prediction/price_prediction_service.py

Production flight market ceiling price prediction service.
Predicts market reference price and validates supported routes, airlines, and cabins.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.preprocessing.preprocess_flight import FlightFeaturePreprocessor
from ml_engine.schemas import PredictionTask, PredictionRequest, PredictionResult, InferenceStatus

logger = logging.getLogger(__name__)


class PricePredictionService:
    """Service predicting market ceiling price for flight wholesale offers."""

    TASK_NAME = PredictionTask.FLIGHT_PRICE.value

    # Supported categories validated against training dataset schema
    SUPPORTED_AIRLINES = {"Air India", "AirAsia", "GO FIRST", "Indigo", "SpiceJet", "Vistara"}
    SUPPORTED_CITIES = {"Bangalore", "Chennai", "Delhi", "Hyderabad", "Kolkata", "Mumbai"}
    SUPPORTED_CLASSES = {"Economy", "Business"}

    def __init__(self, registry: ModelArtifactRegistry):
        self.registry = registry
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", FlightFeaturePreprocessor.EXPECTED_FEATURES)

    def is_offer_supported(self, raw_record: Dict[str, Any]) -> Tuple[bool, str]:
        airline = str(raw_record.get("airline", "")).strip()
        if airline and airline not in self.SUPPORTED_AIRLINES:
            return False, f"Airline '{airline}' is not supported by flight pricing model"

        source = str(raw_record.get("source_city", raw_record.get("origin_city", ""))).strip()
        dest = str(raw_record.get("destination_city", raw_record.get("destination_id", ""))).strip()
        if source and source not in self.SUPPORTED_CITIES:
            return False, f"Origin city '{source}' is not supported by flight pricing model"
        if dest and dest not in self.SUPPORTED_CITIES:
            return False, f"Destination city '{dest}' is not supported by flight pricing model"

        cabin = str(raw_record.get("class", raw_record.get("cabin_class", "Economy"))).strip().capitalize()
        if cabin and cabin not in self.SUPPORTED_CLASSES:
            return False, f"Cabin class '{cabin}' is not supported by flight pricing model"

        return True, ""

    def predict_market_price(self, raw_record: Dict[str, Any]) -> Optional[float]:
        """
        Predicts market ceiling price. Returns None when offer is out-of-domain.
        """
        is_supported, reason = self.is_offer_supported(raw_record)
        if not is_supported:
            logger.info("Flight price prediction unsupported: %s", reason)
            return None

        feat_dict = FlightFeaturePreprocessor.build_features(raw_record)
        row_df = pd.DataFrame([feat_dict])[self.expected_features]

        try:
            X_trans = self.preprocessor.transform(row_df) if self.preprocessor is not None else row_df
            raw_pred = self.estimator.predict(X_trans)
            val = float(raw_pred[0]) if hasattr(raw_pred, "__len__") else float(raw_pred)
            return max(0.0, val) if np.isfinite(val) else None
        except Exception as exc:
            logger.error("Flight price model inference failed: %s", exc)
            raise ModelInferenceError(f"Flight price inference failed: {exc}") from exc

    def handle_prediction_request(self, request: PredictionRequest) -> PredictionResult:
        """PredictionRouter adapter implementing the unified prediction interface."""
        is_supported, reason = self.is_offer_supported(request.features)
        if not is_supported:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                model_name=self.metadata.get("model_name"),
                error_message=reason,
            )

        val = self.predict_market_price(request.features)
        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS if val is not None else InferenceStatus.UNSUPPORTED,
            prediction=val,
            model_name=self.metadata.get("model_name"),
            metadata={"target_column": "price"},
        )
