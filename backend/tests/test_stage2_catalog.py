from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import hash_password
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.models.schema import (
    Base,
    Destination,
    DestinationDailyMetrics,
    InventoryCategory,
    InventoryItem,
    Supplier,
    SupplierContact,
    SupplierOffer,
    SupplierType,
    UnitType,
    User,
    UserRole,
)

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

def _json_serializer(obj):
    return json.dumps(obj, default=str)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    json_serializer=_json_serializer,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS uq_platform_config_single_active"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_config_single_active ON platform_optimization_configs (is_active) WHERE is_active = 1"))
        conn.execute(text("DROP INDEX IF EXISTS uq_supplier_primary_contact"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_primary_contact ON supplier_contacts (supplier_id) WHERE is_primary = 1"))
        conn.execute(text("DROP INDEX IF EXISTS uq_champion_model_per_type"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_champion_model_per_type ON ml_models (model_type) WHERE is_champion = 1"))
        conn.commit()
    db = TestingSessionLocal()
    try:
        admin = User(
            email="admin@inventoryiq.com",
            full_name="Admin Test",
            hashed_password=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        pm = User(
            email="pm@inventoryiq.com",
            full_name="PM Test",
            hashed_password=hash_password("PmPass123!"),
            role=UserRole.PROCUREMENT_MANAGER,
            is_active=True,
        )
        db.add_all([admin, pm])
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_stage2_destinations_suppliers_inventory_offers(client, db_session):
    # 1. Login Admin
    login_res = client.post("/api/v1/auth/login", json={
        "email": "admin@inventoryiq.com",
        "password": "AdminPass123!"
    })
    admin_auth = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 2. Destinations (Endpoints 20-26)
    create_dest = client.post("/api/v1/destinations", headers=admin_auth, json={
        "dest_id": "DEST_GOA",
        "name": "Goa Beachfront",
        "city": "Goa",
        "country": "India",
        "airport_code": "GOI",
        "search_volume_ceiling": 50000,
        "is_active": True
    })
    assert create_dest.status_code == 201
    assert create_dest.json()["dest_id"] == "DEST_GOA"

    # List destinations
    list_dest = client.get("/api/v1/destinations", headers=admin_auth)
    assert list_dest.status_code == 200
    assert list_dest.json()["total"] >= 1

    # Get destination detail
    detail_dest = client.get("/api/v1/destinations/DEST_GOA", headers=admin_auth)
    assert detail_dest.status_code == 200
    assert detail_dest.json()["city"] == "Goa"

    # Update destination
    patch_dest = client.patch("/api/v1/destinations/DEST_GOA", headers=admin_auth, json={
        "search_volume_ceiling": 60000
    })
    assert patch_dest.status_code == 200
    assert patch_dest.json()["search_volume_ceiling"] == 60000

    # Search velocity
    vel_res = client.get("/api/v1/destinations/DEST_GOA/search-velocity", headers=admin_auth)
    assert vel_res.status_code == 200
    assert "rolling_7d_searches" in vel_res.json()

    # 3. Suppliers & Contacts (Endpoints 27-39)
    create_sup = client.post("/api/v1/suppliers", headers=admin_auth, json={
        "supplier_id": "SUP_TAJ",
        "name": "Taj Hotels & Resorts",
        "supplier_type": "HOTEL",
        "fulfillment_rate": 0.98,
        "avg_lead_time_days": 3.5,
        "max_portfolio_share": 0.30
    })
    assert create_sup.status_code == 201
    assert create_sup.json()["supplier_id"] == "SUP_TAJ"

    # List suppliers
    list_sup = client.get("/api/v1/suppliers", headers=admin_auth)
    assert list_sup.status_code == 200
    assert list_sup.json()["total"] >= 1

    # Add Contacts
    c1 = client.post("/api/v1/suppliers/SUP_TAJ/contacts", headers=admin_auth, json={
        "name": "Rajesh Sharma",
        "contact_role": "Key Account Manager",
        "email": "rajesh@tajhotels.com",
        "phone": "+919876543210",
        "is_primary": True
    })
    assert c1.status_code == 201
    c1_id = c1.json()["id"]

    c2 = client.post("/api/v1/suppliers/SUP_TAJ/contacts", headers=admin_auth, json={
        "name": "Priya Nair",
        "contact_role": "Finance Coordinator",
        "email": "priya@tajhotels.com",
        "is_primary": False
    })
    assert c2.status_code == 201
    c2_id = c2.json()["id"]

    # Reassign Primary Contact
    reassign_res = client.post(f"/api/v1/supplier-contacts/{c2_id}/set-primary", headers=admin_auth)
    assert reassign_res.status_code == 200
    assert reassign_res.json()["is_primary"] is True

    # Verify c1 is no longer primary
    contacts_list = client.get("/api/v1/suppliers/SUP_TAJ/contacts", headers=admin_auth)
    assert contacts_list.status_code == 200
    c_map = {c["id"]: c["is_primary"] for c in contacts_list.json()}
    assert c_map[c2_id] is True
    assert c_map[c1_id] is False

    # 4. Inventory Items & Snapshots (Endpoints 40-47)
    create_inv = client.post("/api/v1/inventory-items", headers=admin_auth, json={
        "inventory_id": "HOTEL_TAJ_EXOTICA",
        "category": "HOTEL",
        "unit_type": "ROOM_NIGHT",
        "dest_id": "DEST_GOA",
        "name": "Taj Exotica Resort & Spa",
        "reference_code": "TAJ-EX-001",
        "star_rating": 5.0,
        "total_capacity": 140
    })
    assert create_inv.status_code == 201

    # Ingest Snapshot
    snap_res = client.post("/api/v1/inventory-snapshots", headers=admin_auth, json={
        "inventory_id": "HOTEL_TAJ_EXOTICA",
        "snapshot_date": str(date.today()),
        "available_units": 45,
        "depletion_velocity": 3.2,
        "avg_selling_price_inr": "12500.00",
        "historical_cancellation_rate": 0.12
    })
    assert snap_res.status_code == 201

    # Get inventory detail with snapshot
    inv_detail = client.get("/api/v1/inventory-items/HOTEL_TAJ_EXOTICA", headers=admin_auth)
    assert inv_detail.status_code == 200
    assert inv_detail.json()["latest_snapshot"]["available_units"] == 45

    # 5. Supplier Offers (Endpoints 48-54)
    offer_payload = {
        "offer_id": "OFFER_TAJ_GOA_001",
        "supplier_id": "SUP_TAJ",
        "inventory_id": "HOTEL_TAJ_EXOTICA",
        "dest_id": "DEST_GOA",
        "inventory_category": "HOTEL",
        "unit_type": "ROOM_NIGHT",
        "available_qty": 30,
        "moq": 5,
        "cost_per_unit_inr": "7800.00",
        "currency": "INR",
        "travel_date": str(date.today() + timedelta(days=14)),
        "valid_until": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "refundable": True,
        "refund_penalty_pct": 0.10,
        "status": "ACTIVE"
    }
    create_offer = client.post("/api/v1/supplier-offers", headers=admin_auth, json=offer_payload)
    assert create_offer.status_code == 201
    assert create_offer.json()["offer_id"] == "OFFER_TAJ_GOA_001"

    # List offers
    list_offers = client.get("/api/v1/supplier-offers?supplier=SUP_TAJ", headers=admin_auth)
    assert list_offers.status_code == 200
    assert list_offers.json()["total"] >= 1

    # Expire offer
    exp_res = client.post("/api/v1/supplier-offers/OFFER_TAJ_GOA_001/expire", headers=admin_auth)
    assert exp_res.status_code == 200
    assert exp_res.json()["status"] == "EXPIRED"

    # Bulk Import CSV
    csv_data = """offer_id,supplier_id,inventory_id,dest_id,inventory_category,unit_type,available_qty,moq,cost_per_unit_inr,currency,travel_date,valid_until,refundable
OFFER_CSV_001,SUP_TAJ,HOTEL_TAJ_EXOTICA,DEST_GOA,HOTEL,ROOM_NIGHT,20,4,8200.00,INR,2026-12-01,2026-11-30T23:59:59,true
OFFER_CSV_002,SUP_TAJ,HOTEL_TAJ_EXOTICA,DEST_GOA,HOTEL,ROOM_NIGHT,15,3,8100.00,INR,2026-12-02,2026-11-30T23:59:59,false
"""
    files = {"file": ("offers.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    import_res = client.post("/api/v1/supplier-offers/bulk-import", headers=admin_auth, files=files)
    assert import_res.status_code in (200, 201)
    assert import_res.json()["rows_imported"] == 2
