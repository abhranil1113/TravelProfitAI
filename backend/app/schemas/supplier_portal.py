from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.models.schema import (
    InventoryCategory,
    OnboardingStage,
    RateSyncStatus,
    SettlementBatchStatus,
    SupplierCredentialStatus,
    SupplierTier,
    SupplierVerificationStatus,
    UnitType,
)


# =============================================================================
# DOMAIN 3: SUPPLIER COLLABORATION & CONNECTIVITY HUB
# =============================================================================

ALLOWED_SUPPLIER_SCOPES = {"rates:write", "availability:write", "sync:read"}


class SupplierCredentialCreateRequest(BaseModel):
    supplier_id: str = Field(..., min_length=2, max_length=32)
    label: str = Field(..., min_length=2, max_length=100)
    scopes: List[str] = Field(default_factory=lambda: ["rates:write", "availability:write", "sync:read"])
    rate_limit_per_minute: int = Field(60, ge=1, le=5000)
    expires_in_days: Optional[int] = Field(90, ge=1, le=1095)

    @field_validator("supplier_id")
    @classmethod
    def normalize_supplier_id(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one supplier credential scope is required.")
        cleaned = [s.strip() for s in v]
        invalid = [s for s in cleaned if s not in ALLOWED_SUPPLIER_SCOPES]
        if invalid:
            raise ValueError(f"Unsupported supplier scopes {invalid}. Allowed: {sorted(ALLOWED_SUPPLIER_SCOPES)}.")
        return list(dict.fromkeys(cleaned))


class SupplierCredentialCreateResponse(BaseModel):
    """Only response in lifecycle that returns the raw_api_secret (one-time display)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    credential_uid: str
    supplier_id: str
    key_prefix: str
    label: str
    scopes: List[str]
    status: SupplierCredentialStatus
    rate_limit_per_minute: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    raw_api_secret: str


class SupplierCredentialResponse(BaseModel):
    """Standard credential view — NEVER exposes raw_api_secret or secret_hash."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    credential_uid: str
    supplier_id: str
    key_prefix: str
    label: str
    scopes_json: List[str] = Field(default_factory=list)
    status: SupplierCredentialStatus
    rate_limit_per_minute: int
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SupplierRatePushOfferItem(BaseModel):
    offer_id: str = Field(..., min_length=2, max_length=64)
    inventory_id: Optional[str] = Field(None, max_length=64)
    dest_id: str = Field(..., min_length=2, max_length=32)
    origin_dest_id: Optional[str] = Field(None, max_length=32)
    inventory_category: InventoryCategory
    unit_type: UnitType
    unit_cost: Decimal = Field(..., ge=0)
    list_price: Decimal = Field(..., ge=0)
    currency_code: str = Field("INR", min_length=3, max_length=3)
    moq: int = Field(1, ge=1)
    max_capacity: int = Field(..., ge=1)
    available_units: Optional[int] = Field(None, ge=0)
    valid_from: date
    valid_until: date
    travel_date: date
    external_offer_reference: Optional[str] = Field(None, max_length=128)

    @field_validator("dest_id", "currency_code")
    @classmethod
    def upper_codes(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_dates_and_caps(self) -> SupplierRatePushOfferItem:
        if self.valid_from > self.valid_until:
            raise ValueError("valid_from cannot be after valid_until.")
        if self.valid_until > self.travel_date:
            raise ValueError("valid_until cannot be after travel_date.")
        if self.max_capacity < self.moq:
            raise ValueError("max_capacity must be >= moq.")
        if self.inventory_category == InventoryCategory.HOTEL and self.unit_type != UnitType.ROOM_NIGHT:
            raise ValueError("HOTEL offers must use unit_type ROOM_NIGHT.")
        if self.inventory_category == InventoryCategory.FLIGHT and self.unit_type != UnitType.SEAT:
            raise ValueError("FLIGHT offers must use unit_type SEAT.")
        return self


class SupplierRatePushRequest(BaseModel):
    idempotency_key: Optional[str] = Field(None, min_length=4, max_length=128)
    offers: List[SupplierRatePushOfferItem] = Field(..., min_length=1, max_length=500)


class SupplierRateSyncLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sync_uid: str
    supplier_id: str
    credential_id: Optional[int] = None
    idempotency_key: str
    payload_hash: str
    status: RateSyncStatus
    offers_received: int
    offers_upserted: int
    snapshots_updated: int
    offers_rejected: int
    error_details_json: List[Dict[str, Any]] = Field(default_factory=list)
    synced_at: datetime


class SupplierRateSyncLogListResponse(BaseModel):
    items: List[SupplierRateSyncLogResponse]
    total: int
    page: int
    page_size: int


class SupplierTierUpdateRequest(BaseModel):
    tier: Optional[SupplierTier] = None
    verification_status: Optional[SupplierVerificationStatus] = None
    risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    sla_response_hours: Optional[int] = Field(None, ge=1, le=720)
    notes: Optional[str] = Field(None, max_length=1000)


class SupplierVerificationProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: str
    tier: SupplierTier
    verification_status: SupplierVerificationStatus
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[int] = None
    risk_score: float
    sla_response_hours: int
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SupplierOnboardingCreateRequest(BaseModel):
    supplier_id: str = Field(..., min_length=2, max_length=32)
    checklist_json: Dict[str, bool] = Field(
        default_factory=lambda: {
            "kyc_verified": False,
            "tax_registration_verified": False,
            "api_sandbox_passed": False,
            "sla_signed": False,
        }
    )
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("supplier_id")
    @classmethod
    def upper_sid(cls, v: str) -> str:
        return v.strip().upper()


class SupplierOnboardingAdvanceRequest(BaseModel):
    target_stage: OnboardingStage
    checklist_updates: Optional[Dict[str, bool]] = None
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=1000)


class SupplierOnboardingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    onboarding_uid: str
    supplier_id: str
    stage: OnboardingStage
    checklist_json: Dict[str, bool] = Field(default_factory=dict)
    assigned_admin_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SettlementNettingCreateRequest(BaseModel):
    supplier_id: str = Field(..., min_length=2, max_length=32)
    period_start: date
    period_end: date
    currency: str = Field("INR", min_length=3, max_length=3)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("supplier_id", "currency")
    @classmethod
    def upper_fields(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_period(self) -> SettlementNettingCreateRequest:
        if self.period_start > self.period_end:
            raise ValueError("period_start cannot be after period_end.")
        return self


class SettlementNettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_uid: str
    supplier_id: str
    period_start: date
    period_end: date
    currency: str
    gross_payable_inr: Decimal
    gross_receivable_refunds_inr: Decimal
    net_settlement_inr: Decimal
    po_numbers_json: List[str] = Field(default_factory=list)
    status: SettlementBatchStatus
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    settled_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
