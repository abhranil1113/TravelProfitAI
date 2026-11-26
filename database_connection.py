from __future__ import annotations

"""
TBO InventoryIQ — Database Connection and Connection Pool Interface.

This module provides:
- Initialized SQLAlchemy Engine with production connection pooling (QueuePool).
- SessionLocal sessionmaker for transactional sessions.
- get_db() dependency generator for FastAPI routes.
- check_db_connection() and get_pool_status() diagnostics utilities.
- Interactive CLI validation when executed directly (`python database_connection.py`).
"""

import sys
import os

# Add project root and backend to python path
sys.path.insert(0, os.path.abspath("."))

from backend.app.database.connection import (
    engine,
    SessionLocal,
    get_db,
    check_db_connection,
    get_pool_status,
)
from backend.app.models.schema import Base

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "check_db_connection",
    "get_pool_status",
    "Base",
]


def print_database_report():
    print("=" * 70)
    print("  TBO INVENTORYIQ — DATABASE CONNECTION & POOL STATUS")
    print("=" * 70)

    status = check_db_connection()
    print(f"Connection Status : {status['status'].upper()}")
    print(f"Backend Dialect   : {status['url_scheme']}")
    print(f"Database Name     : {status['database']}")
    if status.get("server_version"):
        print(f"Server Version    : {status['server_version']}")
    
    print("\nConnection Pool Configuration & Runtime Metrics:")
    pool_metrics = status["pool"]
    for k, v in pool_metrics.items():
        print(f"  - {k:<22}: {v}")

    if status["status"] == "connected":
        from sqlalchemy import inspect
        insp = inspect(engine)
        tables = sorted(insp.get_table_names())
        print(f"\nMigrated Tables in Database ({len(tables)} tables):")
        for idx, tbl in enumerate(tables, start=1):
            print(f"  {idx:>2}. {tbl}")
    else:
        print(f"\nConnection Error: {status.get('error')}")

    print("=" * 70)


if __name__ == "__main__":
    print_database_report()
