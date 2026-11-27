from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
from collections import deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Deque, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.exceptions import (
    AppBaseException,
    AuthenticationError,
    BadRequestException,
    ConflictException,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PermissionDeniedError,
)
from backend.app.core.security import hash_token
from backend.app.models.schema import (
    AuditLog,
    Destination,
    ExchangeRate,
    InventoryItem,
    InventorySnapshot,
    OfferStatus,
    POStatus,
    PurchaseOrder,
    PurchaseOrderFulfillment,
    PurchaseOrderLine,
    RateSyncStatus,
    SettlementBatchStatus,
    SettlementNettingBatch,
    Supplier,
    SupplierApiCredential,
    SupplierCredentialStatus,
    SupplierOffer,
    SupplierOnboardingWorkflow,
    SupplierRateSyncLog,
    SupplierTier,
    SupplierVerificationProfile,
    SupplierVerificationStatus,
    OnboardingStage,
)
from backend.app.schemas.supplier_portal import (
    SettlementNettingCreateRequest,
    SupplierCredentialCreateRequest,
    SupplierCredentialCreateResponse,
    SupplierOnboardingAdvanceRequest,
    SupplierOnboardingCreateRequest,
    SupplierRatePushRequest,
    SupplierTierUpdateRequest,
)

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SupplierPortalService:
    """Service layer for Domain 3: Supplier Collaboration & Connectivity Hub."""

    # In-memory sliding-window rate limiter per credential_id (60s window)
    _RATE_LIMIT_LOCK = threading.Lock()
    _RATE_LIMIT_WINDOWS: Dict[int, Deque[float]] = {}

    @classmethod
    def reset_rate_limits(cls) -> None:
        """Clears rate limit windows (useful in isolated tests)."""
        with cls._RATE_LIMIT_LOCK:
            cls._RATE_LIMIT_WINDOWS.clear()

    @classmethod
    def _enforce_rate_limit(cls, credential: SupplierApiCredential) -> None:
        now_ts = time.monotonic()
        cutoff = now_ts - 60.0
        with cls._RATE_LIMIT_LOCK:
            dq = cls._RATE_LIMIT_WINDOWS.setdefault(credential.id, deque())
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= credential.rate_limit_per_minute:
                raise AppBaseException(
                    status_code=429,
                    detail=f"Rate limit exceeded ({credential.rate_limit_per_minute} requests/minute) for credential {credential.credential_uid}.",
                    error_code="RATE_LIMIT_EXCEEDED",
                )
            dq.append(now_ts)

    @classmethod
    def authenticate_machine_credential(
        cls, db: Session, raw_api_key: Optional[str]
    ) -> SupplierApiCredential:
        """
        Authenticates a machine-to-machine supplier API credential separately from human JWTs.
        Enforces active status, expiration, supplier active check, and sliding-window rate limiting.
        """
        if not raw_api_key or not raw_api_key.strip():
            raise AuthenticationError("Supplier API key header (X-Supplier-Key) is missing.")

        key_hash = hash_token(raw_api_key.strip())
        cred = db.execute(
            select(SupplierApiCredential).where(SupplierApiCredential.secret_hash == key_hash)
        ).scalar_one_or_none()
        if not cred:
            raise AuthenticationError("Invalid supplier API credential.")

        if cred.status != SupplierCredentialStatus.ACTIVE or cred.revoked_at is not None:
            raise AuthenticationError(f"Supplier API credential is {cred.status.value}.")

        now = datetime.now(timezone.utc)
        if cred.expires_at and _ensure_utc(cred.expires_at) <= now:
            cred.status = SupplierCredentialStatus.EXPIRED
            db.commit()
            raise AuthenticationError("Supplier API credential has expired.")

        supplier = db.execute(
            select(Supplier).where(Supplier.supplier_id == cred.supplier_id)
        ).scalar_one_or_none()
        if not supplier or not supplier.is_active:
            raise PermissionDeniedError(f"Supplier '{cred.supplier_id}' is inactive or suspended.")

        cls._enforce_rate_limit(cred)
        cred.last_used_at = now
        db.commit()
        return cred

    # --- Credential Management (Admin only) ---

    @staticmethod
    def create_credential(
        db: Session, req: SupplierCredentialCreateRequest, user_id: int
    ) -> SupplierCredentialCreateResponse:
        supplier = db.execute(
            select(Supplier).where(Supplier.supplier_id == req.supplier_id)
        ).scalar_one_or_none()
        if not supplier:
            raise EntityNotFoundError("Supplier", req.supplier_id)

        raw_secret = f"tbo_sup_{secrets.token_urlsafe(32)}"
        prefix = raw_secret[:14]
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)
            if req.expires_in_days
            else None
        )

        cred = SupplierApiCredential(
            supplier_id=supplier.supplier_id,
            key_prefix=prefix,
            secret_hash=hash_token(raw_secret),
            label=req.label.strip(),
            scopes_json=req.scopes,
            status=SupplierCredentialStatus.ACTIVE,
            rate_limit_per_minute=req.rate_limit_per_minute,
            expires_at=expires_at,
            created_by_user_id=user_id,
        )
        db.add(cred)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_CREDENTIAL_CREATED",
            entity_type="supplier_api_credentials",
            entity_id=cred.credential_uid,
            new_value_json={"supplier_id": cred.supplier_id, "key_prefix": prefix, "scopes": req.scopes},
        ))
        db.commit()
        db.refresh(cred)

        return SupplierCredentialCreateResponse(
            id=cred.id,
            credential_uid=cred.credential_uid,
            supplier_id=cred.supplier_id,
            key_prefix=cred.key_prefix,
            label=cred.label,
            scopes=cred.scopes_json,
            status=cred.status,
            rate_limit_per_minute=cred.rate_limit_per_minute,
            expires_at=cred.expires_at,
            created_at=cred.created_at,
            raw_api_secret=raw_secret,
        )

    @staticmethod
    def rotate_credential(
        db: Session, credential_id: int, user_id: int
    ) -> SupplierCredentialCreateResponse:
        old_cred = db.execute(
            select(SupplierApiCredential).where(SupplierApiCredential.id == credential_id).with_for_update()
        ).scalar_one_or_none()
        if not old_cred:
            raise EntityNotFoundError("SupplierApiCredential", credential_id)
        if old_cred.status != SupplierCredentialStatus.ACTIVE:
            raise InvalidStateTransitionError(old_cred.status.value, SupplierCredentialStatus.ROTATED.value)

        now = datetime.now(timezone.utc)
        old_cred.status = SupplierCredentialStatus.ROTATED
        old_cred.revoked_at = now

        raw_secret = f"tbo_sup_{secrets.token_urlsafe(32)}"
        prefix = raw_secret[:14]
        new_cred = SupplierApiCredential(
            supplier_id=old_cred.supplier_id,
            key_prefix=prefix,
            secret_hash=hash_token(raw_secret),
            label=f"{old_cred.label} (Rotated)",
            scopes_json=list(old_cred.scopes_json or []),
            status=SupplierCredentialStatus.ACTIVE,
            rate_limit_per_minute=old_cred.rate_limit_per_minute,
            expires_at=now + timedelta(days=90),
            rotated_from_id=old_cred.id,
            created_by_user_id=user_id,
        )
        db.add(new_cred)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_CREDENTIAL_ROTATED",
            entity_type="supplier_api_credentials",
            entity_id=new_cred.credential_uid,
            old_value_json={"old_credential_uid": old_cred.credential_uid},
            new_value_json={"new_credential_uid": new_cred.credential_uid, "key_prefix": prefix},
        ))
        db.commit()
        db.refresh(new_cred)

        return SupplierCredentialCreateResponse(
            id=new_cred.id,
            credential_uid=new_cred.credential_uid,
            supplier_id=new_cred.supplier_id,
            key_prefix=new_cred.key_prefix,
            label=new_cred.label,
            scopes=new_cred.scopes_json,
            status=new_cred.status,
            rate_limit_per_minute=new_cred.rate_limit_per_minute,
            expires_at=new_cred.expires_at,
            created_at=new_cred.created_at,
            raw_api_secret=raw_secret,
        )

    @staticmethod
    def revoke_credential(
        db: Session, credential_id: int, user_id: int
    ) -> SupplierApiCredential:
        cred = db.execute(
            select(SupplierApiCredential).where(SupplierApiCredential.id == credential_id).with_for_update()
        ).scalar_one_or_none()
        if not cred:
            raise EntityNotFoundError("SupplierApiCredential", credential_id)
        if cred.status == SupplierCredentialStatus.REVOKED:
            return cred
        cred.status = SupplierCredentialStatus.REVOKED
        cred.revoked_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_CREDENTIAL_REVOKED",
            entity_type="supplier_api_credentials",
            entity_id=cred.credential_uid,
        ))
        db.commit()
        db.refresh(cred)
        return cred

    @staticmethod
    def list_credentials(
        db: Session, supplier_id: Optional[str] = None
    ) -> List[SupplierApiCredential]:
        stmt = select(SupplierApiCredential)
        if supplier_id:
            stmt = stmt.where(SupplierApiCredential.supplier_id == supplier_id.upper())
        return list(db.execute(stmt.order_by(SupplierApiCredential.created_at.desc())).scalars().all())

    # --- Rate & Availability Push (Machine Auth + Idempotent) ---

    @staticmethod
    def _resolve_fx_rate_to_inr(db: Session, currency_code: str) -> Tuple[Decimal, Optional[int]]:
        ccy = currency_code.upper()
        if ccy == "INR":
            return Decimal("1.0"), None
        rate_row = db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.from_currency == ccy, ExchangeRate.to_currency == "INR")
            .order_by(ExchangeRate.as_of_date.desc())
        ).scalars().first()
        if not rate_row:
            raise BadRequestException(f"No verified exchange rate available for {ccy}/INR.")
        return rate_row.rate, rate_row.id

    @staticmethod
    def push_rates_and_availability(
        db: Session,
        credential: SupplierApiCredential,
        req: SupplierRatePushRequest,
        header_idempotency_key: Optional[str] = None,
    ) -> SupplierRateSyncLog:
        scopes = set(credential.scopes_json or [])
        if "rates:write" not in scopes and "availability:write" not in scopes:
            raise PermissionDeniedError("Credential lacks 'rates:write' or 'availability:write' scope.")

        canonical_payload = json.dumps(
            [o.model_dump(mode="json") for o in req.offers],
            sort_keys=True,
        )
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        idem_key = (header_idempotency_key or req.idempotency_key or f"auto_{payload_hash[:24]}").strip()

        # Serialize concurrent pushes per supplier to guarantee idempotent replay under READ COMMITTED
        db.execute(
            select(Supplier.supplier_id)
            .where(Supplier.supplier_id == credential.supplier_id)
            .with_for_update()
        ).scalar_one_or_none()

        existing_sync = db.execute(
            select(SupplierRateSyncLog).where(
                SupplierRateSyncLog.supplier_id == credential.supplier_id,
                SupplierRateSyncLog.idempotency_key == idem_key,
            )
        ).scalar_one_or_none()

        if existing_sync:
            if existing_sync.payload_hash != payload_hash:
                raise ConflictException(
                    f"Idempotency key '{idem_key}' was already used for a different payload."
                )
            return existing_sync

        upserted = 0
        snaps_updated = 0
        rejected = 0
        errors: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for item in req.offers:
            try:
                with db.begin_nested():
                    dest = db.execute(
                        select(Destination).where(Destination.dest_id == item.dest_id)
                    ).scalar_one_or_none()
                    if not dest:
                        raise BadRequestException(f"Destination '{item.dest_id}' does not exist.")

                    fx_rate, fx_id = SupplierPortalService._resolve_fx_rate_to_inr(db, item.currency_code)
                    cost_inr = (item.unit_cost * fx_rate).quantize(Decimal("0.01"))
                    list_inr = (item.list_price * fx_rate).quantize(Decimal("0.01"))

                    inv_item: Optional[InventoryItem] = None
                    if item.inventory_id:
                        inv_item = db.execute(
                            select(InventoryItem).where(InventoryItem.inventory_id == item.inventory_id)
                        ).scalar_one_or_none()
                        if not inv_item:
                            raise BadRequestException(f"InventoryItem '{item.inventory_id}' not found.")
                        if inv_item.dest_id != item.dest_id:
                            raise BadRequestException(
                                f"InventoryItem '{item.inventory_id}' destination '{inv_item.dest_id}' "
                                f"does not match offer dest_id '{item.dest_id}'."
                            )

                    existing_offer = db.execute(
                        select(SupplierOffer).where(SupplierOffer.offer_id == item.offer_id)
                    ).scalar_one_or_none()

                    has_rates_write = "rates:write" in scopes
                    has_avail_write = "availability:write" in scopes

                    if existing_offer:
                        if existing_offer.supplier_id != credential.supplier_id:
                            raise PermissionDeniedError(
                                f"Offer '{item.offer_id}' belongs to another supplier; cross-supplier mutation forbidden."
                            )

                        existing_orig_cost = (
                            existing_offer.original_unit_cost
                            if existing_offer.original_unit_cost is not None
                            else existing_offer.unit_cost_inr
                        )
                        existing_orig_list = (
                            existing_offer.original_list_price
                            if existing_offer.original_list_price is not None
                            else existing_offer.list_price_inr
                        )
                        rate_fields_changed = (
                            item.unit_cost != existing_orig_cost
                            or item.list_price != existing_orig_list
                            or item.currency_code != existing_offer.currency_code
                            or item.moq != existing_offer.moq
                            or item.valid_from != existing_offer.valid_from
                            or item.valid_until != existing_offer.valid_until
                            or item.travel_date != existing_offer.travel_date
                            or (
                                item.external_offer_reference is not None
                                and item.external_offer_reference != existing_offer.external_offer_reference
                            )
                        )
                        capacity_changed = item.max_capacity != existing_offer.max_capacity
                        avail_mutation_requested = (item.available_units is not None) or capacity_changed

                        if rate_fields_changed and not has_rates_write:
                            raise PermissionDeniedError(
                                "Credential lacks 'rates:write' scope to modify offer rates or terms."
                            )
                        if avail_mutation_requested and not has_avail_write:
                            raise PermissionDeniedError(
                                "Credential lacks 'availability:write' scope to modify availability or capacity."
                            )
                        if not has_rates_write and not avail_mutation_requested:
                            raise PermissionDeniedError(
                                "Credential lacks 'rates:write' scope and no availability changes were provided."
                            )

                        if has_rates_write:
                            existing_offer.unit_cost_inr = cost_inr
                            existing_offer.list_price_inr = list_inr
                            existing_offer.original_unit_cost = item.unit_cost
                            existing_offer.original_list_price = item.list_price
                            existing_offer.currency_code = item.currency_code
                            existing_offer.exchange_rate_id = fx_id
                            existing_offer.moq = item.moq
                            existing_offer.valid_from = item.valid_from
                            existing_offer.valid_until = item.valid_until
                            existing_offer.travel_date = item.travel_date
                            existing_offer.status = OfferStatus.ACTIVE
                            if item.external_offer_reference:
                                existing_offer.external_offer_reference = item.external_offer_reference
                        if has_avail_write and capacity_changed:
                            existing_offer.max_capacity = item.max_capacity
                    else:
                        if not has_rates_write:
                            raise PermissionDeniedError(
                                "Credential lacks 'rates:write' scope to create new offers."
                            )
                        if item.available_units is not None and not has_avail_write:
                            raise PermissionDeniedError(
                                "Credential lacks 'availability:write' scope to publish availability snapshots."
                            )
                        new_offer = SupplierOffer(
                            offer_id=item.offer_id,
                            supplier_id=credential.supplier_id,
                            inventory_id=item.inventory_id,
                            dest_id=item.dest_id,
                            origin_dest_id=item.origin_dest_id.upper() if item.origin_dest_id else None,
                            inventory_category=item.inventory_category,
                            unit_type=item.unit_type,
                            unit_cost_inr=cost_inr,
                            list_price_inr=list_inr,
                            original_unit_cost=item.unit_cost,
                            original_list_price=item.list_price,
                            currency_code=item.currency_code,
                            exchange_rate_id=fx_id,
                            external_offer_reference=item.external_offer_reference,
                            moq=item.moq,
                            max_capacity=item.max_capacity,
                            valid_from=item.valid_from,
                            valid_until=item.valid_until,
                            travel_date=item.travel_date,
                            status=OfferStatus.ACTIVE,
                        )
                        db.add(new_offer)

                    if inv_item and item.available_units is not None:
                        if not has_avail_write:
                            raise PermissionDeniedError(
                                "Credential lacks 'availability:write' scope to update availability."
                            )
                        avail = min(item.available_units, item.max_capacity)
                        booked = max(0, item.max_capacity - avail)
                        snap = InventorySnapshot(
                            inventory_id=inv_item.inventory_id,
                            supplier_id=credential.supplier_id,
                            inventory_category=item.inventory_category,
                            travel_date=item.travel_date,
                            snapshot_at=now,
                            total_units=avail + booked,
                            available_units=avail,
                            booked_units=booked,
                        )
                        db.add(snap)
                        snaps_updated += 1

                    db.flush()
                upserted += 1
            except Exception as exc:
                rejected += 1
                errors.append({"offer_id": item.offer_id, "error": str(exc)})

        if upserted == 0 and rejected > 0:
            sync_status = RateSyncStatus.FAILED
        elif rejected > 0:
            sync_status = RateSyncStatus.PARTIAL
        else:
            sync_status = RateSyncStatus.SUCCESS

        sync_log = SupplierRateSyncLog(
            supplier_id=credential.supplier_id,
            credential_id=credential.id,
            idempotency_key=idem_key,
            payload_hash=payload_hash,
            status=sync_status,
            offers_received=len(req.offers),
            offers_upserted=upserted,
            snapshots_updated=snaps_updated,
            offers_rejected=rejected,
            error_details_json=errors,
            synced_at=now,
        )
        db.add(sync_log)
        db.add(AuditLog(
            user_id=None,
            action="SUPPLIER_RATE_PUSH",
            entity_type="supplier_rate_sync_logs",
            entity_id=credential.supplier_id,
            new_value_json={
                "credential_uid": credential.credential_uid,
                "status": sync_status.value,
                "upserted": upserted,
                "rejected": rejected,
            },
        ))
        db.commit()
        db.refresh(sync_log)
        return sync_log

    @staticmethod
    def list_sync_logs(
        db: Session,
        supplier_id: Optional[str] = None,
        status: Optional[RateSyncStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[SupplierRateSyncLog], int]:
        stmt = select(SupplierRateSyncLog)
        if supplier_id:
            stmt = stmt.where(SupplierRateSyncLog.supplier_id == supplier_id.upper())
        if status:
            stmt = stmt.where(SupplierRateSyncLog.status == status)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(
            db.execute(
                stmt.order_by(SupplierRateSyncLog.synced_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
        )
        return items, total

    # --- Supplier Tiers & Verification (Admin only) ---

    @staticmethod
    def get_or_update_tier_profile(
        db: Session, supplier_id: str, req: SupplierTierUpdateRequest, user_id: int
    ) -> SupplierVerificationProfile:
        sid = supplier_id.upper()
        supplier = db.execute(select(Supplier).where(Supplier.supplier_id == sid)).scalar_one_or_none()
        if not supplier:
            raise EntityNotFoundError("Supplier", supplier_id)

        profile = db.execute(
            select(SupplierVerificationProfile).where(SupplierVerificationProfile.supplier_id == sid)
        ).scalar_one_or_none()
        if not profile:
            profile = SupplierVerificationProfile(supplier_id=sid)
            db.add(profile)
            db.flush()

        if req.tier is not None:
            profile.tier = req.tier
        if req.verification_status is not None:
            profile.verification_status = req.verification_status
            if req.verification_status == SupplierVerificationStatus.VERIFIED:
                profile.verified_at = datetime.now(timezone.utc)
                profile.verified_by_user_id = user_id
        if req.risk_score is not None:
            profile.risk_score = req.risk_score
        if req.sla_response_hours is not None:
            profile.sla_response_hours = req.sla_response_hours
        if req.notes is not None:
            profile.notes = req.notes

        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_TIER_VERIFICATION_UPDATED",
            entity_type="supplier_verification_profiles",
            entity_id=sid,
            new_value_json={
                "tier": profile.tier.value,
                "verification_status": profile.verification_status.value,
            },
        ))
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def get_tier_profile(db: Session, supplier_id: str) -> SupplierVerificationProfile:
        sid = supplier_id.upper()
        profile = db.execute(
            select(SupplierVerificationProfile).where(SupplierVerificationProfile.supplier_id == sid)
        ).scalar_one_or_none()
        if not profile:
            raise EntityNotFoundError("SupplierVerificationProfile", sid)
        return profile

    # --- Supplier Onboarding Workflows (Admin only) ---

    _VALID_ONBOARDING_TRANSITIONS: Dict[OnboardingStage, set[OnboardingStage]] = {
        OnboardingStage.INITIATED: {OnboardingStage.DOCUMENT_REVIEW, OnboardingStage.REJECTED},
        OnboardingStage.DOCUMENT_REVIEW: {OnboardingStage.TECHNICAL_INTEGRATION, OnboardingStage.REJECTED},
        OnboardingStage.TECHNICAL_INTEGRATION: {OnboardingStage.SANDBOX_VERIFICATION, OnboardingStage.REJECTED},
        OnboardingStage.SANDBOX_VERIFICATION: {OnboardingStage.APPROVED, OnboardingStage.REJECTED},
        OnboardingStage.APPROVED: set(),
        OnboardingStage.REJECTED: set(),
    }

    @staticmethod
    def create_onboarding(
        db: Session, req: SupplierOnboardingCreateRequest, user_id: int
    ) -> SupplierOnboardingWorkflow:
        supplier = db.execute(
            select(Supplier).where(Supplier.supplier_id == req.supplier_id)
        ).scalar_one_or_none()
        if not supplier:
            raise EntityNotFoundError("Supplier", req.supplier_id)

        wf = SupplierOnboardingWorkflow(
            supplier_id=supplier.supplier_id,
            stage=OnboardingStage.INITIATED,
            checklist_json=req.checklist_json,
            assigned_admin_id=user_id,
            notes=req.notes,
        )
        db.add(wf)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_ONBOARDING_CREATED",
            entity_type="supplier_onboarding_workflows",
            entity_id=wf.onboarding_uid,
            new_value_json={"supplier_id": wf.supplier_id, "stage": wf.stage.value},
        ))
        db.commit()
        db.refresh(wf)
        return wf

    @staticmethod
    def advance_onboarding(
        db: Session, onboarding_id: int, req: SupplierOnboardingAdvanceRequest, user_id: int
    ) -> SupplierOnboardingWorkflow:
        wf = db.execute(
            select(SupplierOnboardingWorkflow).where(SupplierOnboardingWorkflow.id == onboarding_id).with_for_update()
        ).scalar_one_or_none()
        if not wf:
            raise EntityNotFoundError("SupplierOnboardingWorkflow", onboarding_id)

        allowed = SupplierPortalService._VALID_ONBOARDING_TRANSITIONS.get(wf.stage, set())
        if req.target_stage not in allowed:
            raise InvalidStateTransitionError(wf.stage.value, req.target_stage.value)

        if req.target_stage == OnboardingStage.REJECTED and not req.rejection_reason:
            raise BadRequestException("rejection_reason is required when rejecting supplier onboarding.")

        if req.checklist_updates:
            merged = dict(wf.checklist_json or {})
            merged.update(req.checklist_updates)
            wf.checklist_json = merged

        if req.target_stage == OnboardingStage.APPROVED:
            if wf.checklist_json and not all(bool(v) for v in wf.checklist_json.values()):
                raise BadRequestException("All onboarding checklist items must be true before APPROVED.")
            wf.completed_at = datetime.now(timezone.utc)
            profile = db.execute(
                select(SupplierVerificationProfile).where(SupplierVerificationProfile.supplier_id == wf.supplier_id)
            ).scalar_one_or_none()
            if not profile:
                profile = SupplierVerificationProfile(supplier_id=wf.supplier_id)
                db.add(profile)
            profile.verification_status = SupplierVerificationStatus.VERIFIED
            profile.verified_at = datetime.now(timezone.utc)
            profile.verified_by_user_id = user_id

        if req.target_stage == OnboardingStage.REJECTED:
            wf.completed_at = datetime.now(timezone.utc)
            wf.rejection_reason = req.rejection_reason

        old_stage = wf.stage.value
        wf.stage = req.target_stage
        if req.notes:
            wf.notes = req.notes

        db.add(AuditLog(
            user_id=user_id,
            action="SUPPLIER_ONBOARDING_ADVANCED",
            entity_type="supplier_onboarding_workflows",
            entity_id=wf.onboarding_uid,
            old_value_json={"stage": old_stage},
            new_value_json={"stage": wf.stage.value},
        ))
        db.commit()
        db.refresh(wf)
        return wf

    @staticmethod
    def list_onboardings(
        db: Session, supplier_id: Optional[str] = None
    ) -> List[SupplierOnboardingWorkflow]:
        stmt = select(SupplierOnboardingWorkflow)
        if supplier_id:
            stmt = stmt.where(SupplierOnboardingWorkflow.supplier_id == supplier_id.upper())
        return list(db.execute(stmt.order_by(SupplierOnboardingWorkflow.created_at.desc())).scalars().all())

    # --- Settlement Netting Batches (Admin or PM) ---

    @staticmethod
    def create_netting_batch(
        db: Session, req: SettlementNettingCreateRequest, user_id: int
    ) -> SettlementNettingBatch:
        supplier = db.execute(
            select(Supplier).where(Supplier.supplier_id == req.supplier_id)
        ).scalar_one_or_none()
        if not supplier:
            raise EntityNotFoundError("Supplier", req.supplier_id)

        start_dt = datetime.combine(req.period_start, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(req.period_end, datetime.max.time(), tzinfo=timezone.utc)
        req_currency = req.currency.upper()

        existing_batches = list(
            db.execute(
                select(SettlementNettingBatch.po_numbers_json).where(
                    SettlementNettingBatch.supplier_id == supplier.supplier_id,
                    SettlementNettingBatch.status != SettlementBatchStatus.CANCELLED,
                )
            ).scalars().all()
        )
        already_batched = {po for po_list in existing_batches for po in (po_list or [])}

        candidate_pos = list(
            db.execute(
                select(PurchaseOrder).where(
                    PurchaseOrder.supplier_id == supplier.supplier_id,
                    PurchaseOrder.currency == req_currency,
                    PurchaseOrder.status.in_([POStatus.CONFIRMED, POStatus.PARTIALLY_RECEIVED, POStatus.COMPLETED]),
                    PurchaseOrder.ordered_at >= start_dt,
                    PurchaseOrder.ordered_at <= end_dt,
                )
            ).scalars().all()
        )
        pos = [
            p for p in candidate_pos
            if p.po_number not in already_batched
            and start_dt <= _ensure_utc(p.ordered_at) <= end_dt
        ]
        po_nums = [p.po_number for p in pos]
        gross_payable = sum((p.total_committed_spend_inr for p in pos), Decimal("0.00"))

        gross_refunds = Decimal("0.00")
        if po_nums:
            line_ids = list(
                db.execute(
                    select(PurchaseOrderLine.id).where(PurchaseOrderLine.po_number.in_(po_nums))
                ).scalars().all()
            )
            if line_ids:
                ful_refunds = db.execute(
                    select(func.coalesce(func.sum(PurchaseOrderFulfillment.supplier_refund_received_inr), Decimal("0.00")))
                    .where(PurchaseOrderFulfillment.po_line_id.in_(line_ids))
                ).scalar_one()
                gross_refunds = Decimal(str(ful_refunds))

        net_amount = gross_payable - gross_refunds
        batch = SettlementNettingBatch(
            supplier_id=supplier.supplier_id,
            period_start=req.period_start,
            period_end=req.period_end,
            currency=req.currency,
            gross_payable_inr=gross_payable,
            gross_receivable_refunds_inr=gross_refunds,
            net_settlement_inr=net_amount,
            po_numbers_json=po_nums,
            status=SettlementBatchStatus.CALCULATED,
            created_by_user_id=user_id,
            notes=req.notes,
        )
        db.add(batch)
        db.flush()
        db.add(AuditLog(
            user_id=user_id,
            action="SETTLEMENT_NETTING_CALCULATED",
            entity_type="settlement_netting_batches",
            entity_id=batch.batch_uid,
            new_value_json={"net_settlement_inr": str(net_amount), "po_count": len(po_nums)},
        ))
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def approve_netting_batch(
        db: Session, batch_id: int, user_id: int
    ) -> SettlementNettingBatch:
        batch = db.execute(
            select(SettlementNettingBatch).where(SettlementNettingBatch.id == batch_id).with_for_update()
        ).scalar_one_or_none()
        if not batch:
            raise EntityNotFoundError("SettlementNettingBatch", batch_id)
        if batch.status != SettlementBatchStatus.CALCULATED:
            raise InvalidStateTransitionError(batch.status.value, SettlementBatchStatus.APPROVED.value)

        batch.status = SettlementBatchStatus.APPROVED
        batch.approved_by_user_id = user_id
        db.add(AuditLog(
            user_id=user_id,
            action="SETTLEMENT_NETTING_APPROVED",
            entity_type="settlement_netting_batches",
            entity_id=batch.batch_uid,
        ))
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def settle_netting_batch(
        db: Session, batch_id: int, user_id: int
    ) -> SettlementNettingBatch:
        batch = db.execute(
            select(SettlementNettingBatch).where(SettlementNettingBatch.id == batch_id).with_for_update()
        ).scalar_one_or_none()
        if not batch:
            raise EntityNotFoundError("SettlementNettingBatch", batch_id)
        if batch.status != SettlementBatchStatus.APPROVED:
            raise InvalidStateTransitionError(batch.status.value, SettlementBatchStatus.SETTLED.value)

        batch.status = SettlementBatchStatus.SETTLED
        batch.settled_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            user_id=user_id,
            action="SETTLEMENT_NETTING_SETTLED",
            entity_type="settlement_netting_batches",
            entity_id=batch.batch_uid,
            new_value_json={"net_settlement_inr": str(batch.net_settlement_inr)},
        ))
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def list_netting_batches(
        db: Session, supplier_id: Optional[str] = None
    ) -> List[SettlementNettingBatch]:
        stmt = select(SettlementNettingBatch)
        if supplier_id:
            stmt = stmt.where(SettlementNettingBatch.supplier_id == supplier_id.upper())
        return list(db.execute(stmt.order_by(SettlementNettingBatch.created_at.desc())).scalars().all())
