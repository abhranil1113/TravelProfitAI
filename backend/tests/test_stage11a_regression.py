from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
import threading
import pytest
from sqlalchemy import func, select

from backend.app.core.exceptions import BadRequestException
from backend.app.core.notification_events import EventTypes
from backend.app.models.schema import (
    ApprovalStatus,
    Base,
    BudgetPeriodType,
    BudgetScope,
    BudgetStatus,
    Destination,
    FulfillmentStatus,
    InventoryCategory,
    Notification,
    POStatus,
    ProcurementBudget,
    PurchaseOrder,
    PurchaseOrderFulfillment,
    PurchaseOrderLine,
    Supplier,
    SupplierOffer,
    SupplierType,
    UnitType,
    User,
    UserRole,
)
from backend.app.schemas.budget import BudgetAdjustRequest
from backend.app.schemas.procurement import (
    FulfillmentCreateRequest,
    PurchaseOrderConfirmRequest,
    PurchaseOrderCreateLine,
    PurchaseOrderCreateRequest,
)
from backend.app.services.budget_service import BudgetService
from backend.app.services.notification_service import NotificationService
from backend.app.services.procurement_service import ProcurementService
from backend.tests.conftest import TestingSessionLocal


# ==============================================================================
# SECTION 1: NOTIFICATION EVENT LOOP & THREADPOOL DISPATCH TESTS
# ==============================================================================

def test_notify_sync_from_worker_thread_no_loop(db):
    """
    Verify notify_sync does not drop coroutines when invoked from a worker thread
    without a running asyncio loop (FastAPI threadpool simulation).
    """
    error_container = []
    result_container = []

    def worker_action():
        try:
            # Verify no running loop in this worker thread
            with pytest.raises(RuntimeError):
                asyncio.get_running_loop()

            res = NotificationService.notify_sync(
                event_type=EventTypes.PROCUREMENT_PO_CREATED,
                title="Threadpool PO Notification",
                message="Testing threadpool dispatch without running loop",
                recipient_ids=[1],
                source_module="procurement",
                db=db,
            )
            result_container.append(res)
        except Exception as exc:
            error_container.append(exc)

    thread = threading.Thread(target=worker_action)
    thread.start()
    thread.join(timeout=10.0)

    assert not error_container, f"Unexpected error in worker thread: {error_container}"
    assert len(result_container) == 1

    # Verify notification was persisted in database and not dropped
    notif = db.execute(
        select(Notification).where(
            Notification.user_id == 1,
            Notification.title == "Threadpool PO Notification",
        )
    ).scalar_one_or_none()

    assert notif is not None
    assert notif.message == "Testing threadpool dispatch without running loop"


def test_notify_sync_with_main_loop_registered(db):
    """
    Verify notify_sync safely schedules onto the registered main event loop
    via asyncio.run_coroutine_threadsafe when called from an anyio/FastAPI threadpool worker.
    """
    main_loop = asyncio.new_event_loop()
    loop_thread_ready = threading.Event()
    stop_loop_event = threading.Event()

    def run_main_loop():
        asyncio.set_event_loop(main_loop)
        loop_thread_ready.set()
        main_loop.run_forever()

    loop_thread = threading.Thread(target=run_main_loop, daemon=True)
    loop_thread.start()
    loop_thread_ready.wait(timeout=5.0)

    try:
        # Register the running main loop
        NotificationService.set_main_loop(main_loop)
        assert NotificationService.get_main_loop() is main_loop

        future_container = []
        error_container = []

        def worker_action():
            try:
                # Dispatched from a threadpool worker
                future = NotificationService.notify_sync(
                    event_type=EventTypes.SYSTEM_ERROR_RATE,
                    title="Main Loop Scheduled Alert",
                    message="Notification scheduled from worker to main loop",
                    recipient_ids=[1],
                    source_module="system",
                    db=db,
                )
                future_container.append(future)
            except Exception as exc:
                error_container.append(exc)

        worker_thread = threading.Thread(target=worker_action)
        worker_thread.start()
        worker_thread.join(timeout=10.0)

        assert not error_container, f"Worker thread error: {error_container}"
        assert len(future_container) == 1

        future = future_container[0]
        # Wait for the future dispatched to the main loop to finish
        result = future.result(timeout=10.0)
        assert result.persisted_count >= 1

        # Check DB persistence
        notif = db.execute(
            select(Notification).where(
                Notification.user_id == 1,
                Notification.title == "Main Loop Scheduled Alert",
            )
        ).scalar_one_or_none()
        assert notif is not None
    finally:
        main_loop.call_soon_threadsafe(main_loop.stop)
        loop_thread.join(timeout=5.0)
        NotificationService.set_main_loop(None)


