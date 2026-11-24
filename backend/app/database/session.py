from __future__ import annotations

import json
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

db_url = settings.DATABASE_URL
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif db_url.startswith("postgresql+psycopg://"):
    try:
        import psycopg
    except ImportError:
        try:
            import psycopg2
            db_url = db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        except ImportError:
            pass


def _json_serializer(obj):
    return json.dumps(obj, default=str)


engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
    json_serializer=_json_serializer,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
