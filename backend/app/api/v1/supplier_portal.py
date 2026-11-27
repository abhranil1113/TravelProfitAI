from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.exceptions import PermissionDeniedError
from backend.app.dependencies import (
    get_authenticated_supplier,
    get_db,
    get_idempotency_key,
    require_roles,
)
from backend.app.models.schema import RateSyncStatus, SupplierApiCredential, User, UserRole
from backend.app.schemas.supplier_portal import (
    SettlementNettingCreateRequest,
    SettlementNettingResponse,
    SupplierCredentialCreateRequest,
    SupplierCredentialCreateResponse,
    SupplierCredentialResponse,
    SupplierOnboardingAdvanceRequest,
    SupplierOnboardingCreateRequest,
    SupplierOnboardingResponse,
    SupplierRatePushRequest,
    SupplierRateSyncLogListResponse,
    SupplierRateSyncLogResponse,
    SupplierTierUpdateRequest,
    SupplierVerificationProfileResponse,
)
from backend.app.services.supplier_portal_service import SupplierPortalService

router = APIRouter(prefix="/supplier-portal", tags=["25. Supplier Collaboration & Connectivity Hub"])


# --- Supplier API Credentials (Admin only) ---

@router.post("/credentials", response_model=SupplierCredentialCreateResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_credential(
    req: SupplierCredentialCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create machine-to-machine API credential for a supplier (Admin only; raw secret returned once)."""
    return SupplierPortalService.create_credential(db, req, user_id=current_admin.id)


@router.get("/credentials", response_model=List[SupplierCredentialResponse])
def list_supplier_credentials(
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: Optional[str] = None,
):
    """List supplier API credentials without ever exposing raw secrets (Admin only)."""
    items = SupplierPortalService.list_credentials(db, supplier_id=supplier_id)
    return [SupplierCredentialResponse.model_validate(i) for i in items]


@router.post("/credentials/{credential_id}/rotate", response_model=SupplierCredentialCreateResponse)
def rotate_supplier_credential(
    credential_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Atomically rotate a supplier API credential and revoke the prior key (Admin only)."""
    return SupplierPortalService.rotate_credential(db, credential_id, user_id=current_admin.id)


@router.post("/credentials/{credential_id}/revoke", response_model=SupplierCredentialResponse)
def revoke_supplier_credential(
    credential_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Revoke an active supplier API credential (Admin only)."""
    cred = SupplierPortalService.revoke_credential(db, credential_id, user_id=current_admin.id)
    return SupplierCredentialResponse.model_validate(cred)


# --- Machine-to-Machine Supplier Rate & Availability Push ---

@router.post("/rates/push", response_model=SupplierRateSyncLogResponse, status_code=status.HTTP_201_CREATED)
def push_supplier_rates_and_availability(
    req: SupplierRatePushRequest,
    supplier_cred: Annotated[SupplierApiCredential, Depends(get_authenticated_supplier)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[Optional[str], Depends(get_idempotency_key)] = None,
):
    """
    Supplier machine-authenticated idempotent rate & availability push.
    Enforces strict supplier-level isolation via X-Supplier-Key credential.
    """
    log = SupplierPortalService.push_rates_and_availability(
        db, credential=supplier_cred, req=req, header_idempotency_key=idempotency_key
    )
    return SupplierRateSyncLogResponse.model_validate(log)


@router.get("/me/sync-logs", response_model=SupplierRateSyncLogListResponse)
def get_own_supplier_sync_logs(
    supplier_cred: Annotated[SupplierApiCredential, Depends(get_authenticated_supplier)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Machine-authenticated supplier view of its own synchronization logs (isolated by supplier_id)."""
    scopes = set(supplier_cred.scopes_json or [])
    if "sync:read" not in scopes:
        raise PermissionDeniedError("Credential lacks 'sync:read' scope.")
    items, total = SupplierPortalService.list_sync_logs(
        db, supplier_id=supplier_cred.supplier_id, page=page, page_size=page_size
    )
    return SupplierRateSyncLogListResponse(
        items=[SupplierRateSyncLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# --- Human-Role Sync Logs View (Admin & PM) ---

@router.get("/sync-logs", response_model=SupplierRateSyncLogListResponse)
def list_supplier_sync_logs(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: Optional[str] = None,
    status_filter: Optional[RateSyncStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """View supplier synchronization logs (Admin & Procurement Manager)."""
    items, total = SupplierPortalService.list_sync_logs(
        db, supplier_id=supplier_id, status=status_filter, page=page, page_size=page_size
    )
    return SupplierRateSyncLogListResponse(
        items=[SupplierRateSyncLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# --- Supplier Tier & Verification Management ---

@router.put("/suppliers/{supplier_id}/tier-verification", response_model=SupplierVerificationProfileResponse)
def update_supplier_tier_verification(
    supplier_id: str,
    req: SupplierTierUpdateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Manage supplier tier and verification status (Admin only)."""
    prof = SupplierPortalService.get_or_update_tier_profile(db, supplier_id, req, user_id=current_admin.id)
    return SupplierVerificationProfileResponse.model_validate(prof)


@router.get("/suppliers/{supplier_id}/tier-verification", response_model=SupplierVerificationProfileResponse)
def get_supplier_tier_verification(
    supplier_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get supplier tier and verification profile."""
    prof = SupplierPortalService.get_tier_profile(db, supplier_id)
    return SupplierVerificationProfileResponse.model_validate(prof)


# --- Supplier Onboarding Workflows (Admin only) ---

@router.post("/onboarding", response_model=SupplierOnboardingResponse, status_code=status.HTTP_201_CREATED)
def initiate_supplier_onboarding(
    req: SupplierOnboardingCreateRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Initiate a supplier onboarding workflow (Admin only)."""
    wf = SupplierPortalService.create_onboarding(db, req, user_id=current_admin.id)
    return SupplierOnboardingResponse.model_validate(wf)


@router.get("/onboarding", response_model=List[SupplierOnboardingResponse])
def list_supplier_onboardings(
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: Optional[str] = None,
):
    """List supplier onboarding workflows (Admin only)."""
    items = SupplierPortalService.list_onboardings(db, supplier_id=supplier_id)
    return [SupplierOnboardingResponse.model_validate(i) for i in items]


@router.post("/onboarding/{onboarding_id}/advance", response_model=SupplierOnboardingResponse)
def advance_supplier_onboarding(
    onboarding_id: int,
    req: SupplierOnboardingAdvanceRequest,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Advance or reject a supplier onboarding stage (Admin only)."""
    wf = SupplierPortalService.advance_onboarding(db, onboarding_id, req, user_id=current_admin.id)
    return SupplierOnboardingResponse.model_validate(wf)


# --- Settlement Netting Batches (Admin & PM) ---

@router.post("/settlement-netting", response_model=SettlementNettingResponse, status_code=status.HTTP_201_CREATED)
def create_settlement_netting_batch(
    req: SettlementNettingCreateRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Calculate and create a supplier settlement netting batch (Admin & Procurement Manager)."""
    batch = SupplierPortalService.create_netting_batch(db, req, user_id=current_user.id)
    return SettlementNettingResponse.model_validate(batch)


@router.get("/settlement-netting", response_model=List[SettlementNettingResponse])
def list_settlement_netting_batches(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: Optional[str] = None,
):
    """List supplier settlement netting batches (Admin & Procurement Manager)."""
    items = SupplierPortalService.list_netting_batches(db, supplier_id=supplier_id)
    return [SettlementNettingResponse.model_validate(i) for i in items]


@router.post("/settlement-netting/{batch_id}/approve", response_model=SettlementNettingResponse)
def approve_settlement_netting_batch(
    batch_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Approve a calculated settlement netting batch (Admin & Procurement Manager)."""
    batch = SupplierPortalService.approve_netting_batch(db, batch_id, user_id=current_user.id)
    return SettlementNettingResponse.model_validate(batch)


@router.post("/settlement-netting/{batch_id}/settle", response_model=SettlementNettingResponse)
def settle_settlement_netting_batch(
    batch_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.PROCUREMENT_MANAGER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Mark an approved settlement netting batch as SETTLED (Admin & Procurement Manager)."""
    batch = SupplierPortalService.settle_netting_batch(db, batch_id, user_id=current_user.id)
    return SettlementNettingResponse.model_validate(batch)
