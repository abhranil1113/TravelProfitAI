"""
ml_engine/engine.py

Central orchestration interface for the TBO InventoryIQ ML Engine.
Provides unified prediction dispatching, task routing, feature validation,
batch inference, latency monitoring, and error handling.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
import numpy as np
import pandas as pd

from ml_engine.config import MLEngineConfig
from ml_engine.exceptions import (
    MLEngineError,
    ModelNotFoundError,
    FeatureValidationError,
    ModelInferenceError,
    UnsupportedPredictionError,
)
from ml_engine.monitoring.metrics_collector import InferenceMetricsCollector
from ml_engine.schemas import (
    PredictionTask,
    InferenceStatus,
    PredictionRequest,
    PredictionResult,
    BatchPredictionRequest,
    BatchPredictionResult,
)

logger = logging.getLogger(__name__)


class FeatureValidator:
    """Validates raw feature dictionaries against model contracts."""

    @staticmethod
    def validate_features(
        features: Dict[str, Any],
        expected_features: List[str],
        strict: bool = True
    ) -> Tuple[bool, List[str], Dict[str, str]]:
        """
        Validates feature presence and completeness.
        Returns:
            (is_valid, missing_features, invalid_fields)
        """
        missing = [f for f in expected_features if f not in features or features[f] is None]
        invalid = {}

        if strict and missing:
            return False, missing, invalid

        return len(missing) == 0, missing, invalid


class PredictionRouter:
    """Dispatches prediction tasks to registered predictor services or handlers."""

    def __init__(self):
        self._handlers: Dict[PredictionTask, Callable[[PredictionRequest], PredictionResult]] = {}

    def register(self, task: PredictionTask, handler: Callable[[PredictionRequest], PredictionResult]) -> None:
        """Registers a specialized prediction service handler for a task."""
        self._handlers[task] = handler
        logger.info("Registered predictor handler for task: %s", task.value)

    def has_handler(self, task: PredictionTask) -> bool:
        """Checks if a specialized predictor is registered for the task."""
        return task in self._handlers

    def dispatch(self, request: PredictionRequest) -> PredictionResult:
        """Routes the request to the registered predictor handler."""
        if request.task not in self._handlers:
            raise ModelNotFoundError(f"No predictor handler registered for task '{request.task.value}'")
        return self._handlers[request.task](request)


class MLEngine:
    """
    Central, production-oriented Machine Learning Engine for TBO InventoryIQ.
    Orchestrates prediction routing, feature validation, batch execution, and operational monitoring.
    """

    def __init__(
        self,
        config: Optional[MLEngineConfig] = None,
        registry: Optional[Any] = None,
    ):
        self.config = config or MLEngineConfig()
        self.registry = registry
        self.router = PredictionRouter()
        self.validator = FeatureValidator()
        self.metrics = InferenceMetricsCollector.get_instance()

    @classmethod
    def create_default(
        cls,
        base_model_dir: str = "data/models",
        db: Optional[Any] = None,
        registry: Optional[Any] = None,
        searches_df: Optional[pd.DataFrame] = None,
        optimization_timestamp: Optional[str] = None,
    ) -> "MLEngine":
        """
        Factory creating a fully wired central ML Engine with all domain predictors registered.
        """
        from ml_engine.model_registry.registry import ModelArtifactRegistry
        from ml_engine.demand_forecasting.forecast_service import DemandForecastService
        from ml_engine.price_prediction.price_prediction_service import PricePredictionService
        from ml_engine.risk_prediction.risk_prediction_service import RiskPredictionService
        from ml_engine.inventory_forecasting.inventory_forecast_service import InventoryForecastService

        reg = registry or ModelArtifactRegistry(base_dir=base_model_dir, db=db)
        engine = cls(config=MLEngineConfig(base_model_dir=base_model_dir), registry=reg)

        # Register domain predictor handlers
        try:
            demand_svc = DemandForecastService(
                registry=reg, searches_df=searches_df, optimization_timestamp=optimization_timestamp
            )
            engine.register_predictor(PredictionTask.DEMAND_FORECASTING, demand_svc.handle_prediction_request)
        except Exception as e:
            logger.debug("Demand service auto-registration skipped: %s", e)

        try:
            price_svc = PricePredictionService(registry=reg)
            engine.register_predictor(PredictionTask.FLIGHT_PRICE, price_svc.handle_prediction_request)
        except Exception as e:
            logger.debug("Flight price service auto-registration skipped: %s", e)

        try:
            risk_svc = RiskPredictionService(registry=reg)
            engine.register_predictor(PredictionTask.HOTEL_CANCELLATION, risk_svc.handle_prediction_request)
        except Exception as e:
            logger.debug("Hotel cancellation risk service auto-registration skipped: %s", e)

        try:
            inv_svc = InventoryForecastService(registry=reg)
            engine.register_predictor(PredictionTask.INVENTORY_FORECASTING, inv_svc.handle_prediction_request)
        except Exception as e:
            logger.debug("Inventory forecast service auto-registration skipped: %s", e)

        return engine

    def register_predictor(
        self, task: PredictionTask, handler: Callable[[PredictionRequest], PredictionResult]
    ) -> None:
        """Registers a dedicated domain predictor for a specific task."""
        self.router.register(task, handler)

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """
        Executes unified prediction for a single request with profiling and error isolation.
        Guarantees structured PredictionResult return without unhandled process termination.
        """
        start_time = time.perf_counter()

        try:
            # 1. Specialized handler dispatch if registered
            if self.router.has_handler(request.task):
                result = self.router.dispatch(request)
                latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
                result.latency_ms = latency_ms

                # Record telemetry
                is_success = (result.status == InferenceStatus.SUCCESS)
                is_unsup = (result.status == InferenceStatus.UNSUPPORTED)
                self.metrics.record_inference(request.task.value, latency_ms, is_success, is_unsup)
                return result

            # 2. Generic artifact loading fallback if registry is connected
            if self.registry is not None:
                res = self._predict_via_registry(request, start_time)
                self.metrics.record_inference(request.task.value, res.latency_ms, is_success=True)
                return res

            raise ModelNotFoundError(
                f"No predictor service or model registry configured for task '{request.task.value}'"
            )

        except UnsupportedPredictionError as upe:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            self.metrics.record_inference(request.task.value, latency_ms, is_success=False, is_unsupported=True)
            logger.info("Prediction unsupported for task %s (%s): %s", request.task.value, request.entity_id, upe)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                latency_ms=latency_ms,
                error_message=str(upe),
            )
        except FeatureValidationError as fve:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            self.metrics.record_inference(request.task.value, latency_ms, is_success=False)
            logger.warning("Feature validation failed for task %s: %s", request.task.value, fve)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                latency_ms=latency_ms,
                error_message=str(fve),
                metadata={"missing_features": fve.missing_features},
            )
        except Exception as exc:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            self.metrics.record_inference(request.task.value, latency_ms, is_success=False)
            logger.error("Inference failure for task %s: %s", request.task.value, exc, exc_info=True)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                latency_ms=latency_ms,
                error_message=str(exc),
            )

    def batch_predict(self, request: BatchPredictionRequest) -> BatchPredictionResult:
        """
        Executes multi-record batch inference with per-record isolation and aggregate metrics.
        """
        start_batch = time.perf_counter()
        results: List[PredictionResult] = []
        success_cnt = 0
        failed_cnt = 0
        unsupported_cnt = 0

        for record in request.records:
            single_req = PredictionRequest(
                task=request.task,
                features=record,
                context=request.context,
            )
            res = self.predict(single_req)
            results.append(res)

            if res.status == InferenceStatus.SUCCESS:
                success_cnt += 1
            elif res.status == InferenceStatus.UNSUPPORTED:
                unsupported_cnt += 1
            else:
                failed_cnt += 1

        total_latency_ms = float(round((time.perf_counter() - start_batch) * 1000.0, 3))

        return BatchPredictionResult(
            task=request.task,
            results=results,
            total_records=len(request.records),
            successful_records=success_cnt,
            failed_records=failed_cnt,
            unsupported_records=unsupported_cnt,
            total_latency_ms=total_latency_ms,
        )

    def _predict_via_registry(self, request: PredictionRequest, start_time: float) -> PredictionResult:
        """Internal generic inference path using the connected model registry."""
        task_name = request.task.value
        estimator, preprocessor, metadata = self.registry.get_model(task_name)
        expected_features: List[str] = metadata.get("feature_names", [])

        # Validate input features against model contract
        is_valid, missing, _ = self.validator.validate_features(
            request.features, expected_features, strict=self.config.strict_feature_validation
        )
        if not is_valid:
            raise FeatureValidationError(
                f"Missing required features for {task_name}: {missing}", missing_features=missing
            )

        row_df = pd.DataFrame([request.features])[expected_features]
        X_trans = preprocessor.transform(row_df) if preprocessor is not None else row_df

        # Predict
        if hasattr(estimator, "predict_proba"):
            raw_proba = estimator.predict_proba(X_trans)
            prob_dict = {f"class_{i}": float(p) for i, p in enumerate(raw_proba[0])}
            val = float(raw_prob[0][1]) if len(raw_proba[0]) > 1 else float(raw_proba[0][0])
            pred_label = "POSITIVE" if val >= 0.5 else "NEGATIVE"
        else:
            raw_pred = estimator.predict(X_trans)
            val = float(raw_pred[0]) if hasattr(raw_pred, "__len__") else float(raw_pred)
            prob_dict = None
            pred_label = None

        latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS,
            prediction=val,
            prediction_label=pred_label,
            probabilities=prob_dict,
            latency_ms=latency_ms,
            model_name=metadata.get("model_name"),
            model_version=metadata.get("saved_timestamp"),
            metadata={"target_column": metadata.get("target_column")},
        )
