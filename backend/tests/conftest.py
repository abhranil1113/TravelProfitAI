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
def worker_headers():
    return {"X-Worker-Token": settings.WORKER_SECRET_TOKEN}
