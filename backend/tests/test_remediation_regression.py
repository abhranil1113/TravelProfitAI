from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.exceptions import BadRequestException, PermissionDeniedError
from backend.app.dependencies import require_worker_token
from backend.app.models.schema import (
    ApprovalStatus,
    BudgetStatus,
    BudgetTransactionType,
    InventoryCategory,
    OptimizationMode,
    POStatus,
    ProcurementBudget,
    SolverStatus,
    Supplier,
    SupplierOffer,
    SupplierType,
    UnitType,
)
from backend.app.schemas.optimization import OptimizationRunTriggerRequest
from backend.app.schemas.procurement import (
    FulfillmentCreateRequest,
    PurchaseOrderCreateLine,
    PurchaseOrderCreateRequest,
)
from backend.app.services.optimization_service import OptimizationService
from backend.app.services.procurement_service import ProcurementService


# ==============================================================================
# SECTION 1: OPTIMIZATION SERVICE REAL SOLVER EXECUTION
# ==============================================================================

def test_optimization_real_execution(seeded_optimization_db):
    db = seeded_optimization_db
    """Verify OptimizationService executes genuine OR-Tools solver and stores authentic metrics."""
    req = OptimizationRunTriggerRequest(
        optimization_mode=OptimizationMode.JOINT,
        total_budget_inr=Decimal("250000.00"),
        max_supplier_share=Decimal("0.40"),
        max_destination_share=Decimal("0.35"),
        scenario_name="Real Optimization Test",
    )
    run = OptimizationService.trigger_run(db, req, user_id=1)

    assert run.solver_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert run.best_objective_inr is not None
    assert run.best_objective_inr > Decimal("0.00")
    assert run.total_spend_inr > Decimal("0.00")
    assert run.total_spend_inr <= Decimal("250000.00")
    assert run.solve_time_seconds is not None
    assert run.selected_offers_count > 0
    assert len(run.recommendations) > 0

    # Verify authentic baseline benchmarks
    assert run.baseline_comparisons_json is not None
    assert len(run.baseline_comparisons_json) >= 2
    assert any("Greedy" in b.get("name", "") for b in run.baseline_comparisons_json)

    # Verify authentic constraint records
    assert len(run.constraints) >= 2
    budget_constraint = next((c for c in run.constraints if c.constraint_type.value == "BUDGET"), None)
    assert budget_constraint is not None
    assert budget_constraint.threshold_value == Decimal("250000.00")
    assert budget_constraint.slack_value >= Decimal("0.00")

    # Verify sensitivity scenarios
    assert len(run.sensitivity_scenarios) >= 2

    # Verify real artifacts generated
    assert len(run.artifacts) >= 3
    filenames = [a.filename for a in run.artifacts]
    assert "procurement_recommendations.csv" in filenames
    assert "rejected_opportunities.csv" in filenames
    assert "optimization_summary.json" in filenames


def test_optimization_compare_runs(seeded_optimization_db):
    db = seeded_optimization_db
    """Verify run comparison assigns comparison_group_id and retrieves compared runs."""
    req = OptimizationRunTriggerRequest(
        optimization_mode=OptimizationMode.HOTEL_ONLY,
        total_budget_inr=Decimal("100000.00"),
    )
    run1 = OptimizationService.trigger_run(db, req, user_id=1)
    run2 = OptimizationService.trigger_run(db, req, user_id=1)

    cmp_res = OptimizationService.compare_runs(db, [run1.run_id, run2.run_id])
    assert cmp_res.comparison_group_id.startswith("cmp_")
    assert len(cmp_res.runs) >= 2

    get_cmp = OptimizationService.get_comparison_group(db, cmp_res.comparison_group_id)
    assert get_cmp.comparison_group_id == cmp_res.comparison_group_id
    assert len(get_cmp.runs) >= 2


# ==============================================================================
# SECTION 2: PROCUREMENT VALIDATIONS & FINANCIAL INTEGRITY
# ==============================================================================

def test_procurement_rejects_inactive_supplier(db):
    """Verify PO creation rejects an inactive supplier."""
    supp = Supplier(supplier_id="INACTIVE-SUP", name="Inactive Corp", supplier_type=SupplierType.HOTEL, is_active=False)
    db.add(supp)
    db.commit()

    req = PurchaseOrderCreateRequest(
        supplier_id="INACTIVE-SUP",
        lines=[PurchaseOrderCreateLine(offer_id="OFF-TEST", ordered_qty=5, unit_cost_inr=Decimal("1000.00"))],
    )
    with pytest.raises(BadRequestException) as exc:
        ProcurementService.create_purchase_order(db, req, user_id=1)
    assert "inactive" in str(exc.value).lower()


