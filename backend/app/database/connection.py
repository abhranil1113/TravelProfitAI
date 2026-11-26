from __future__ import annotations

import logging
from typing import Any, Dict
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.database.session import engine, SessionLocal, get_db
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def check_db_connection() -> Dict[str, Any]:
    """
    Validates database connectivity and returns engine and pool diagnostics.
    """
    settings = get_settings()
    pool_info = get_pool_status(engine)
    result = {
        "status": "unknown",
        "url_scheme": engine.url.get_backend_name(),
        "database": engine.url.database,
        "pool": pool_info,
        "server_version": None,
        "error": None,
    }

    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT 1;")).fetchone()
            if row and row[0] == 1:
                result["status"] = "connected"
            
            try:
                ver_row = conn.execute(text("SELECT version();")).fetchone()
                if ver_row:
                    result["server_version"] = ver_row[0]
            except Exception:
                pass
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        logger.error("Database connection check failed: %s", exc)

    return result


def get_pool_status(eng: Engine | None = None) -> Dict[str, Any]:
    """
    Returns current connection pool metrics from the SQLAlchemy engine.
    """
    target_engine = eng or engine
    pool = target_engine.pool
    pool_class = pool.__class__.__name__

    stats: Dict[str, Any] = {
        "pool_class": pool_class,
        "pool_pre_ping": True,
    }

    if hasattr(pool, "size"):
        stats["pool_size"] = pool.size()
    if hasattr(pool, "checkedin"):
        stats["checked_in"] = pool.checkedin()
    if hasattr(pool, "checkedout"):
        stats["checked_out"] = pool.checkedout()
    if hasattr(pool, "overflow"):
        stats["overflow"] = pool.overflow()
    if hasattr(pool, "_recycle"):
        stats["pool_recycle_seconds"] = pool._recycle
    if hasattr(pool, "_timeout"):
        stats["pool_timeout_seconds"] = pool._timeout

    return stats


__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "check_db_connection",
    "get_pool_status",
]