@pytest.mark.asyncio
async def test_notify_async_direct(db):
    """Verify direct async NotificationService.notify executes cleanly with full persistence."""
    result = await NotificationService.notify(
        event_type=EventTypes.PRICING_BUDGET_THRESHOLD,
        title="Direct Async Budget Alert",
        message="Async notification execution test",
        recipient_ids=[1],
        source_module="budget",
        db=db,
    )

    assert result.persisted_count == 1
    assert result.delivery_status in ("PERSISTED_OFFLINE", "DELIVERED", "COMPLETED")

    notif = db.execute(
        select(Notification).where(
            Notification.user_id == 1,
            Notification.title == "Direct Async Budget Alert",
        )
    ).scalar_one_or_none()
    assert notif is not None


# ==============================================================================
# SECTION 2: CONCURRENT PURCHASE ORDER FULFILLMENT TESTS
# ==============================================================================

@pytest.fixture(scope="function")
def concurrent_env():
    """
    Provides an isolated named in-memory SQLite database with shared cache (cache=shared)
    so multiple concurrent threads can instantiate distinct sessions while sharing
    the same in-memory database with true cross-thread transaction locking.
    """
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.core.security import hash_password

    db_name = f"mem_stage11a_{uuid.uuid4().hex[:8]}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionMaker()

    # Seed Admin User and Destination
    admin = User(
        id=1,
        email="admin@inventoryiq.com",
        full_name="System Admin",
        hashed_password=hash_password("AdminSecurePass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    blr = Destination(
        dest_id="BLR",
        name="Bangalore",
        city="Bangalore",
        country="India",
        search_volume_ceiling=1000,
    )
    session.add_all([admin, blr])
    session.commit()

    yield session, SessionMaker

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_concurrent_po_fulfillment_prevents_over_receipt(concurrent_env):
    """
    Verify pessimistic locking prevents over-receipt during concurrent fulfillment.
    Line ordered quantity is 10. Two concurrent requests attempt 7 units each (total 14).
    Exactly one must succeed and one must be rejected.
    """
    db, SessionMaker = concurrent_env
    today = date.today()
    supplier = Supplier(
        supplier_id="SUP-FULFILL-RACE",
        name="Fulfillment Race Supplier",
        supplier_type=SupplierType.HOTEL,
    )
    db.add(supplier)
    db.flush()

    offer = SupplierOffer(
        offer_id="OFF-FULFILL-RACE",
        supplier_id=supplier.supplier_id,
        dest_id="BLR",
        currency_code="INR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("1000.00"),
        list_price_inr=Decimal("1200.00"),
        valid_from=today,
        valid_until=today + timedelta(days=7),
        travel_date=today + timedelta(days=14),
        max_capacity=50,
        moq=1,
    )
    db.add(offer)
    db.flush()

    db.commit()

    po_create_req = PurchaseOrderCreateRequest(
        supplier_id=supplier.supplier_id,
        lines=[
            PurchaseOrderCreateLine(
                offer_id=offer.offer_id,
                ordered_qty=10,
                unit_cost_inr=Decimal("1000.00"),
            )
        ],
        notes="PO for fulfillment race test",
    )
    po = ProcurementService.create_purchase_order(db, po_create_req, user_id=1)
    ProcurementService.confirm_purchase_order(
        db,
        po.po_number,
        PurchaseOrderConfirmRequest(notes="Confirming for test"),
        user_id=1,
    )
    po_num = po.po_number
    line_id = po.lines[0].id

    results = []
    errors = []

    def execute_fulfillment(qty: int):
        thread_db = SessionMaker()
        try:
            req = FulfillmentCreateRequest(
                delivered_qty=qty,
                notes=f"Attempting {qty} units",
            )
            ful = ProcurementService.record_fulfillment(
                db=thread_db,
                po_number=po_num,
                line_id=line_id,
                req=req,
                user_id=1,
            )
            results.append(ful.delivered_qty)
        except (BadRequestException, Exception) as exc:
            errors.append(str(exc))
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(execute_fulfillment, 7)
        f2 = executor.submit(execute_fulfillment, 7)
        f1.result()
        f2.result()

    # Exactly one request must succeed (7 units) and one must be rejected
    assert len(results) == 1, f"Expected 1 success, got {len(results)}: results={results}, errors={errors}"
    assert results[0] == 7
    assert len(errors) == 1, f"Expected 1 rejection error, got {len(errors)}: {errors}"

    # Verify database state has strictly 7 units fulfilled (never 14)
    db.expire_all()
    total_delivered = db.execute(
        select(func.coalesce(func.sum(PurchaseOrderFulfillment.delivered_qty), 0))
        .where(PurchaseOrderFulfillment.po_line_id == line_id)
    ).scalar_one()

    assert total_delivered == 7
    assert total_delivered <= 10


# ==============================================================================
# SECTION 3: CONCURRENT BUDGET & PO RESERVATION TESTS
# ==============================================================================

def test_concurrent_po_reservations_budget_limit(concurrent_env):
    """
    Verify concurrent PO reservations cannot exceed active budget available amount.
    Budget total is 100,000 INR. Two concurrent requests attempt 70,000 INR each (total 140,000).
    Exactly one must succeed and one must be rejected.
    """
    db, SessionMaker = concurrent_env
    today = date.today()
    budget = ProcurementBudget(
        budget_code="BUD-RACE-LIMIT",
        name="Concurrent Reservation Limit Budget",
        scope=BudgetScope.GLOBAL,
        period_type=BudgetPeriodType.QUARTERLY,
        period_start=today,
        period_end=today + timedelta(days=90),
        total_amount_inr=Decimal("100000.00"),
        spent_amount_inr=Decimal("0.00"),
        reserved_amount_inr=Decimal("0.00"),
        status=BudgetStatus.ACTIVE,
        created_by_user_id=1,
    )
    db.add(budget)

    supplier = Supplier(
        supplier_id="SUP-BUDGET-RACE",
        name="Budget Race Supplier",
        supplier_type=SupplierType.HOTEL,
    )
    db.add(supplier)
    db.flush()

    offer = SupplierOffer(
        offer_id="OFF-BUDGET-RACE",
        supplier_id=supplier.supplier_id,
        dest_id="BLR",
        currency_code="INR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("70000.00"),
        list_price_inr=Decimal("80000.00"),
        valid_from=today,
        valid_until=today + timedelta(days=7),
        travel_date=today + timedelta(days=14),
        max_capacity=50,
        moq=1,
    )
    db.add(offer)
    db.commit()
    budget_id = budget.id

    success_pos = []
    budget_errors = []

    def submit_po():
        thread_db = SessionMaker()
        try:
            req = PurchaseOrderCreateRequest(
                supplier_id=supplier.supplier_id,
                budget_id=budget_id,
                lines=[
                    PurchaseOrderCreateLine(
                        offer_id=offer.offer_id,
                        ordered_qty=1,
                        unit_cost_inr=Decimal("70000.00"),
                    )
                ],
                notes="Concurrent PO reservation test",
            )
            po = ProcurementService.create_purchase_order(
                db=thread_db,
                req=req,
                user_id=1,
            )
            success_pos.append(po.po_number)
        except (BadRequestException, Exception) as exc:
            budget_errors.append(str(exc))
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(submit_po)
        f2 = executor.submit(submit_po)
        f1.result()
        f2.result()

    # Exactly one PO must be created, and the second must be rejected
    assert len(success_pos) == 1, f"Expected 1 successful PO, got: {success_pos}"
    assert len(budget_errors) == 1, f"Expected 1 budget rejection, got: {budget_errors}"

    # Verify database budget state: reserved is exactly 70,000, not 140,000
    db.expire_all()
    b_fresh = db.execute(
        select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
    ).scalar_one()

    assert b_fresh.reserved_amount_inr == Decimal("70000.00")
    assert b_fresh.total_amount_inr == Decimal("100000.00")
    # Verify balance invariant: spent + reserved <= total
    assert b_fresh.spent_amount_inr + b_fresh.reserved_amount_inr <= b_fresh.total_amount_inr


def test_concurrent_budget_reduction_and_po_reservation(concurrent_env):
    """
    Verify serialization between budget reduction and PO reservation.
    Budget total is 100,000 INR.
    Operation A: PO requests 70,000 INR.
    Operation B: Reduction of 60,000 INR (new total 40,000 INR).
    Since 40,000 < 70,000, both cannot commit together.
    Row-level locking guarantees one succeeds and one is rejected, never corrupting balances.
    """
    db, SessionMaker = concurrent_env
    today = date.today()
    budget = ProcurementBudget(
        budget_code="BUD-ADJUST-RACE",
        name="Concurrent Adjustment Race Budget",
        scope=BudgetScope.GLOBAL,
        period_type=BudgetPeriodType.QUARTERLY,
        period_start=today,
        period_end=today + timedelta(days=90),
        total_amount_inr=Decimal("100000.00"),
        spent_amount_inr=Decimal("0.00"),
        reserved_amount_inr=Decimal("0.00"),
        status=BudgetStatus.ACTIVE,
        created_by_user_id=1,
    )
    db.add(budget)

    supplier = Supplier(
        supplier_id="SUP-ADJUST-RACE",
        name="Adjust Race Supplier",
        supplier_type=SupplierType.HOTEL,
    )
    db.add(supplier)
    db.flush()

    offer = SupplierOffer(
        offer_id="OFF-ADJUST-RACE",
        supplier_id=supplier.supplier_id,
        dest_id="BLR",
        currency_code="INR",
        inventory_category=InventoryCategory.HOTEL,
        unit_type=UnitType.ROOM_NIGHT,
        unit_cost_inr=Decimal("70000.00"),
        list_price_inr=Decimal("80000.00"),
        valid_from=today,
        valid_until=today + timedelta(days=7),
        travel_date=today + timedelta(days=14),
        max_capacity=50,
        moq=1,
    )
    db.add(offer)
    db.commit()
    budget_id = budget.id

    op_results = []
    op_errors = []

    def run_po_reserve():
        thread_db = SessionMaker()
        try:
            req = PurchaseOrderCreateRequest(
                supplier_id=supplier.supplier_id,
                budget_id=budget_id,
                lines=[
                    PurchaseOrderCreateLine(
                        offer_id=offer.offer_id,
                        ordered_qty=1,
                        unit_cost_inr=Decimal("70000.00"),
                    )
                ],
                notes="PO reserving 70k",
            )
            ProcurementService.create_purchase_order(thread_db, req, user_id=1)
            op_results.append("PO_RESERVED")
        except (BadRequestException, Exception) as exc:
            op_errors.append(f"PO_REJECTED: {exc}")
        finally:
            thread_db.close()

    def run_budget_adjust():
        thread_db = SessionMaker()
        try:
            req = BudgetAdjustRequest(
                amount_inr=Decimal("-60000.00"),
                description="Reducing budget by 60k",
            )
            BudgetService.adjust_budget(thread_db, budget_id, req, user_id=1)
            op_results.append("BUDGET_ADJUSTED")
        except (BadRequestException, Exception) as exc:
            op_errors.append(f"ADJUST_REJECTED: {exc}")
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_po_reserve)
        f2 = executor.submit(run_budget_adjust)
        f1.result()
        f2.result()

    # One operation must succeed, and the other must be rejected due to balance constraints
    assert len(op_results) == 1, f"Expected exactly 1 operation to succeed, got: {op_results}"
    assert len(op_errors) == 1, f"Expected exactly 1 operation to be rejected, got: {op_errors}"

    # Verify final budget invariants
    db.expire_all()
    b_final = db.execute(
        select(ProcurementBudget).where(ProcurementBudget.id == budget_id)
    ).scalar_one()

    assert b_final.spent_amount_inr + b_final.reserved_amount_inr <= b_final.total_amount_inr
    assert b_final.total_amount_inr > Decimal("0.00")