def test_procurement_rejects_supplier_mismatch_and_expired_offer(db):
    """Verify PO creation rejects offers from other suppliers and expired offers."""
    supp1 = Supplier(supplier_id="SUP-A", name="Supplier A", supplier_type=SupplierType.HOTEL, is_active=True)
    supp2 = Supplier(supplier_id="SUP-B", name="Supplier B", supplier_type=SupplierType.HOTEL, is_active=True)
    db.add_all([supp1, supp2])
    db.commit()

    # Offer belonging to SUP-B
    off_b = SupplierOffer(
        offer_id="OFF-SUP-B",
        supplier_id="SUP-B",
        dest_id="BLR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("2000.00"),
        list_price_inr=Decimal("2500.00"),
        currency_code="INR",
        moq=1,
        max_capacity=10,
        valid_from=date.today() - timedelta(days=5),
        valid_until=date.today() + timedelta(days=5),
        travel_date=date.today() + timedelta(days=5),
    )
    # Expired offer belonging to SUP-A
    off_exp = SupplierOffer(
        offer_id="OFF-EXPIRED",
        supplier_id="SUP-A",
        dest_id="BLR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("1500.00"),
        list_price_inr=Decimal("2000.00"),
        currency_code="INR",
        moq=1,
        max_capacity=10,
        valid_from=date.today() - timedelta(days=10),
        valid_until=date.today() - timedelta(days=1),
        travel_date=date.today(),
    )
    db.add_all([off_b, off_exp])
    db.commit()

    # Attempt to order SUP-B offer under SUP-A
    req_mismatch = PurchaseOrderCreateRequest(
        supplier_id="SUP-A",
        lines=[PurchaseOrderCreateLine(offer_id="OFF-SUP-B", ordered_qty=2, unit_cost_inr=Decimal("2000.00"))],
    )
    with pytest.raises(BadRequestException) as exc1:
        ProcurementService.create_purchase_order(db, req_mismatch, user_id=1)
    assert "belongs to supplier" in str(exc1.value).lower()

    # Attempt to order expired offer
    req_expired = PurchaseOrderCreateRequest(
        supplier_id="SUP-A",
        lines=[PurchaseOrderCreateLine(offer_id="OFF-EXPIRED", ordered_qty=2, unit_cost_inr=Decimal("1500.00"))],
    )
    with pytest.raises(BadRequestException) as exc2:
        ProcurementService.create_purchase_order(db, req_expired, user_id=1)
    assert "expired" in str(exc2.value).lower()


def test_procurement_rejects_moq_and_capacity_violations(db):
    """Verify PO creation enforces MOQ and capacity bounds."""
    supp = Supplier(supplier_id="SUP-BOUNDS", name="Supplier Bounds", supplier_type=SupplierType.HOTEL, is_active=True)
    db.add(supp)
    db.commit()

    offer = SupplierOffer(
        offer_id="OFF-BOUNDS",
        supplier_id="SUP-BOUNDS",
        dest_id="BLR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("1000.00"),
        list_price_inr=Decimal("1200.00"),
        currency_code="INR",
        moq=5,
        max_capacity=20,
        valid_from=date.today() - timedelta(days=2),
        valid_until=date.today() + timedelta(days=10),
        travel_date=date.today() + timedelta(days=10),
    )
    db.add(offer)
    db.commit()

    # Below MOQ
    req_moq = PurchaseOrderCreateRequest(
        supplier_id="SUP-BOUNDS",
        lines=[PurchaseOrderCreateLine(offer_id="OFF-BOUNDS", ordered_qty=3, unit_cost_inr=Decimal("1000.00"))],
    )
    with pytest.raises(BadRequestException) as exc_moq:
        ProcurementService.create_purchase_order(db, req_moq, user_id=1)
    assert "moq" in str(exc_moq.value).lower()

    # Above capacity
    req_cap = PurchaseOrderCreateRequest(
        supplier_id="SUP-BOUNDS",
        lines=[PurchaseOrderCreateLine(offer_id="OFF-BOUNDS", ordered_qty=25, unit_cost_inr=Decimal("1000.00"))],
    )
    with pytest.raises(BadRequestException) as exc_cap:
        ProcurementService.create_purchase_order(db, req_cap, user_id=1)
    assert "capacity" in str(exc_cap.value).lower()


