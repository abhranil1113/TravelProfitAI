from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles, require_worker_token
from backend.app.models.schema import (
    DeploymentMode,
    DeploymentStatus,
    DriftSeverity,
    FreshnessStatus,
    MLModelType,
    User,
    UserRole,
)
from backend.app.schemas.ml_registry import MLModelResponse
from backend.app.schemas.mlops import (
    DriftComputeRequest,
    FeatureFreshnessCheckRequest,
    FeatureFreshnessResponse,
    ModelDeploymentCreateRequest,
    ModelDeploymentResponse,
    ModelDeploymentUpdateRequest,
    ModelDriftReportListResponse,
    ModelDriftReportResponse,
    ModelLifecycleEventResponse,
    ModelPromoteGovernanceRequest,
    ModelRollbackRequest,
    RetrainingTriggerConfigRequest,
    RetrainingTriggerConfigResponse,
    ShadowPredictionLogRequest,
    ShadowPredictionLogResponse,
)
from backend.app.services.mlops_service import MLOpsService

router = APIRouter(prefix="/mlops", tags=["24. MLOps Production Governance"])


# --- Drift Monitoring ---

@router.post("/drift/compute", response_model=ModelDriftReportResponse, status_code=status.HTTP_201_CREATED)
def compute_trusted_drift_metrics(
    req: DriftComputeRequest,
    worker_token: Annotated[str, Depends(require_worker_token)],
    db: Annotated[Session, Depends(get_db)],
):
    """Trusted monitoring service endpoint: computes PSI & KS drift from raw distributions."""
    report = MLOpsService.compute_and_record_drift(db, req)
    return ModelDriftReportResponse.model_validate(report)


@router.get("/drift", response_model=ModelDriftReportListResponse)
def list_drift_reports(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    model_id: Optional[int] = None,
    model_type: Optional[MLModelType] = None,
    severity: Optional[DriftSeverity] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """View model drift reports (Admin & Analyst only; Procurement Manager restricted)."""
    items, total = MLOpsService.list_drift_reports(
        db, model_id=model_id, model_type=model_type, severity=severity, page=page, page_size=page_size
    )
    return ModelDriftReportListResponse(
        items=[ModelDriftReportResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# --- Feature Freshness ---

@router.post("/feature-freshness/check", response_model=FeatureFreshnessResponse, status_code=status.HTTP_201_CREATED)
def record_feature_freshness_check(
    req: FeatureFreshnessCheckRequest,
    worker_token: Annotated[str, Depends(require_worker_token)],
    db: Annotated[Session, Depends(get_db)],
):
    """Trusted monitoring service endpoint: evaluates feature freshness against SLA."""
    metric = MLOpsService.check_feature_freshness(db, req)
    return FeatureFreshnessResponse.model_validate(metric)


@router.get("/feature-freshness", response_model=List[FeatureFreshnessResponse])
def list_feature_freshness(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    feature_group_name: Optional[str] = None,
    status_filter: Optional[FreshnessStatus] = Query(None, alias="status"),
):
    """View feature freshness monitoring metrics."""
    items = MLOpsService.list_feature_freshness(db, feature_group_name=feature_group_name, status=status_filter)
    return [FeatureFreshnessResponse.model_validate(i) for i in items]


# --- Shadow & Canary Deployments (Admin only) ---

@router.post("/deployments", response_model=ModelDeploymentResponse, status_code=status.HTTP_201_CREATED)
def create_model_deployment(
    req: ModelDeploymentCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a SHADOW (0% live impact) or CANARY deployment (Admin only)."""
    dep = MLOpsService.create_deployment(db, req, user_id=current_admin.id)
    return ModelDeploymentResponse.model_validate(dep)


@router.get("/deployments", response_model=List[ModelDeploymentResponse])
def list_model_deployments(
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    model_type: Optional[MLModelType] = None,
    deployment_mode: Optional[DeploymentMode] = None,
    status_filter: Optional[DeploymentStatus] = Query(None, alias="status"),
):
    """List shadow and canary model deployments (Admin only)."""
    items = MLOpsService.list_deployments(
        db, model_type=model_type, deployment_mode=deployment_mode, status=status_filter
    )
    return [ModelDeploymentResponse.model_validate(i) for i in items]


@router.patch("/deployments/{deployment_id}", response_model=ModelDeploymentResponse)
def update_model_deployment(
    deployment_id: int,
    req: ModelDeploymentUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Adjust canary traffic percentage or deployment status (Admin only)."""
    dep = MLOpsService.update_deployment(db, deployment_id, req, user_id=current_admin.id)
    return ModelDeploymentResponse.model_validate(dep)


@router.post("/deployments/{deployment_id}/shadow-predictions", response_model=ShadowPredictionLogResponse, status_code=status.HTTP_201_CREATED)
def record_shadow_prediction(
    deployment_id: int,
    req: ShadowPredictionLogRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Log an isolated shadow prediction without influencing live procurement decisions."""
    log = MLOpsService.record_shadow_prediction(db, deployment_id, req)
    return ShadowPredictionLogResponse.model_validate(log)


@router.get("/deployments/{deployment_id}/shadow-predictions", response_model=List[ShadowPredictionLogResponse])
def list_shadow_predictions(
    deployment_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Inspect shadow prediction logs vs champion predictions (Admin only)."""
    items = MLOpsService.list_shadow_logs(db, deployment_id)
    return [ShadowPredictionLogResponse.model_validate(i) for i in items]


# --- Promotion, Rollback & Lifecycle History ---

@router.post("/models/{model_id}/promote", response_model=MLModelResponse)
def promote_model_governed(
    model_id: int,
    req: ModelPromoteGovernanceRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Governed champion promotion with drift gate and lifecycle audit (Admin only)."""
    model = MLOpsService.promote_model_governed(db, model_id, req, user_id=current_admin.id)
    return MLModelResponse.model_validate(model)


@router.post("/models/{model_id}/rollback", response_model=MLModelResponse)
def rollback_model(
    model_id: int,
    req: ModelRollbackRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Roll back active champion/canary model to prior stable version (Admin only)."""
    model = MLOpsService.rollback_model(db, model_id, req, user_id=current_admin.id)
    return MLModelResponse.model_validate(model)


@router.get("/history", response_model=List[ModelLifecycleEventResponse])
def list_monitoring_history(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    model_id: Optional[int] = None,
    model_type: Optional[MLModelType] = None,
):
    """View immutable model promotion, deployment, and rollback history (Admin & Analyst)."""
    items = MLOpsService.list_lifecycle_history(db, model_id=model_id, model_type=model_type)
    return [ModelLifecycleEventResponse.model_validate(i) for i in items]


# --- Retraining Triggers (Admin only) ---

@router.put("/retraining-triggers", response_model=RetrainingTriggerConfigResponse)
def upsert_retraining_trigger(
    req: RetrainingTriggerConfigRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Configure automated retraining triggers for a model type (Admin only)."""
    cfg = MLOpsService.upsert_retraining_trigger(db, req, user_id=current_admin.id)
    return RetrainingTriggerConfigResponse.model_validate(cfg)


@router.get("/retraining-triggers", response_model=List[RetrainingTriggerConfigResponse])
def list_retraining_triggers(
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    model_type: Optional[MLModelType] = None,
):
    """List retraining trigger configurations (Admin only)."""
    items = MLOpsService.list_retraining_triggers(db, model_type=model_type)
    return [RetrainingTriggerConfigResponse.model_validate(i) for i in items]
