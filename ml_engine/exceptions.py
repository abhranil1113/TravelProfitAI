"""
ml_engine/exceptions.py

Custom exception hierarchy for the centralized ML Engine.
Provides distinct domain exceptions for registry, preprocessing, and inference failures.
"""


class MLEngineError(Exception):
    """Base exception for all ML Engine operational failures."""
    pass


class ModelNotFoundError(MLEngineError):
    """Raised when a requested model artifact or directory cannot be located."""
    pass


class FeatureValidationError(MLEngineError):
    """Raised when input features fail schema validation, type checks, or value bounds."""
    def __init__(self, message: str, missing_features: list[str] = None, invalid_types: dict = None):
        super().__init__(message)
        self.missing_features = missing_features or []
        self.invalid_types = invalid_types or {}


class SchemaMismatchError(FeatureValidationError):
    """Raised when the input feature vector shape or ordering does not match the model feature contract."""
    pass


class ModelInferenceError(MLEngineError):
    """Raised when the underlying estimator or preprocessor encounters a runtime failure during inference."""
    pass


class ArtifactCorruptedError(MLEngineError):
    """Raised when a serialized model artifact fails checksum verification or deserialization."""
    pass


class UnsupportedPredictionError(MLEngineError):
    """Raised when a prediction request cannot be serviced due to missing domain history or out-of-domain input."""
    pass
