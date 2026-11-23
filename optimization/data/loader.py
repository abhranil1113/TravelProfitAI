"""
optimization/data/loader.py

Safe, point-in-time data loading service for Phase 5 procurement optimization.
"""

import os
from typing import Dict, Any, Optional
import pandas as pd
from optimization.exceptions import OptimizationError


class DatasetLoader:
    """Loads cleaned Phase 1 processed parquet tables required for optimization."""

    DEFAULT_PATHS = {
        "supplier_offers": "data/processed/supplier_offers/cleaned_supplier_offers.parquet",
        "inventory_availability": "data/processed/inventory/cleaned_inventory_availability.parquet",
        "customer_searches": "data/processed/searches/cleaned_customer_search_events.parquet",
        "market_signals": "data/processed/market_signals/cleaned_market_seasonal_signals.parquet",
    }

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or "."

    def _resolve_path(self, relative_path: str) -> str:
        return os.path.join(self.base_dir, relative_path)

    def load_supplier_offers(self) -> pd.DataFrame:
        path = self._resolve_path(self.DEFAULT_PATHS["supplier_offers"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing supplier offers dataset at {path}")
        df = pd.read_parquet(path)
        return df

    def load_inventory_availability(self) -> pd.DataFrame:
        path = self._resolve_path(self.DEFAULT_PATHS["inventory_availability"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing inventory availability dataset at {path}")
        df = pd.read_parquet(path)
        return df

    def load_customer_searches(self) -> pd.DataFrame:
        path = self._resolve_path(self.DEFAULT_PATHS["customer_searches"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing customer search events dataset at {path}")
        df = pd.read_parquet(path)
        return df

    def load_market_signals(self) -> pd.DataFrame:
        path = self._resolve_path(self.DEFAULT_PATHS["market_signals"])
        if not os.path.exists(path):
            raise OptimizationError(f"Missing market seasonal signals dataset at {path}")
        df = pd.read_parquet(path)
        return df
