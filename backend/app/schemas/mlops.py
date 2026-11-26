from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.schema import (
    DeploymentMode,
    DeploymentStatus,
    DriftSeverity,
    FreshnessStatus,
    MLModelType,
    ModelLifecycleAction,
    RetrainingTriggerMetric,
)


# =============================================================================
# DOMAIN 2: MLOPS PRODUCTION GOVERNANCE
# =============================================================================

class DriftComputeRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int = Field(..., ge=1)
    baseline_window_start: date
    baseline_window_end: date
    target_window_start: date
    target_window_end: date
    baseline_features: Dict[str, List[float]] = Field(..., min_length=1)
    target_features: Dict[str, List[float]] = Field(..., min_length=1)
    num_buckets: int = Field(10, ge=5, le=20)

    @model_validator(mode="after")
    def validate_windows_and_samples(self) -> DriftComputeRequest:
        if self.baseline_window_start > self.baseline_window_end:
            raise ValueError("baseline_window_start cannot be after baseline_window_end.")
        if self.target_window_start > self.target_window_end:
            raise ValueError("target_window_start cannot be after target_window_end.")
        common_cols = set(self.baseline_features.keys()) & set(self.target_features.keys())
        if not common_cols:
            raise ValueError("baseline_features and target_features must share at least one feature column.")
        for col in common_cols:
            if len(self.baseline_features[col]) < 10 or len(self.target_features[col]) < 10:
                raise ValueError(f"Feature '{col}' requires at least 10 observations in both baseline and target windows.")
        return self


class ModelDriftReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    report_uid: str
    model_id: int
    model_type: MLModelType
    baseline_window_start: date
    baseline_window_end: date
    target_window_start: date
    target_window_end: date
    sample_size_baseline: int
    sample_size_target: int
    overall_psi: float
    max_ks_statistic: float
    min_ks_pvalue: float
    severity: DriftSeverity
    feature_metrics_json: Dict[str, Any] = Field(default_factory=dict)
    computed_by_service: str
    retraining_recommended: bool
    created_at: datetime


class ModelDriftReportListResponse(BaseModel):
    items: List[ModelDriftReportResponse]
    total: int
    page: int
    page_size: int


class FeatureFreshnessCheckRequest(BaseModel):
    feature_set_id: Optional[int] = None
    feature_group_name: str = Field(..., min_length=2, max_length=100)
    last_updated_at: datetime
    sla_threshold_seconds: int = Field(86400, ge=60, le=2592000)
    record_count: int = Field(0, ge=0)
    details_json: Dict[str, Any] = Field(default_factory=dict)


class FeatureFreshnessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature_set_id: Optional[int] = None
    feature_group_name: str
    last_updated_at: datetime
    evaluated_at: datetime
    lag_seconds: int
    sla_threshold_seconds: int
    status: FreshnessStatus
    record_count: int
    details_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ModelDeploymentCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: int = Field(..., ge=1)
    deployment_mode: DeploymentMode
    traffic_percentage: float = Field(0.0, ge=0.0, le=100.0)
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_mode_traffic_isolation(self) -> ModelDeploymentCreateRequest:
        if self.deployment_mode == DeploymentMode.SHADOW and self.traffic_percentage != 0.0:
            raise ValueError("SHADOW deployment must have traffic_percentage=0.0 and cannot influence live decisions.")
        if self.deployment_mode == DeploymentMode.CANARY and self.traffic_percentage <= 0.0:
            raise ValueError("CANARY deployment requires traffic_percentage > 0.0 and <= 100.0.")
        return self


class ModelDeploymentUpdateRequest(BaseModel):
    traffic_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    status: Optional[DeploymentStatus] = None
    notes: Optional[str] = Field(None, max_length=1000)


class ModelDeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    deployment_uid: str
    model_id: int
    model_type: MLModelType
    deployment_mode: DeploymentMode
    status: DeploymentStatus
    traffic_percentage: float
    influences_live_decisions: bool
    deployed_by_user_id: Optional[int] = None
    activated_at: datetime
    ended_at: Optional[datetime] = None
    rollback_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ShadowPredictionLogRequest(BaseModel):
    entity_id: str = Field(..., min_length=1, max_length=64)
    features: Dict[str, Any] = Field(default_factory=dict)
    champion_prediction: Optional[float] = None
    candidate_prediction: Optional[float] = None


class ShadowPredictionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    deployment_id: int
    model_id: int
    entity_id: str
    champion_prediction: Optional[float] = None
    candidate_prediction: float
    prediction_delta: Optional[float] = None
    latency_ms: float
    features_hash: Optional[str] = None
    recorded_at: datetime


class ModelRollbackRequest(BaseModel):
    target_model_id: Optional[int] = None
    reason: str = Field(..., min_length=5, max_length=1000)


class ModelPromoteGovernanceRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)
    require_no_severe_drift: bool = True


class ModelLifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_id: int
    model_type: MLModelType
    action: ModelLifecycleAction
    previous_champion_model_id: Optional[int] = None
    performed_by_user_id: Optional[int] = None
    reason: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class RetrainingTriggerConfigRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_type: MLModelType
    trigger_metric: RetrainingTriggerMetric
    threshold_value: float = Field(..., gt=0.0)
    auto_trigger_training: bool = False
    cooldown_hours: int = Field(24, ge=1, le=720)
    is_enabled: bool = True


class RetrainingTriggerConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_type: MLModelType
    trigger_metric: RetrainingTriggerMetric
    threshold_value: float
    auto_trigger_training: bool
    cooldown_hours: int
    is_enabled: bool
    last_triggered_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
