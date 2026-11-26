"""
ml_engine/engine.py

Central orchestration interface for the TBO InventoryIQ ML Engine.
Provides unified prediction dispatching, task routing, feature validation,
bounded admission control, true thread-lifecycle semaphore management, timeout enforcement,
batch execution with overall deadlines, operational telemetry, and graceful executor shutdown.
"""

import concurrent.futures
import logging
import threading
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
    InferenceTimeoutError,
    UnsupportedPredictionError,
)
from ml_engine.monitoring.metrics_collector import InferenceMetricsCollector
from ml_engine.preprocessing.schema_validator import FeatureSchemaValidator
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
        strict: bool = True,
        allow_imputation: bool = False,
        numeric_features: Optional[List[str]] = None,
        categorical_features: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str], Dict[str, str], Dict[str, Any]]:
        """
        Validates feature presence, numeric finiteness, and categorical types.
        Returns:
            (is_valid, missing_features, invalid_types, invalid_values)
        """
        return FeatureSchemaValidator.validate_features(
            features=features,
            expected_features=expected_features,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            strict=strict,
            allow_imputation=allow_imputation,
        )


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
    Orchestrates prediction routing, feature validation, timeout enforcement, bounded admission,
    batch deadlines, and operational telemetry.
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

        # Bounded admission control: prevents unbounded work queue growth and executor starvation
        total_capacity = max(1, self.config.max_workers + self.config.max_queue_depth)
        self._admission_semaphore = threading.BoundedSemaphore(total_capacity)

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_workers,
            thread_name_prefix="MLEngineWorker"
        )
        self._is_shutdown = False
        self._lifecycle_lock = threading.Lock()

    def __enter__(self) -> "MLEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown(wait=True)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """
        Gracefully terminates internal thread pool executor without interrupting active tasks unexpectedly.
        """
        with self._lifecycle_lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            logger.info("Initiating MLEngine executor shutdown (wait=%s)...", wait)
            try:
                self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
            except TypeError:
                # Older Python versions may not accept cancel_futures
                self._executor.shutdown(wait=wait)
            logger.info("MLEngine executor shutdown completed.")

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

    def _record_telemetry(self, task_name: str, latency_ms: float, is_success: bool, is_unsupported: bool = False) -> None:
        """Conditionally records telemetry metrics if enabled in configuration."""
        if self.config.enable_metrics_tracking:
            self.metrics.record_inference(
                task_name=task_name,
                latency_ms=latency_ms,
                is_success=is_success,
                is_unsupported=is_unsupported,
            )

    def _release_admission_slot(self, future: concurrent.futures.Future) -> None:
        """
        Callback invoked strictly when the underlying future completes or is cancelled.
        Guarantees that a timed-out caller does not release a slot while the worker thread is still running.
        """
        try:
            self._admission_semaphore.release()
        except ValueError:
            pass

    def predict(
        self,
        request: PredictionRequest,
        timeout_override: Optional[float] = None,
        admission_timeout_override: Optional[float] = None,
    ) -> PredictionResult:
        """
        Executes unified prediction for a single request with bounded admission and timeout enforcement.
        Note: Python threads cannot be preemptively killed in-process. If a task exceeds its timeout,
        the Future returns TIMEOUT to the caller immediately, but the thread continues executing until completion.
        The admission slot remains occupied until the underlying worker finishes, preventing thread pool starvation.
        """
        if self._is_shutdown:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                error_message="MLEngine has been shut down; request rejected.",
            )

        start_time = time.perf_counter()

        # 1. Bounded admission check: clamp admission wait to available budget
        adm_timeout = 0.05
        if admission_timeout_override is not None:
            adm_timeout = max(0.001, admission_timeout_override)
        elif timeout_override is not None:
            adm_timeout = min(0.05, max(0.001, timeout_override))

        admitted = self._admission_semaphore.acquire(blocking=True, timeout=adm_timeout)
        if not admitted:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            logger.warning("Inference admission rejected: queue capacity saturated for task %s", request.task.value)
            self._record_telemetry(request.task.value, latency_ms, is_success=False)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                latency_ms=latency_ms,
                error_message="Inference rejected: engine queue capacity exceeded (admission overload).",
            )

        # 2. Check remaining execution time budget after queue admission
        now = time.perf_counter()
        elapsed_admission = now - start_time
        if timeout_override is not None:
            remaining_after_admission = timeout_override - elapsed_admission
            if remaining_after_admission <= 0:
                # Batch/overall deadline expired during queue admission; release slot immediately
                self._admission_semaphore.release()
                latency_ms = float(round(elapsed_admission * 1000.0, 3))
                logger.warning("Inference deadline expired during queue admission for task %s", request.task.value)
                self._record_telemetry(request.task.value, latency_ms, is_success=False)
                return PredictionResult(
                    task=request.task,
                    status=InferenceStatus.TIMEOUT,
                    prediction=None,
                    latency_ms=latency_ms,
                    error_message=f"Inference deadline expired during queue admission (elapsed: {latency_ms:.1f}ms).",
                )
            timeout_sec = min(self.config.inference_timeout_seconds, remaining_after_admission)
        else:
            timeout_sec = self.config.inference_timeout_seconds

        # 3. Submit task to thread pool
        try:
            future = self._executor.submit(self._execute_prediction, request)
        except Exception as submit_exc:
            # If submission fails (e.g. executor shut down concurrently), release immediately
            self._admission_semaphore.release()
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            logger.error("Failed to submit inference task for %s: %s", request.task.value, submit_exc)
            self._record_telemetry(request.task.value, latency_ms, is_success=False)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                latency_ms=latency_ms,
                error_message=f"Task submission failed: {submit_exc}",
            )

        # Attach callback so admission slot is released ONLY when the worker actually finishes or is cancelled
        future.add_done_callback(self._release_admission_slot)

        # 4. Wait up to clamped timeout threshold
        try:
            result = future.result(timeout=timeout_sec)
            return result
        except concurrent.futures.TimeoutError:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            logger.error("Inference timed out for task %s after %.2fs", request.task.value, timeout_sec)
            self._record_telemetry(request.task.value, latency_ms, is_success=False)
            # NOTE: The admission slot is NOT released here. The background worker is still running.
            # _release_admission_slot will release the slot once the thread actually completes.
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.TIMEOUT,
                prediction=None,
                latency_ms=latency_ms,
                error_message=f"Inference exceeded timeout of {timeout_sec:.2f}s",
            )
        except Exception as exc:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            logger.error("Worker exception during inference for %s: %s", request.task.value, exc)
            self._record_telemetry(request.task.value, latency_ms, is_success=False)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                latency_ms=latency_ms,
                error_message=str(exc),
            )

    def _execute_prediction(self, request: PredictionRequest) -> PredictionResult:
        """Internal worker executing model prediction."""
        start_time = time.perf_counter()

        try:
            # 1. Specialized handler dispatch if registered
            if self.router.has_handler(request.task):
                result = self.router.dispatch(request)
                latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
                result.latency_ms = latency_ms

                is_success = (result.status == InferenceStatus.SUCCESS)
                is_unsup = (result.status == InferenceStatus.UNSUPPORTED)
                self._record_telemetry(request.task.value, latency_ms, is_success, is_unsup)
                return result

            # 2. Generic artifact loading fallback if registry is connected
            if self.registry is not None:
                res = self._predict_via_registry(request, start_time)
                self._record_telemetry(request.task.value, res.latency_ms, is_success=True)
                return res

            raise ModelNotFoundError(
                f"No predictor service or model registry configured for task '{request.task.value}'"
            )

        except UnsupportedPredictionError as upe:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            self._record_telemetry(request.task.value, latency_ms, is_success=False, is_unsupported=True)
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
            self._record_telemetry(request.task.value, latency_ms, is_success=False)
            logger.warning("Feature validation failed for task %s: %s", request.task.value, fve)
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.FAILED,
                prediction=None,
                latency_ms=latency_ms,
                error_message=str(fve),
                metadata={
                    "missing_features": fve.missing_features,
                    "invalid_types": fve.invalid_types,
                    "invalid_values": fve.invalid_values,
                },
            )
        except Exception as exc:
            latency_ms = float(round((time.perf_counter() - start_time) * 1000.0, 3))
            self._record_telemetry(request.task.value, latency_ms, is_success=False)
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
        Executes multi-record batch inference with an overall batch deadline.
        Preserves original input ordering and isolates per-record outcomes.
        Marks unreached records with TIMEOUT once the overall batch deadline expires.
        """
        start_batch = time.perf_counter()
        results: List[PredictionResult] = []
        success_cnt = 0
        failed_cnt = 0
        unsupported_cnt = 0
        timeout_cnt = 0

        batch_timeout = request.batch_timeout_seconds or self.config.batch_timeout_seconds
        batch_deadline = start_batch + batch_timeout

        for idx, record in enumerate(request.records):
            now = time.perf_counter()
            remaining_time = batch_deadline - now

            if remaining_time <= 0:
                # Overall batch deadline has expired: fail remaining items with TIMEOUT
                elapsed_ms = float(round((now - start_batch) * 1000.0, 3))
                timeout_res = PredictionResult(
                    task=request.task,
                    status=InferenceStatus.TIMEOUT,
                    prediction=None,
                    latency_ms=elapsed_ms,
                    error_message=f"Overall batch deadline of {batch_timeout:.1f}s exceeded prior to processing record {idx}",
                )
                results.append(timeout_res)
                timeout_cnt += 1
                continue

            single_req = PredictionRequest(
                task=request.task,
                features=record,
                context=request.context,
            )
            # Clamp per-record admission and execution timeouts to remaining batch budget
            clamped_admission = min(0.05, max(0.001, remaining_time))
            res = self.predict(
                single_req,
                timeout_override=remaining_time,
                admission_timeout_override=clamped_admission,
            )
            results.append(res)

            if res.status == InferenceStatus.SUCCESS:
                success_cnt += 1
            elif res.status == InferenceStatus.UNSUPPORTED:
                unsupported_cnt += 1
            elif res.status == InferenceStatus.TIMEOUT:
                timeout_cnt += 1
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
            timeout_records=timeout_cnt,
            total_latency_ms=total_latency_ms,
        )

    def _predict_via_registry(self, request: PredictionRequest, start_time: float) -> PredictionResult:
        """Internal generic inference path using the connected model registry."""
        task_name = request.task.value
        estimator, preprocessor, metadata = self.registry.get_model(task_name)
        expected_features: List[str] = metadata.get("feature_names", [])

        # Validate input features against model contract
        is_valid, missing, inv_types, inv_vals = self.validator.validate_features(
            request.features,
            expected_features,
            strict=self.config.strict_feature_validation,
            allow_imputation=self.config.allow_imputation,
        )
        if not is_valid:
            err_msg = f"Feature validation failed for {task_name}"
            if missing:
                err_msg += f": missing {missing}"
            if inv_vals:
                err_msg += f": invalid {inv_vals}"
            raise FeatureValidationError(
                err_msg,
                missing_features=missing,
                invalid_types=inv_types,
                invalid_values=inv_vals,
            )

        row_df = pd.DataFrame([request.features])[expected_features]
        X_trans = preprocessor.transform(row_df) if preprocessor is not None else row_df

        # Predict
        if hasattr(estimator, "predict_proba"):
            raw_proba = estimator.predict_proba(X_trans)
            prob_dict = {f"class_{i}": float(p) for i, p in enumerate(raw_proba[0])}
            val = float(raw_proba[0][1]) if len(raw_proba[0]) > 1 else float(raw_proba[0][0])
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
            prediction_type="MODEL",
            prediction_label=pred_label,
            probabilities=prob_dict,
            latency_ms=latency_ms,
            model_name=metadata.get("model_name"),
            model_version=metadata.get("saved_timestamp"),
            artifact_checksum=metadata.get("_artifact_sha256"),
            checksum_verified=bool(metadata.get("_checksum_verified", False)),
            is_independently_trusted=bool(metadata.get("_is_independently_trusted", False)),
            metadata={
                "target_column": metadata.get("target_column"),
                "checksum_trust_source": metadata.get("_checksum_trust_source"),
            },
        )
