from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.schema import OptimizationMode, SolverBackend


class PlatformConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_name: str
    version: int
    status: str
    is_active: bool
    activated_at: Optional[datetime] = None
    activated_by_user_id: Optional[int] = None
    default_total_budget_inr: Decimal
    max_supplier_share: Decimal
    max_destination_share: Decimal
    hotel_min_budget_share: Decimal
    hotel_max_budget_share: Decimal
    flight_min_budget_share: Decimal
    flight_max_budget_share: Decimal
    target_currency: str
    allow_prototype_currency_override: bool
    prototype_eur_to_inr_rate: Decimal
    bayesian_shrinkage_lambda: Decimal
    default_flight_salvage_pct: Decimal
    default_solver_backend: SolverBackend
    updated_by_user_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PlatformConfigCreateRequest(BaseModel):
    profile_name: str = Field("Default Profile", min_length=2, max_length=64)
    default_total_budget_inr: Decimal = Field(Decimal("100000000.00"), gt=0)
    max_supplier_share: Decimal = Field(Decimal("0.40"), gt=0, le=1)
    max_destination_share: Decimal = Field(Decimal("0.35"), gt=0, le=1)
    hotel_min_budget_share: Decimal = Field(Decimal("0.30"), ge=0, le=1)
    hotel_max_budget_share: Decimal = Field(Decimal("0.70"), ge=0, le=1)
    flight_min_budget_share: Decimal = Field(Decimal("0.30"), ge=0, le=1)
    flight_max_budget_share: Decimal = Field(Decimal("0.70"), ge=0, le=1)
    target_currency: str = Field("INR", min_length=3, max_length=3)
    allow_prototype_currency_override: bool = False
    prototype_eur_to_inr_rate: Decimal = Field(Decimal("90.00"), gt=0)
    bayesian_shrinkage_lambda: Decimal = Field(Decimal("0.30"), ge=0, le=1)
    default_flight_salvage_pct: Decimal = Field(Decimal("0.10"), ge=0, le=1)
    default_solver_backend: SolverBackend = SolverBackend.SCIP
    notes: Optional[str] = None


class PlatformConfigUpdateRequest(BaseModel):
    profile_name: Optional[str] = Field(None, min_length=2, max_length=64)
    default_total_budget_inr: Optional[Decimal] = Field(None, gt=0)
    max_supplier_share: Optional[Decimal] = Field(None, gt=0, le=1)
    max_destination_share: Optional[Decimal] = Field(None, gt=0, le=1)
    hotel_min_budget_share: Optional[Decimal] = Field(None, ge=0, le=1)
    hotel_max_budget_share: Optional[Decimal] = Field(None, ge=0, le=1)
    flight_min_budget_share: Optional[Decimal] = Field(None, ge=0, le=1)
    flight_max_budget_share: Optional[Decimal] = Field(None, ge=0, le=1)
    target_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    allow_prototype_currency_override: Optional[bool] = None
    prototype_eur_to_inr_rate: Optional[Decimal] = Field(None, gt=0)
    bayesian_shrinkage_lambda: Optional[Decimal] = Field(None, ge=0, le=1)
    default_flight_salvage_pct: Optional[Decimal] = Field(None, ge=0, le=1)
    default_solver_backend: Optional[SolverBackend] = None
    notes: Optional[str] = None


class PlatformConfigListResponse(BaseModel):
    items: List[PlatformConfigResponse]
    total: int


# --- Optimization Config Templates ---

class OptimizationConfigTemplateCreateRequest(BaseModel):
    template_name: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None
    default_mode: OptimizationMode = OptimizationMode.JOINT
    default_solver_backend: SolverBackend = SolverBackend.SCIP
    default_salvage_rate: Decimal = Field(Decimal("0.10"), ge=0, le=1)
    default_max_supplier_share: Decimal = Field(Decimal("0.40"), gt=0, le=1)
    default_max_destination_share: Decimal = Field(Decimal("0.35"), gt=0, le=1)
    default_budget_inr: Decimal = Field(Decimal("50000000.00"), gt=0)
    extra_params_json: Optional[Dict[str, Any]] = None
    is_active: bool = True


class OptimizationConfigTemplateUpdateRequest(BaseModel):
    template_name: Optional[str] = Field(None, min_length=2, max_length=64)
    description: Optional[str] = None
    default_mode: Optional[OptimizationMode] = None
    default_solver_backend: Optional[SolverBackend] = None
    default_salvage_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    default_max_supplier_share: Optional[Decimal] = Field(None, gt=0, le=1)
    default_max_destination_share: Optional[Decimal] = Field(None, gt=0, le=1)
    default_budget_inr: Optional[Decimal] = Field(None, gt=0)
    extra_params_json: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class OptimizationConfigTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_name: str
    description: Optional[str] = None
    default_mode: OptimizationMode
    default_solver_backend: SolverBackend
    default_salvage_rate: Decimal
    default_max_supplier_share: Decimal
    default_max_destination_share: Decimal
    default_budget_inr: Decimal
    extra_params_json: Optional[Dict[str, Any]] = None
    is_active: bool
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class OptimizationConfigTemplateListResponse(BaseModel):
    items: List[OptimizationConfigTemplateResponse]
    total: int
