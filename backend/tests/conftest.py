from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import get_settings
from backend.app.core.security import create_access_token, hash_password
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.models.schema import Base, User, UserRole

settings = get_settings()

# Isolated in-memory SQLite database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"


def _json_serializer(obj):
    return json.dumps(obj, default=str)


test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    json_serializer=_json_serializer,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    """Provides a clean, isolated in-memory database session for each test."""
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS uq_platform_config_single_active"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_config_single_active ON platform_optimization_configs (is_active) WHERE is_active = 1"))
        conn.execute(text("DROP INDEX IF EXISTS uq_supplier_primary_contact"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_primary_contact ON supplier_contacts (supplier_id) WHERE is_primary = 1"))
        conn.execute(text("DROP INDEX IF EXISTS uq_champion_model_per_type"))
        conn.execute(text("DROP INDEX IF EXISTS uq_ml_model_single_champion"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ml_model_single_champion ON ml_models (model_type) WHERE is_champion = 1"))
        conn.commit()
    session: Session = TestingSessionLocal()
    try:
        # Seed test users
        admin = User(
            id=1,
            email="admin@inventoryiq.com",
            full_name="System Admin",
            hashed_password=hash_password("AdminSecurePass123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        pm = User(
            id=2,
            email="pm@inventoryiq.com",
            full_name="Procurement Manager",
            hashed_password=hash_password("PMSecurePass123!"),
            role=UserRole.PROCUREMENT_MANAGER,
            is_active=True,
        )
        analyst = User(
            id=3,
            email="analyst@inventoryiq.com",
            full_name="Data Analyst",
            hashed_password=hash_password("AnalystSecurePass123!"),
            role=UserRole.ANALYST,
            is_active=True,
        )
        inactive = User(
            id=4,
            email="inactive@inventoryiq.com",
            full_name="Inactive User",
            hashed_password=hash_password("InactivePass123!"),
            role=UserRole.ANALYST,
            is_active=False,
        )
        session.add_all([admin, pm, analyst, inactive])
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with isolated test database session override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_headers():
    token = create_access_token(subject="1", role="ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def pm_headers():
    token = create_access_token(subject="2", role="PROCUREMENT_MANAGER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def analyst_headers():
    token = create_access_token(subject="3", role="ANALYST")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def seeded_optimization_db(db):
    """Seeds realistic multi-supplier, multi-destination catalog rows for real optimization solver tests."""
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal
    from backend.app.models.schema import (
        CustomerSearchEvent,
        Destination,
        InventoryCategory,
        InventoryItem,
        InventorySnapshot,
        MarketSignal,
        OfferStatus,
        Supplier,
        SupplierOffer,
        SupplierType,
        UnitType,
    )

    today = date.today()
    now_utc = datetime.now(timezone.utc) - timedelta(hours=1)

    dests = [
        Destination(dest_id="GOA", name="Goa", city="Panaji", country="India", airport_code="GOI", search_volume_ceiling=50000),
        Destination(dest_id="DEL", name="Delhi", city="Delhi", country="India", airport_code="DEL", search_volume_ceiling=80000),
        Destination(dest_id="BOM", name="Mumbai", city="Mumbai", country="India", airport_code="BOM", search_volume_ceiling=75000),
        Destination(dest_id="BLR", name="Bangalore", city="Bangalore", country="India", airport_code="BLR", search_volume_ceiling=65000),
        Destination(dest_id="HYD", name="Hyderabad", city="Hyderabad", country="India", airport_code="HYD", search_volume_ceiling=45000),
    ]
    supps = [
        Supplier(supplier_id="SUP_HTL_1", name="Taj Hotels", supplier_type=SupplierType.HOTEL, fulfillment_rate=0.98, max_spend_share_cap=0.50, is_active=True),
        Supplier(supplier_id="SUP_HTL_2", name="Oberoi Group", supplier_type=SupplierType.HOTEL, fulfillment_rate=0.97, max_spend_share_cap=0.50, is_active=True),
        Supplier(supplier_id="SUP_HTL_3", name="Marriott India", supplier_type=SupplierType.HOTEL, fulfillment_rate=0.96, max_spend_share_cap=0.50, is_active=True),
        Supplier(supplier_id="SUP_FLT_1", name="IndiGo Wholesale", supplier_type=SupplierType.FLIGHT, fulfillment_rate=0.99, max_spend_share_cap=0.50, is_active=True),
        Supplier(supplier_id="SUP_FLT_2", name="Vistara Corp", supplier_type=SupplierType.FLIGHT, fulfillment_rate=0.98, max_spend_share_cap=0.50, is_active=True),
    ]
    db.add_all(dests + supps)
    db.flush()

    specs = [
        ("OFF_SEED_H1", "SUP_HTL_1", "INV_H1", None, "GOA", InventoryCategory.HOTEL, UnitType.ROOM_NIGHT, "3000.00", "4500.00", 2, 100),
        ("OFF_SEED_H2", "SUP_HTL_2", "INV_H2", None, "DEL", InventoryCategory.HOTEL, UnitType.ROOM_NIGHT, "3200.00", "4800.00", 2, 100),
        ("OFF_SEED_H3", "SUP_HTL_3", "INV_H3", None, "BOM", InventoryCategory.HOTEL, UnitType.ROOM_NIGHT, "2800.00", "4200.00", 2, 100),
        ("OFF_SEED_F1", "SUP_FLT_1", "INV_F1", "HYD", "DEL", InventoryCategory.FLIGHT, UnitType.SEAT, "3500.00", "5200.00", 2, 100),
        ("OFF_SEED_F2", "SUP_FLT_2", "INV_F2", "DEL", "BLR", InventoryCategory.FLIGHT, UnitType.SEAT, "4000.00", "5900.00", 2, 100),
        ("OFF_SEED_F3", "SUP_FLT_1", "INV_F3", "BOM", "GOA", InventoryCategory.FLIGHT, UnitType.SEAT, "2900.00", "4400.00", 2, 100),
    ]
    travel_dt = today + timedelta(days=20)
    for oid, sid, iid, orig, dst, cat, utype, cost, price, moq, cap in specs:
        db.add(InventoryItem(
            inventory_id=iid, inventory_category=cat, unit_type=utype,
            dest_id=dst, origin_dest_id=orig, is_active=True,
        ))
        db.flush()
        db.add(InventorySnapshot(
            inventory_id=iid, supplier_id=sid, inventory_category=cat,
            travel_date=travel_dt, snapshot_at=now_utc,
            total_units=120, booked_units=20, available_units=cap,
        ))
        db.add(SupplierOffer(
            offer_id=oid, supplier_id=sid, inventory_id=iid,
            dest_id=dst, origin_dest_id=orig, inventory_category=cat, unit_type=utype,
            unit_cost_inr=Decimal(cost), list_price_inr=Decimal(price),
            currency_code="INR", moq=moq, max_capacity=cap,
            valid_from=today - timedelta(days=5), valid_until=today + timedelta(days=15),
            travel_date=travel_dt, status=OfferStatus.ACTIVE,
            customer_refund_rate_rc=0.5, resale_probability_f=0.4,
            resale_discount_delta=0.85, supplier_refund_unsold_r_u=0.2,
            supplier_refund_cancelled_r_c=0.3, salvage_rate_s=0.1,
        ))

    for d_idx, dst in enumerate(["GOA", "DEL", "BOM", "BLR"]):
        for cat in (InventoryCategory.HOTEL, InventoryCategory.FLIGHT):
            for day_off in range(3):
                for s_idx in range(15):
                    db.add(CustomerSearchEvent(
                        search_id=f"SRCH_{dst}_{cat.value}_{day_off}_{s_idx}_{d_idx}",
                        search_date=today - timedelta(days=day_off),
                        travel_date=travel_dt,
                        dest_id=dst,
                        inventory_category=cat,
                        travellers_count=4,
                        rooms_count=2 if cat == InventoryCategory.HOTEL else None,
                        search_price=Decimal("4600.00"),
                        currency_code="INR",
                        clicked=True,
                        booking_completed=(s_idx < 10),
                    ))
        db.add(MarketSignal(
            dest_id=dst, signal_date=travel_dt, signal_type="PEAK_DEMAND",
            event_name=f"SeasonalPeak_{dst}", demand_multiplier=1.25, is_peak_season=True,
        ))

    db.commit()
    return db


@pytest.fixture(scope="function")
def worker_headers():
    return {"X-Worker-Token": settings.WORKER_SECRET_TOKEN}
