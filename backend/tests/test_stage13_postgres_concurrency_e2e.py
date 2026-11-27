from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import get_settings
from backend.app.core.exceptions import AuthenticationError, BadRequestException, ConflictException
from backend.app.core.security import generate_secure_token, hash_password, hash_token
from backend.app.models.schema import (
    BudgetStatus,
    CurrencyExposureSnapshot,
    DeploymentMode,
    Destination,
    InventoryCategory,
    InventoryItem,
    MLModel,
    MLModelType,
    ModelDeployment,
    ModelLifecycleEvent,
    OfferStatus,
    ProcurementBudget,
    PurchaseOrder,
    PurchaseOrderLine,
    RefreshToken,
    Supplier,
    SupplierApiCredential,
    SupplierOffer,
    SupplierRateSyncLog,
    SupplierType,
    UnitType,
    User,
    UserRole,
)
from backend.app.schemas.mlops import ModelDeploymentCreateRequest
from backend.app.schemas.procurement import PurchaseOrderCreateLine, PurchaseOrderCreateRequest
from backend.app.schemas.supplier_portal import (
    SupplierCredentialCreateRequest,
    SupplierRatePushOfferItem,
    SupplierRatePushRequest,
)
from backend.app.services.auth_service import AuthService
from backend.app.services.mlops_service import MLOpsService
from backend.app.services.procurement_service import ProcurementService
from backend.app.services.supplier_portal_service import SupplierPortalService


def _get_pg_session_factory():
    url = get_settings().DATABASE_URL
    engine = create_engine(url, pool_size=8, max_overflow=8, pool_pre_ping=True)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _cleanup_pg(session_factory):
    """Removes every Stage 13 temporary record from live PostgreSQL cleanly in FK-safe order."""
    stmts = [
        "DELETE FROM notification_deliveries WHERE notification_id IN (SELECT id FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'stg13_%') OR entity_id LIKE 'STG13%')",
        "DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'stg13_%') OR entity_id LIKE 'STG13%' OR message LIKE '%STG13%'",
        "DELETE FROM audit_logs WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'stg13_%') OR entity_id LIKE 'STG13%'",
        "DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'stg13_%')",
        "DELETE FROM model_lifecycle_events WHERE model_id IN (SELECT id FROM ml_models WHERE version LIKE 'stg13-%') OR reason LIKE 'STG13%'",
        "DELETE FROM model_deployments WHERE model_id IN (SELECT id FROM ml_models WHERE version LIKE 'stg13-%') OR notes LIKE 'STG13%'",
        "DELETE FROM ml_models WHERE version LIKE 'stg13-%'",
        "DELETE FROM budget_ledger_entries WHERE budget_id IN (SELECT id FROM procurement_budgets WHERE budget_code LIKE 'STG13_%') OR description LIKE '%STG13%'",
        "DELETE FROM purchase_order_lines WHERE offer_id LIKE 'STG13_%' OR po_number IN (SELECT po_number FROM purchase_orders WHERE supplier_id LIKE 'STG13_%')",
        "DELETE FROM purchase_orders WHERE supplier_id LIKE 'STG13_%'",
        "DELETE FROM supplier_rate_sync_logs WHERE supplier_id LIKE 'STG13%'",
        "DELETE FROM supplier_api_credentials WHERE supplier_id LIKE 'STG13%'",
        "DELETE FROM offer_predictions WHERE offer_id LIKE 'STG13%'",
        "DELETE FROM rejected_opportunities WHERE offer_id LIKE 'STG13%' OR supplier_id LIKE 'STG13%' OR dest_id LIKE 'STG13%'",
        "DELETE FROM procurement_recommendations WHERE offer_id LIKE 'STG13%' OR supplier_id LIKE 'STG13%' OR dest_id LIKE 'STG13%'",
        "DELETE FROM supplier_offers WHERE offer_id LIKE 'STG13%' OR dest_id LIKE 'STG13%' OR supplier_id LIKE 'STG13%'",
        "DELETE FROM inventory_items WHERE inventory_id LIKE 'STG13%' OR dest_id LIKE 'STG13%'",
        "DELETE FROM procurement_budgets WHERE budget_code LIKE 'STG13%'",
        "DELETE FROM suppliers WHERE supplier_id LIKE 'STG13%'",
        "DELETE FROM destinations WHERE dest_id LIKE 'STG13%'",
        "DELETE FROM users WHERE email LIKE 'stg13_%'",
    ]
    with session_factory() as db:
        for sql in stmts:
            try:
                db.execute(text(sql))
                db.commit()
            except Exception:
                db.rollback()


