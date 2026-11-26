from __future__ import annotations

import json
import logging
from typing import Any, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

db_url = settings.DATABASE_URL
connect_args: Dict[str, Any] = {}
engine_kwargs: Dict[str, Any] = {
    "pool_pre_ping": True,
    "echo": getattr(settings, "DB_ECHO", False),
}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
elif db_url.startswith("postgresql+psycopg://"):
    try:
        import psycopg
    except ImportError:
        try:
            import psycopg2
            db_url = db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        except ImportError:
            pass
    engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": getattr(settings, "DB_POOL_SIZE", 10),
        "max_overflow": getattr(settings, "DB_MAX_OVERFLOW", 20),
        "pool_timeout": getattr(settings, "DB_POOL_TIMEOUT", 30),
        "pool_recycle": getattr(settings, "DB_POOL_RECYCLE", 1800),
    })
elif db_url.startswith("postgresql"):
    engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": getattr(settings, "DB_POOL_SIZE", 10),
        "max_overflow": getattr(settings, "DB_MAX_OVERFLOW", 20),
        "pool_timeout": getattr(settings, "DB_POOL_TIMEOUT", 30),
        "pool_recycle": getattr(settings, "DB_POOL_RECYCLE", 1800),
    })


def _json_serializer(obj: Any) -> str:
    return json.dumps(obj, default=str)


engine_kwargs["json_serializer"] = _json_serializer

engine = create_engine(
    db_url,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for providing a transactional database session per request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