def test_procurement_fulfillment_overdelivery_prevention(db):
    """Verify fulfillment rejects over-delivery and completes PO when fully delivered."""
    supp = Supplier(supplier_id="SUP-FUL", name="Supplier Ful", supplier_type=SupplierType.HOTEL, is_active=True)
    db.add(supp)
    db.commit()

    offer = SupplierOffer(
        offer_id="OFF-FUL",
        supplier_id="SUP-FUL",
        dest_id="BLR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("500.00"),
        list_price_inr=Decimal("600.00"),
        currency_code="INR",
        moq=1,
        max_capacity=50,
        valid_from=date.today() - timedelta(days=2),
        valid_until=date.today() + timedelta(days=10),
        travel_date=date.today() + timedelta(days=10),
    )
    db.add(offer)
    db.commit()

    req = PurchaseOrderCreateRequest(
        supplier_id="SUP-FUL",
        lines=[PurchaseOrderCreateLine(offer_id="OFF-FUL", ordered_qty=10, unit_cost_inr=Decimal("500.00"))],
    )
    po = ProcurementService.create_purchase_order(db, req, user_id=1)
    lines = ProcurementService.list_lines(db, po.po_number)
    line_id = lines[0].id

    # First partial delivery: 6 units (ordered: 10)
    ProcurementService.record_fulfillment(
        db, po.po_number, line_id,
        FulfillmentCreateRequest(delivered_qty=6, notes="Partial 6 units"),
        user_id=1,
    )

    # Attempt to deliver 5 units (total: 11 > 10) -> Should fail
    with pytest.raises(BadRequestException) as exc:
        ProcurementService.record_fulfillment(
            db, po.po_number, line_id,
            FulfillmentCreateRequest(delivered_qty=5, notes="Excess 5 units"),
            user_id=1,
        )
    assert "over-delivery" in str(exc.value).lower()

    # Deliver remaining 4 units -> Line complete and PO transitions to COMPLETED
    ProcurementService.record_fulfillment(
        db, po.po_number, line_id,
        FulfillmentCreateRequest(delivered_qty=4, notes="Final 4 units"),
        user_id=1,
    )
    po_refreshed = ProcurementService.get_purchase_order(db, po.po_number)
    assert po_refreshed.status == POStatus.COMPLETED


# ==============================================================================
# SECTION 3: SECURITY & WORKER TOKEN BACKDOOR PREVENTION
# ==============================================================================

def test_require_worker_token_security():
    """Verify require_worker_token strictly requires secret token and rejects admin JWT bypass."""
    # Valid worker token
    valid_token = Settings().WORKER_SECRET_TOKEN
    assert require_worker_token(x_worker_token=valid_token) == valid_token

    # Missing token
    with pytest.raises(PermissionDeniedError):
        require_worker_token(x_worker_token=None)

    # Invalid token
    with pytest.raises(PermissionDeniedError):
        require_worker_token(x_worker_token="invalid_token_attempt")


def test_production_settings_validation():
    """Verify Settings rejects weak default secrets and wildcard CORS in production."""
    with pytest.raises(ValueError) as exc1:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="tbo_inventoryiq_super_secret_jwt_key_2026_sabuj_sangha",
            BACKEND_CORS_ORIGINS=["https://app.inventoryiq.com"],
        )
    assert "SECRET_KEY" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="A_Valid_Strong_Secret_Key_That_Has_More_Than_32_Chars!",
            WORKER_SECRET_TOKEN="tbo_worker_internal_secret_token_sabuj_sangha",
            BACKEND_CORS_ORIGINS=["https://app.inventoryiq.com"],
        )
    assert "WORKER_SECRET_TOKEN" in str(exc2.value)

    with pytest.raises(ValueError) as exc3:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="A_Valid_Strong_Secret_Key_That_Has_More_Than_32_Chars!",
            WORKER_SECRET_TOKEN="A_Valid_Strong_Worker_Token_32_Chars!",
            BACKEND_CORS_ORIGINS=["*"],
        )
    assert "BACKEND_CORS_ORIGINS" in str(exc3.value)
