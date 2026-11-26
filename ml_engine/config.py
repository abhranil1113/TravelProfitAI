"""
ml_engine/config.py

Configuration parameters governing artifact directories, strict validation thresholds,
and inference execution constraints for the ML Engine.
"""

from pydantic import BaseModel, Field


class MLEngineConfig(BaseModel):
    """Runtime configuration settings for the central ML Engine."""
    base_model_dir: str = "data/models"
    strict_feature_validation: bool = True
    allow_imputation: bool = True
    inference_timeout_seconds: float = 5.0
    enable_metrics_tracking: bool = True
    cache_models: bool = True
    default_random_seed: int = 42
