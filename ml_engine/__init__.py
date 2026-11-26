"""
ml_engine package entrypoint.
Exposes public classes, exceptions, configuration, and monitoring for the centralized ML Engine.
"""

from ml_engine.config import MLEngineConfig
from ml_engine.engine import MLEngine, FeatureValidator, PredictionRouter
from ml_engine.adapters import OptimizationMLAdapter
from ml_engine.exceptions import (
    MLEngineError,
    ModelNotFoundError,
    FeatureValidationError,
    SchemaMismatchError,
    ModelInferenceError,
    InferenceTimeoutError,
    ArtifactCorruptedError,
    ChecksumMismatchError,
    UnsupportedPredictionError,
)
from ml_engine.schemas import (
    PredictionTask,
    InferenceStatus,
    PredictionRequest,
    PredictionResult,
    BatchPredictionRequest,
    BatchPredictionResult,
    ModelMetadataSchema,
)
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.model_registry.model_metadata import ModelMetadataValidator
from ml_engine.monitoring.metrics_collector import InferenceMetricsCollector
from ml_engine.monitoring.data_drift import DataDriftDetector

__all__ = [
    "MLEngine",
    "MLEngineConfig",
    "FeatureValidator",
    "PredictionRouter",
    "OptimizationMLAdapter",
    "PredictionTask",
    "InferenceStatus",
    "PredictionRequest",
    "PredictionResult",
    "BatchPredictionRequest",
    "BatchPredictionResult",
    "ModelMetadataSchema",
    "ModelArtifactRegistry",
    "ModelMetadataValidator",
    "InferenceMetricsCollector",
    "DataDriftDetector",
    "MLEngineError",
    "ModelNotFoundError",
    "FeatureValidationError",
    "SchemaMismatchError",
    "ModelInferenceError",
    "InferenceTimeoutError",
    "ArtifactCorruptedError",
    "ChecksumMismatchError",
    "UnsupportedPredictionError",
]
