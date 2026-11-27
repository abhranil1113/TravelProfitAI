"""
ml_engine/price_prediction/price_prediction_service.py

Production flight market ceiling price prediction service.
Predicts market reference price and validates supported routes, airlines, and cabins.
Rejects missing flight parameters strictly without fabricating synthetic default routes or carriers.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError, FeatureValidationError
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.preprocessing.preprocess_flight import FlightFeaturePreprocessor
from ml_engine.schemas import PredictionTask, PredictionRequest, PredictionResult, InferenceStatus

logger = logging.getLogger(__name__)


class PricePredictionService:
    """Service predicting market ceiling price for flight wholesale offers."""

    TASK_NAME = PredictionTask.FLIGHT_PRICE.value

    # Supported categories validated against training dataset schema
    SUPPORTED_AIRLINES = {"Air_India", "AirAsia", "GO_FIRST", "Indigo", "SpiceJet", "Vistara"}
    AIRLINE_ALIASES = {
        "air india": "Air_India",
        "air_india": "Air_India",
        "airasia": "AirAsia",
        "go first": "GO_FIRST",
        "go_first": "GO_FIRST",
        "indigo": "Indigo",
        "spicejet": "SpiceJet",
        "vistara": "Vistara",
    }
    SUPPORTED_CITIES = {"Bangalore", "Chennai", "Delhi", "Hyderabad", "Kolkata", "Mumbai"}
    AIRPORT_CODE_TO_CITY = {
        "BLR": "Bangalore",
        "MAA": "Chennai",
        "DEL": "Delhi",
        "HYD": "Hyderabad",
        "CCU": "Kolkata",
        "BOM": "Mumbai",
    }
    SUPPORTED_CLASSES = {"Economy", "Business"}

    def __init__(self, registry: ModelArtifactRegistry):
        self.registry = registry
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", FlightFeaturePreprocessor.EXPECTED_FEATURES)

    def is_offer_supported(self, raw_record: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verifies that all mandatory route and carrier fields are present and supported.
        Never allows empty or missing flight attributes to pass silently.
        """
        # Validate field presence first
        missing = FlightFeaturePreprocessor.validate_raw_record(raw_record)
        if missing:
            return False, f"Missing required flight fields: {missing}"

        airline_raw = str(raw_record.get("airline", "")).strip()
        airline = self.AIRLINE_ALIASES.get(airline_raw.lower(), airline_raw)
        if not airline or airline not in self.SUPPORTED_AIRLINES:
            return False, f"Airline '{airline_raw}' is not in supported training domains: {sorted(self.SUPPORTED_AIRLINES)}"

        source_raw = str(raw_record.get("source_city") or raw_record.get("origin_city", "")).strip()
        dest_raw = str(raw_record.get("destination_city") or raw_record.get("destination_id", "")).strip()
        source = self.AIRPORT_CODE_TO_CITY.get(source_raw.upper(), source_raw)
        dest = self.AIRPORT_CODE_TO_CITY.get(dest_raw.upper(), dest_raw)
        if not source or source not in self.SUPPORTED_CITIES:
            return False, f"Origin city '{source_raw}' is not in supported flight cities: {sorted(self.SUPPORTED_CITIES)}"
        if not dest or dest not in self.SUPPORTED_CITIES:
            return False, f"Destination city '{dest_raw}' is not in supported flight cities: {sorted(self.SUPPORTED_CITIES)}"

        cabin = str(raw_record.get("class") or raw_record.get("cabin_class", "Economy")).strip().capitalize()
        if not cabin or cabin not in self.SUPPORTED_CLASSES:
            return False, f"Cabin class '{cabin}' is not supported: {sorted(self.SUPPORTED_CLASSES)}"

        return True, ""

    def predict_market_price(self, raw_record: Dict[str, Any]) -> Optional[float]:
        """
        Predicts market ceiling price. Returns None when offer is out-of-domain or incomplete.
        """
        is_supported, reason = self.is_offer_supported(raw_record)
        if not is_supported:
            logger.info("Flight price prediction unsupported: %s", reason)
            return None

        feat_dict = FlightFeaturePreprocessor.build_features(raw_record, allow_imputation=False)
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
                prediction_type="MODEL",
                model_name=self.metadata.get("model_name"),
                model_version=self.metadata.get("saved_timestamp"),
                artifact_checksum=self.metadata.get("_artifact_sha256"),
                checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
                is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
                error_message=reason,
                metadata={"checksum_trust_source": self.metadata.get("_checksum_trust_source")},
            )

        val = self.predict_market_price(request.features)
        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS if val is not None else InferenceStatus.UNSUPPORTED,
            prediction=val,
            prediction_type="MODEL",
            model_name=self.metadata.get("model_name"),
            model_version=self.metadata.get("saved_timestamp"),
            artifact_checksum=self.metadata.get("_artifact_sha256"),
            checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
            is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
            error_message="Price prediction returned unavailable value" if val is None else None,
            metadata={
                "target_column": "price",
                "checksum_trust_source": self.metadata.get("_checksum_trust_source"),
            },
        )