def test_real_postgresql_concurrent_for_update_locking():
    """
    Executes multi-threaded concurrency tests directly against PostgreSQL using SELECT ... FOR UPDATE:
    1) Budget exhaustion race on Purchase Orders (strict non-negative balance).
    2) Concurrent CANARY deployment creation (single active CANARY invariant).
    3) Concurrent refresh token rotation reuse attack detection.
    4) Concurrent Supplier Portal idempotent rate pushes.
    """
    engine, SessionFactory = _get_pg_session_factory()
    _cleanup_pg(SessionFactory)
    try:
        # Verify PG connectivity cleanly
        with SessionFactory() as db:
            db.execute(text("SELECT 1"))

        uid_tag = uuid.uuid4().hex[:6].upper()
        with SessionFactory() as db:
            u = User(
                email=f"stg13_{uid_tag}@inventoryiq.com",
                full_name="Stage 13 PG User",
                hashed_password=hash_password("Stage13Pass!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            d = Destination(dest_id="STG13D", name="Stg13Dest", city="Goa", country="India", airport_code="GOI")
            s = Supplier(supplier_id="STG13_SUP", name="Stage 13 PG Supplier", supplier_type=SupplierType.HOTEL, max_spend_share_cap=1.0, is_active=True)
            db.add_all([u, d, s])
            db.flush()

            b = ProcurementBudget(
                budget_code=f"STG13_BUD_{uid_tag}",
                name="STG13 Concurrency Budget",
                scope="GLOBAL",
                period_type="MONTHLY",
                period_start=date.today(),
                period_end=date.today() + timedelta(days=30),
                total_amount_inr=Decimal("50000.00"),
                spent_amount_inr=Decimal("0.00"),
                reserved_amount_inr=Decimal("0.00"),
                status=BudgetStatus.ACTIVE,
                created_by_user_id=u.id,
            )
            off = SupplierOffer(
                offer_id="STG13_OFF1",
                supplier_id="STG13_SUP",
                dest_id="STG13D",
                inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT,
                unit_cost_inr=Decimal("10000.00"),
                list_price_inr=Decimal("14000.00"),
                currency_code="INR",
                moq=1,
                max_capacity=100,
                valid_from=date.today() - timedelta(days=1),
                valid_until=date.today() + timedelta(days=10),
                travel_date=date.today() + timedelta(days=15),
                status=OfferStatus.ACTIVE,
            )
            m1 = MLModel(
                model_type=MLModelType.HOTEL_CANCELLATION,
                version=f"stg13-{uid_tag}-1",
                algorithm="LightGBM",
                artifact_dir="data/models/hotel_cancellation",
                metrics_json={"roc_auc": 0.91},
                training_cutoff_date=date.today(),
                is_champion=False,
                model_status="TRAINED",
            )
            m2 = MLModel(
                model_type=MLModelType.HOTEL_CANCELLATION,
                version=f"stg13-{uid_tag}-2",
                algorithm="LightGBM",
                artifact_dir="data/models/hotel_cancellation",
                metrics_json={"roc_auc": 0.92},
                training_cutoff_date=date.today(),
                is_champion=False,
                model_status="TRAINED",
            )
            raw_rt = generate_secure_token()
            rt_row = RefreshToken(
                user_id=u.id,
                token_hash=hash_token(raw_rt),
                token_family_id=f"STG13_FAM_{uid_tag}",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add_all([b, off, m1, m2, rt_row])
            db.commit()
            user_id, budget_id, m1_id, m2_id = u.id, b.id, m1.id, m2.id

        # 1. Concurrent PO budget reservation race: 4 x 20,000 against 50,000 budget -> max 2 succeed
        def _place_po(_):
            with SessionFactory() as tdb:
                try:
                    po = ProcurementService.create_purchase_order(
                        tdb,
                        PurchaseOrderCreateRequest(
                            supplier_id="STG13_SUP",
                            budget_id=budget_id,
                            notes="STG13 concurrent PO",
                            lines=[PurchaseOrderCreateLine(offer_id="STG13_OFF1", ordered_qty=2, unit_cost_inr=Decimal("10000.00"))],
                        ),
                        user_id=user_id,
                    )
                    return ("OK", po.po_number)
                except BadRequestException as exc:
                    return ("BLOCKED", str(exc))

        with ThreadPoolExecutor(max_workers=4) as pool:
            po_results = list(pool.map(_place_po, range(4)))
        assert sum(1 for k, _ in po_results if k == "OK") == 2
        assert sum(1 for k, _ in po_results if k == "BLOCKED") == 2
        with SessionFactory() as db:
            b_final = db.get(ProcurementBudget, budget_id)
            assert b_final.reserved_amount_inr == Decimal("40000.00")

        # 2. Concurrent CANARY deployment creation -> exactly 1 succeeds, 1 raises ConflictException
        def _deploy_canary(mid):
            with SessionFactory() as tdb:
                try:
                    dep = MLOpsService.create_deployment(
                        tdb,
                        ModelDeploymentCreateRequest(model_id=mid, deployment_mode=DeploymentMode.CANARY, traffic_percentage=10.0, notes="STG13 canary"),
                        user_id=user_id,
                    )
                    return ("OK", dep.id)
                except ConflictException as exc:
                    return ("CONFLICT", str(exc))

        with ThreadPoolExecutor(max_workers=2) as pool:
            dep_results = list(pool.map(_deploy_canary, [m1_id, m2_id]))
        assert sum(1 for k, _ in dep_results if k == "OK") == 1
        assert sum(1 for k, _ in dep_results if k == "CONFLICT") == 1

        # 3. Concurrent refresh token rotation -> at most 1 succeeds, rival fails UnauthorizedException
        def _rotate(_):
            with SessionFactory() as tdb:
                try:
                    AuthService.rotate_refresh_token(tdb, raw_rt)
                    return "OK"
                except AuthenticationError:
                    return "REJECTED"

        with ThreadPoolExecutor(max_workers=2) as pool:
            rt_results = list(pool.map(_rotate, range(2)))
        assert rt_results.count("OK") == 1
        assert rt_results.count("REJECTED") == 1

        # 4. Supplier portal concurrent idempotent push
        SupplierPortalService.reset_rate_limits()
        with SessionFactory() as db:
            cred = SupplierPortalService.create_credential(
                db,
                SupplierCredentialCreateRequest(
                    supplier_id="STG13_SUP",
                    label="STG13 Key",
                    scopes=["rates:write"],
                    rate_limit_per_minute=100,
                    expires_in_days=30,
                ),
                user_id=user_id,
            )
            cred_id = cred.id

        idemp = f"STG13_IDEMP_{uid_tag}"
        push_req = SupplierRatePushRequest(
            idempotency_key=idemp,
            offers=[SupplierRatePushOfferItem(
                offer_id="STG13_OFF1", dest_id="STG13D", inventory_category=InventoryCategory.HOTEL,
                unit_type=UnitType.ROOM_NIGHT, unit_cost=Decimal("9500.00"), list_price=Decimal("13500.00"),
                currency_code="INR", moq=1, max_capacity=100,
                valid_from=date.today() - timedelta(days=1), valid_until=date.today() + timedelta(days=10),
                travel_date=date.today() + timedelta(days=15),
            )],
        )

        def _push(_):
            with SessionFactory() as tdb:
                c_obj = tdb.get(SupplierApiCredential, cred_id)
                res = SupplierPortalService.push_rates_and_availability(tdb, c_obj, push_req, header_idempotency_key=idemp)
                return ("OK", res.id)

        with ThreadPoolExecutor(max_workers=3) as pool:
            push_res = list(pool.map(_push, range(3)))
        ok_ids = {rid for k, rid in push_res if k == "OK"}
        assert len(ok_ids) == 1  # Every replay/race points to single canonical log record

    finally:
        _cleanup_pg(SessionFactory)
        engine.dispose()
