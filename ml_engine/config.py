"""
ml_engine/config.py

Configuration parameters governing artifact directories, strict validation thresholds,
inference execution constraints, queue admission, and checksum policies for the ML Engine.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class MLEngineConfig(BaseModel):
    """Runtime configuration settings for the central ML Engine."""
    base_model_dir: str = "data/models"
    strict_feature_validation: bool = True
    allow_imputation: bool = False  # Strict by default: never silently fabricate missing values
    inference_timeout_seconds: float = 5.0
    batch_timeout_seconds: float = 30.0
    enable_metrics_tracking: bool = True
    cache_models: bool = True
    verify_checksums: bool = True
    strict_checksum_verification: bool = False  # Fail-closed when True and no trusted checksum available
    trusted_checksums: Dict[str, str] = Field(default_factory=dict)  # Independently configured task -> SHA256
    default_random_seed: int = 42
    max_workers: int = 4
    max_queue_depth: int = 32
