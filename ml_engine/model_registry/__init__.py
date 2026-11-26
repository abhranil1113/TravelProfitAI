"""
ml_engine/model_registry package entrypoint.
Exposes ModelArtifactRegistry and ModelMetadataValidator.
"""

from ml_engine.model_registry.model_metadata import ModelMetadataValidator
from ml_engine.model_registry.registry import ModelArtifactRegistry

__all__ = [
    "ModelArtifactRegistry",
    "ModelMetadataValidator",
]
