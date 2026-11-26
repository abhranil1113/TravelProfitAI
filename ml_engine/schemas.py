"""
ml_engine/schemas.py

Typed data schemas for prediction requests, results, batch inference,
and model metadata definitions.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PredictionTask(str, Enum):
    """Supported machine learning inference tasks."""
    DEMAND_FORECASTING = "demand_forecasting"
    FLIGHT_PRICE = "flight_price"
    HOTEL_CANCELLATION = "hotel_cancellation"
    INVENTORY_FORECASTING = "inventory_forecasting"
    SUPPLIER_LEAD_TIME = "supplier_lead_time_prediction"


class InferenceStatus(str, Enum):
    """Status outcomes for prediction operations."""
    SUCCESS = "SUCCESS"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class PredictionRequest(BaseModel):
    """Unified single-record prediction request payload."""
    task: PredictionTask
    features: Dict[str, Any]
    entity_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PredictionResult(BaseModel):
    """Standardized prediction response returned across all ML tasks."""
    task: PredictionTask
    status: InferenceStatus
    prediction: Optional[Any] = None
    prediction_label: Optional[str] = None
    confidence_score: Optional[float] = None
    probabilities: Optional[Dict[str, float]] = None
    latency_ms: float = 0.0
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BatchPredictionRequest(BaseModel):
    """Unified multi-record prediction request payload."""
    task: PredictionTask
    records: List[Dict[str, Any]]
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BatchPredictionResult(BaseModel):
    """Standardized multi-record prediction response."""
    task: PredictionTask
    results: List[PredictionResult]
    total_records: int
    successful_records: int
    failed_records: int
    unsupported_records: int
    total_latency_ms: float


class ModelMetadataSchema(BaseModel):
    """Schema representing validated metadata.json serialized alongside model artifacts."""
    task_name: str
    task_type: str
    model_name: str
    target_column: Optional[str] = None
    feature_names: List[str]
    feature_count: int
    saved_timestamp: Optional[str] = None
    random_seed: Optional[int] = 42
    test_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    cv_summary: Optional[Dict[str, Any]] = Field(default_factory=dict)
    business_params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    selection_rationale: Optional[str] = None
