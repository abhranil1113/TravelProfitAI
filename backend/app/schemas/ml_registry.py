from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import MLModelType, TrainingStatus


class FeatureSetCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=2, max_length=100)
    version: str = Field(..., max_length=32)
    model_type: MLModelType
    parquet_path: str = Field(..., max_length=512)
    num_rows: int = Field(..., ge=0)
    num_features: int = Field(..., ge=0)
    column_names: List[str]
    split_type: Optional[str] = Field("TEMPORAL", max_length=32)
    cutoff_date: Optional[date] = None


class FeatureSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    name: str
    version: str
    model_type: MLModelType
    parquet_path: str
    num_rows: int
    num_features: int
    column_names_json: List[str]
    split_type: Optional[str] = None
    cutoff_date: Optional[date] = None
    created_at: datetime


class MLModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_type: MLModelType
    version: str
    algorithm: str
    artifact_dir: Optional[str] = None
    metrics_json: Optional[Dict[str, Any]] = None
    training_cutoff_date: Optional[date] = None
    is_champion: bool
    artifact_checksum: Optional[str] = None
    feature_schema_version: Optional[str] = None
    framework_version: Optional[str] = None
    model_status: Optional[str] = None
    promoted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MLModelListResponse(BaseModel):
    items: List[MLModelResponse]
    total: int


class ModelTrainingTriggerRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_type: MLModelType
    feature_set_id: int
    algorithm: str = Field("LightGBM", max_length=64)
    hyperparameters: Optional[Dict[str, Any]] = None
    cv_folds: int = Field(5, ge=2, le=10)
    notes: Optional[str] = None


class ModelTrainingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_type: MLModelType
    feature_set_id: int
    algorithm: str
    hyperparameters_json: Optional[Dict[str, Any]] = None
    cv_folds: int
    status: TrainingStatus
    training_started_at: Optional[datetime] = None
    training_completed_at: Optional[datetime] = None
    metrics_json: Optional[Dict[str, Any]] = None
    feature_importance_json: Optional[Dict[str, Any]] = None
    artifact_dir: Optional[str] = None
    promoted_model_id: Optional[int] = None
    celery_task_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ModelTrainingRunListResponse(BaseModel):
    items: List[ModelTrainingRunResponse]
    total: int
    page: int
    page_size: int
