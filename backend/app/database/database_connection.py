from __future__ import annotations

"""
Alias module for database connection interface.
Re-exports from backend.app.database.connection.
"""

from backend.app.database.connection import (
    engine,
    SessionLocal,
    get_db,
    check_db_connection,
    get_pool_status,
)

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "check_db_connection",
    "get_pool_status",
]
