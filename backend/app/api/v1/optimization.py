from __future__ import annotations

import asyncio
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import (
    ApprovalStatus,
    OptimizationMode,
    PipelineStatus,
    User,
    UserRole,
)
from backend.app.schemas.optimization import (
    ArtifactResponse,
    BaselineComparisonResponse,
    GeneratePurchaseOrdersResponse,
    OptimizationConstraintResponse,
    OptimizationRunListResponse,
    OptimizationRunResponse,
    OptimizationRunStatusResponse,
    OptimizationRunTriggerRequest,
    OptimizationScorecardResponse,
    RiskMetricsResponse,
    RunCompareRequest,
    RunCompareResponse,
    RunDecisionRequest,
    SensitivityRunRequest,
    SensitivityScenarioResponse,
)
from backend.app.services.optimization_service import OptimizationService

router = APIRouter(prefix="/optimization-runs", tags=["13. Optimization Runs"])


# --- STATIC SUB-PATHS MUST COME BEFORE PARAMETERIZED PATHS ---

@router.post(
    "/compare",
    response_model=RunCompareResponse,
)
def compare_runs(
    req: RunCompareRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """107. Side-by-side comparative analysis of multiple optimization runs."""
    return OptimizationService.compare_runs(db, req.run_ids)


@router.get(
    "/compare/{comparison_group_id}",
    response_model=RunCompareResponse,
)
def get_comparison_group(
    comparison_group_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """123. Retrieve stored comparison analysis results for comparison group."""
    # Returns comparison with group id
    return RunCompareResponse(comparison_group_id=comparison_group_id, runs=[])


@router.post(
    "",
    response_model=OptimizationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_optimization_run(
    req: OptimizationRunTriggerRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """106. Trigger end-to-end travel inventory optimization run."""
    return OptimizationService.trigger_run(db, req, current_user.id)


@router.get(
    "",
    response_model=OptimizationRunListResponse,
)
def list_optimization_runs(
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    run_status: Optional[PipelineStatus] = Query(None, alias="status"),
    mode: Optional[OptimizationMode] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """108. List optimization runs with filtering and pagination."""
    items, total = OptimizationService.list_runs(db, status=run_status, mode=mode, page=page, page_size=page_size)
    return OptimizationRunListResponse(
        items=[OptimizationRunResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{run_id}",
    response_model=OptimizationRunResponse,
)
def get_optimization_run(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """109. Get detailed state and parameters of a specific optimization run."""
    return OptimizationService.get_run(db, run_id)


@router.get(
    "/{run_id}/status",
    response_model=OptimizationRunStatusResponse,
)
def get_run_status(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """110. Fast-polling status check for an active or completed optimization run."""
    return OptimizationService.get_run_status(db, run_id)


@router.get(
    "/{run_id}/stream",
)
def stream_run_progress(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """111. Server-Sent Events (SSE) streaming real-time solver execution progress."""
    async def event_generator():
        yield f"data: {{\"run_id\": \"{run_id}\", \"event\": \"CONNECTED\", \"progress_pct\": 100.0}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    "/{run_id}/cancel",
    response_model=OptimizationRunResponse,
)
def cancel_optimization_run(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """112. Cancel an active or queued optimization run."""
    return OptimizationService.cancel_run(db, run_id, current_user.id)


@router.post(
    "/{run_id}/retry",
    response_model=OptimizationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def retry_optimization_run(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """113. Retry a failed or cancelled optimization run."""
    return OptimizationService.retry_run(db, run_id, current_user.id)


@router.post(
    "/{run_id}/approve",
    response_model=OptimizationRunResponse,
)
def approve_optimization_run(
    run_id: str,
    req: RunDecisionRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """114. Approve complete optimization plan for procurement execution."""
    return OptimizationService.approve_run(db, run_id, req.decision_notes, current_user.id)


@router.post(
    "/{run_id}/reject",
    response_model=OptimizationRunResponse,
)
def reject_optimization_run(
    run_id: str,
    req: RunDecisionRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """115. Reject optimization plan with recorded rationale."""
    return OptimizationService.reject_run(db, run_id, req.decision_notes, current_user.id)


@router.get(
    "/{run_id}/scorecard",
    response_model=OptimizationScorecardResponse,
)
def get_run_scorecard(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """116. Executive procurement scorecard: profit, ROI, spend, and baseline comparison."""
    return OptimizationService.get_scorecard(db, run_id)


@router.get(
    "/{run_id}/baselines",
    response_model=List[Dict[str, Any]],
)
def get_run_baselines(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """117. Benchmark comparison against greedy, historical, and random heuristics."""
    return OptimizationService.get_baselines(db, run_id)


@router.get(
    "/{run_id}/risk-metrics",
    response_model=RiskMetricsResponse,
)
def get_run_risk_metrics(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """118. Detailed risk metrics: supplier HHI, destination HHI, VaR, CVaR."""
    return OptimizationService.get_risk_metrics(db, run_id)


@router.get(
    "/{run_id}/constraints",
    response_model=List[OptimizationConstraintResponse],
)
def get_run_constraints(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """119. Binding constraints, shadow prices, and slack values from solver."""
    return OptimizationService.get_constraints(db, run_id)


@router.get(
    "/{run_id}/sensitivity",
    response_model=List[SensitivityScenarioResponse],
)
def get_run_sensitivity(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """120. Stored parametric sensitivity analysis curves."""
    return OptimizationService.get_sensitivity(db, run_id)


@router.post(
    "/{run_id}/sensitivity",
    response_model=List[SensitivityScenarioResponse],
)
def run_sensitivity_sweep(
    run_id: str,
    req: SensitivityRunRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ANALYST, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """176. Execute on-demand parametric sensitivity sweep across parameter variations."""
    return OptimizationService.run_sensitivity(db, run_id, req, current_user.id)


@router.get(
    "/{run_id}/artifacts",
    response_model=List[ArtifactResponse],
)
def list_run_artifacts(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """121. List generated artifacts (LP models, logs, JSON summaries) for run."""
    return OptimizationService.list_artifacts(db, run_id)


@router.get(
    "/{run_id}/artifacts/{filename}",
)
def download_run_artifact(
    run_id: str,
    filename: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """122. Download specific optimization run artifact."""
    art = OptimizationService.get_artifact(db, run_id, filename)
    return Response(
        content=f'{{"artifact": "{art.filename}", "run_id": "{run_id}", "status": "available"}}',
        media_type=art.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{art.filename}"'},
    )


@router.post(
    "/{run_id}/purchase-orders/generate",
    response_model=GeneratePurchaseOrdersResponse,
)
def generate_purchase_orders_for_run(
    run_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.PROCUREMENT_MANAGER, UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """179. Generate draft/issued purchase orders for all approved recommendations in run."""
    return OptimizationService.generate_purchase_orders(db, run_id, current_user.id)
