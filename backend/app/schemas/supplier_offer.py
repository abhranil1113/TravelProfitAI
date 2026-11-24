from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.schema import InventoryCategory, OfferStatus, UnitType
from backend.app.schemas.inventory import InventorySnapshotResponse


class SupplierOfferCreateRequest(BaseModel):
    offer_id: Optional[str] = None
    supplier_id: str = Field(..., max_length=32)
    inventory_id: Optional[str] = None
    dest_id: Optional[str] = "BLR"
    origin_dest_id: Optional[str] = Field(None, max_length=32)
    inventory_category: InventoryCategory = InventoryCategory.HOTEL
    unit_type: UnitType = UnitType.ROOM_NIGHT
    available_qty: int = 10
    moq: int = 1
    cost_per_unit_inr: Decimal = Decimal("1000.00")
    currency: str = Field("INR", max_length=8)
    original_cost: Optional[Decimal] = None
    original_currency: Optional[str] = Field(None, max_length=8)
    travel_date: Optional[date] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    cancellation_deadline: Optional[datetime] = None
    refundable: bool = False
    refund_penalty_pct: float = Field(0.0, ge=0.0, le=1.0)
    status: OfferStatus = OfferStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def resolve_offer_fields(cls, data):
        if isinstance(data, dict):
            if not data.get("offer_id"):
                import uuid
                data["offer_id"] = f"OFF-{uuid.uuid4().hex[:8].upper()}"
            if "inventory_id" not in data and "inventory_item_id" in data:
                data["inventory_id"] = data["inventory_item_id"]
            if "cost_per_unit_inr" not in data and "offer_price_inr" in data:
                data["cost_per_unit_inr"] = data["offer_price_inr"]
            if "moq" not in data and "min_quantity" in data:
                data["moq"] = data["min_quantity"]
            if "available_qty" not in data:
                data["available_qty"] = data.get("available_units") or data.get("max_quantity") or 10
            if "valid_until" not in data and "valid_to" in data:
                val = data["valid_to"]
                if isinstance(val, str) and len(val) == 10:
                    data["valid_until"] = datetime.fromisoformat(f"{val}T23:59:59")
                elif isinstance(val, (date, datetime)):
                    data["valid_until"] = val
            if not data.get("valid_until"):
                data["valid_until"] = datetime.now() + timedelta(days=30)
            if "valid_from" in data:
                val = data["valid_from"]
                if isinstance(val, str) and len(val) == 10:
                    data["valid_from"] = datetime.fromisoformat(f"{val}T00:00:00")
            if not data.get("travel_date"):
                if data.get("valid_from"):
                    vf = data["valid_from"]
                    data["travel_date"] = vf.date() if isinstance(vf, datetime) else vf
                else:
                    data["travel_date"] = date.today() + timedelta(days=7)
        return data


class SupplierOfferUpdateRequest(BaseModel):
    available_qty: Optional[int] = Field(None, gt=0)
    moq: Optional[int] = Field(None, ge=1)
    cost_per_unit_inr: Optional[Decimal] = Field(None, gt=0)
    valid_until: Optional[datetime] = None
    cancellation_deadline: Optional[datetime] = None
    refundable: Optional[bool] = None
    refund_penalty_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[OfferStatus] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_update_fields(cls, data):
        if isinstance(data, dict):
            if "cost_per_unit_inr" not in data and "offer_price_inr" in data:
                data["cost_per_unit_inr"] = data["offer_price_inr"]
            if "moq" not in data and "min_quantity" in data:
                data["moq"] = data["min_quantity"]
            if "available_qty" not in data:
                if "available_units" in data:
                    data["available_qty"] = data["available_units"]
                elif "max_quantity" in data:
                    data["available_qty"] = data["max_quantity"]
            if "valid_until" not in data and "valid_to" in data:
                val = data["valid_to"]
                if isinstance(val, str) and len(val) == 10:
                    data["valid_until"] = datetime.fromisoformat(f"{val}T23:59:59")
                elif isinstance(val, (date, datetime)):
                    data["valid_until"] = val
        return data


class OfferPredictionBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    offer_id: str
    as_of_date: date
    predicted_selling_price_inr: Optional[Decimal] = None
    predicted_cancellation_prob: Optional[float] = None
    expected_net_margin_inr: Optional[Decimal] = None
    expected_margin_pct: Optional[float] = None
    break_even_sell_through: Optional[float] = None
    spoilage_risk_pct: Optional[float] = None
    model_version_used: Optional[str] = None
    created_at: datetime


class SupplierOfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offer_id: str
    id: Optional[str] = None
    supplier_id: str
    inventory_id: str
    dest_id: str
    origin_dest_id: Optional[str] = None
    inventory_category: InventoryCategory
    unit_type: UnitType
    available_qty: int
    moq: int
    cost_per_unit_inr: Decimal
    offer_price_inr: Optional[Decimal] = None
    available_units: Optional[int] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    currency: str
    original_cost: Optional[Decimal] = None
    original_currency: Optional[str] = None
    travel_date: date
    valid_from: Optional[datetime] = None
    valid_until: datetime
    valid_to: Optional[datetime] = None
    cancellation_deadline: Optional[datetime] = None
    refundable: bool
    refund_penalty_pct: float
    status: OfferStatus
    created_at: datetime
    updated_at: datetime
    latest_prediction: Optional[OfferPredictionBriefResponse] = None
    latest_snapshot: Optional[InventorySnapshotResponse] = None

    @model_validator(mode="before")
    @classmethod
    def populate_id(cls, data):
        if hasattr(data, "offer_id"):
            vf = getattr(data, "valid_from", None)
            vu = getattr(data, "valid_until", None)
            cost = getattr(data, "unit_cost_inr", None)
            if cost is None:
                cost = getattr(data, "cost_per_unit_inr", Decimal("0.00"))
            cap = getattr(data, "max_capacity", None)
            if cap is None:
                cap = getattr(data, "available_qty", 0)
            curr = getattr(data, "currency_code", None) or getattr(data, "currency", "INR")
            return {
                "offer_id": data.offer_id,
                "id": data.offer_id,
                "supplier_id": data.supplier_id,
                "inventory_id": data.inventory_id or "",
                "dest_id": data.dest_id,
                "origin_dest_id": data.origin_dest_id,
                "inventory_category": data.inventory_category,
                "unit_type": data.unit_type,
                "available_qty": cap,
                "available_units": cap,
                "max_quantity": cap,
                "moq": data.moq,
                "min_quantity": data.moq,
                "cost_per_unit_inr": cost,
                "offer_price_inr": cost,
                "currency": curr,
                "original_cost": getattr(data, "original_unit_cost", None) or getattr(data, "original_cost", None),
                "original_currency": getattr(data, "original_currency", None),
                "travel_date": data.travel_date,
                "valid_from": datetime.combine(vf, datetime.min.time()) if isinstance(vf, date) and not isinstance(vf, datetime) else vf,
                "valid_until": datetime.combine(vu, datetime.min.time()) if isinstance(vu, date) and not isinstance(vu, datetime) else vu,
                "valid_to": datetime.combine(vu, datetime.min.time()) if isinstance(vu, date) and not isinstance(vu, datetime) else vu,
                "refundable": getattr(data, "refundable", False) if hasattr(data, "refundable") else (getattr(data, "customer_refund_rate_rc", 0.0) > 0),
                "refund_penalty_pct": getattr(data, "refund_penalty_pct", 0.0) if hasattr(data, "refund_penalty_pct") else getattr(data, "customer_refund_rate_rc", 0.0),
                "status": data.status,
                "created_at": getattr(data, "created_at", None) or datetime.now(),
                "updated_at": getattr(data, "updated_at", None) or datetime.now(),
            }
        elif isinstance(data, dict):
            if "offer_id" in data and "id" not in data:
                data["id"] = data["offer_id"]
            if "cost_per_unit_inr" in data and "offer_price_inr" not in data:
                data["offer_price_inr"] = data["cost_per_unit_inr"]
            if "unit_cost_inr" in data and "cost_per_unit_inr" not in data:
                data["cost_per_unit_inr"] = data["unit_cost_inr"]
                data["offer_price_inr"] = data["unit_cost_inr"]
            if "max_capacity" in data and "available_qty" not in data:
                data["available_qty"] = data["max_capacity"]
            if "available_qty" in data:
                data["available_units"] = data.get("available_units", data["available_qty"])
                data["max_quantity"] = data.get("max_quantity", data["available_qty"])
            if "moq" in data:
                data["min_quantity"] = data.get("min_quantity", data["moq"])
            if "valid_until" in data and "valid_to" not in data:
                data["valid_to"] = data["valid_until"]
            if "currency_code" in data and "currency" not in data:
                data["currency"] = data["currency_code"]
        return data


class SupplierOfferListResponse(BaseModel):
    items: List[SupplierOfferResponse]
    total: int
    page: int
    page_size: int


class BulkImportResponse(BaseModel):
    batch_uid: str
    rows_received: int
    rows_valid: int
    rows_imported: int
    rows_failed: int
    status: str
    error_summary: Optional[str] = None
    imported_count: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def populate_imported_count(cls, data):
        if hasattr(data, "rows_imported") and not hasattr(data, "imported_count"):
            try:
                setattr(data, "imported_count", data.rows_imported)
            except Exception:
                pass
        elif isinstance(data, dict):
            if "imported_count" not in data and "rows_imported" in data:
                data["imported_count"] = data["rows_imported"]
        return data
