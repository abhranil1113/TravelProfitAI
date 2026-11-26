from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db, require_roles
from backend.app.models.schema import FXContractStatus, User, UserRole
from backend.app.schemas.treasury import (
    CurrencyExposureSnapshotResponse,
    FXAlertResponse,
    FXForwardCreateRequest,
    FXForwardExecuteRequest,
    FXForwardListResponse,
    FXForwardResponse,
    HedgeEffectivenessCreateRequest,
    HedgeEffectivenessResponse,
    MarginImpactEvaluateRequest,
    MarginImpactEvaluateResponse,
    MarginProtectionRuleCreateRequest,
    MarginProtectionRuleResponse,
    MarginProtectionRuleUpdateRequest,
)
from backend.app.services.treasury_service import TreasuryService

router = APIRouter(prefix="/treasury", tags=["26. Multi-Currency Treasury & FX Hedging"])


# --- FX Forward Contracts (Admin-only management & execution) ---

@router.post("/fx-contracts", response_model=FXForwardResponse, status_code=status.HTTP_201_CREATED)
def create_fx_forward_contract(
    req: FXForwardCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Draft an FX forward hedge contract (Admin only; requires separate execution)."""
    contract = TreasuryService.create_fx_forward(db, req, user_id=current_admin.id)
    return FXForwardResponse.model_validate(contract)


@router.get("/fx-contracts", response_model=FXForwardListResponse)
def list_fx_forward_contracts(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    base_currency: Optional[str] = None,
    status_filter: Optional[FXContractStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List FX forward contracts."""
    items, total = TreasuryService.list_fx_forwards(
        db, base_currency=base_currency, status=status_filter, page=page, page_size=page_size
    )
    return FXForwardListResponse(
        items=[FXForwardResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/fx-contracts/{contract_id}/execute", response_model=FXForwardResponse)
def execute_fx_forward_contract(
    contract_id: int,
    req: FXForwardExecuteRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Approve and execute a draft FX forward contract (Admin only; policy enforced)."""
    contract = TreasuryService.execute_fx_forward(db, contract_id, req, admin_user_id=current_admin.id)
    return FXForwardResponse.model_validate(contract)


@router.post("/fx-contracts/{contract_id}/settle", response_model=FXForwardResponse)
def settle_fx_forward_contract(
    contract_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Settle an active FX forward contract (Admin only)."""
    contract = TreasuryService.settle_fx_forward(db, contract_id, admin_user_id=current_admin.id)
    return FXForwardResponse.model_validate(contract)


@router.post("/fx-contracts/{contract_id}/cancel", response_model=FXForwardResponse)
def cancel_fx_forward_contract(
    contract_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Cancel a draft or active FX forward contract (Admin only)."""
    contract = TreasuryService.cancel_fx_forward(db, contract_id, admin_user_id=current_admin.id)
    return FXForwardResponse.model_validate(contract)


# --- Currency Exposure Monitoring ---

@router.post("/exposure/snapshot", response_model=CurrencyExposureSnapshotResponse, status_code=status.HTTP_201_CREATED)
def calculate_currency_exposure_snapshot(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    currency_code: str = Query(..., min_length=3, max_length=3),
    target_currency: str = Query("INR", min_length=3, max_length=3),
):
    """Calculate and record a real-time currency exposure snapshot (monitoring only)."""
    snap = TreasuryService.compute_currency_exposure(db, currency_code=currency_code, target_currency=target_currency)
    return CurrencyExposureSnapshotResponse.model_validate(snap)


@router.get("/exposure", response_model=List[CurrencyExposureSnapshotResponse])
def list_currency_exposure(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    currency_code: Optional[str] = None,
):
    """View currency exposure snapshots across all authenticated roles."""
    items = TreasuryService.list_exposure_snapshots(db, currency_code=currency_code)
    return [CurrencyExposureSnapshotResponse.model_validate(i) for i in items]


# --- Hedge Effectiveness ---

@router.post("/hedge-effectiveness", response_model=HedgeEffectivenessResponse, status_code=status.HTTP_201_CREATED)
def record_hedge_effectiveness(
    req: HedgeEffectivenessCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Measure IFRS 9 / IAS 39 dollar-offset hedge effectiveness (Admin only)."""
    rec = TreasuryService.record_hedge_effectiveness(db, req, user_id=current_admin.id)
    return HedgeEffectivenessResponse.model_validate(rec)


@router.get("/hedge-effectiveness", response_model=List[HedgeEffectivenessResponse])
def list_hedge_effectiveness(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    contract_id: Optional[int] = None,
):
    """List hedge effectiveness measurement records."""
    items = TreasuryService.list_hedge_effectiveness(db, contract_id=contract_id)
    return [HedgeEffectivenessResponse.model_validate(i) for i in items]


# --- Margin Protection Rules & Evaluation ---

@router.post("/margin-rules", response_model=MarginProtectionRuleResponse, status_code=status.HTTP_201_CREATED)
def create_margin_protection_rule(
    req: MarginProtectionRuleCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a margin protection threshold rule (Admin only)."""
    rule = TreasuryService.create_margin_rule(db, req, user_id=current_admin.id)
    return MarginProtectionRuleResponse.model_validate(rule)


@router.patch("/margin-rules/{rule_id}", response_model=MarginProtectionRuleResponse)
def update_margin_protection_rule(
    rule_id: int,
    req: MarginProtectionRuleUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update a margin protection rule (Admin only)."""
    rule = TreasuryService.update_margin_rule(db, rule_id, req, user_id=current_admin.id)
    return MarginProtectionRuleResponse.model_validate(rule)


@router.get("/margin-rules", response_model=List[MarginProtectionRuleResponse])
def list_margin_protection_rules(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    currency_code: Optional[str] = None,
):
    """List configured margin protection rules."""
    items = TreasuryService.list_margin_rules(db, currency_code=currency_code)
    return [MarginProtectionRuleResponse.model_validate(i) for i in items]


@router.post("/margin-impact/evaluate", response_model=MarginImpactEvaluateResponse)
def evaluate_procurement_margin_impact(
    req: MarginImpactEvaluateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Evaluate FX margin impact and check margin protection rules (Admin & Procurement Manager)."""
    return TreasuryService.evaluate_margin_impact(db, req, user_id=current_user.id)


# --- FX Alerts ---

@router.get("/alerts", response_model=List[FXAlertResponse])
def list_fx_alerts(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    currency_code: Optional[str] = None,
    is_acknowledged: Optional[bool] = None,
):
    """List treasury FX and margin erosion alerts."""
    items = TreasuryService.list_fx_alerts(db, currency_code=currency_code, is_acknowledged=is_acknowledged)
    return [FXAlertResponse.model_validate(i) for i in items]


@router.post("/alerts/{alert_id}/acknowledge", response_model=FXAlertResponse)
def acknowledge_fx_alert(
    alert_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Acknowledge an FX alert."""
    alert = TreasuryService.acknowledge_fx_alert(db, alert_id, user_id=current_user.id)
    return FXAlertResponse.model_validate(alert)
