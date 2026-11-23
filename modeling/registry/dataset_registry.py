"""
TBO InventoryIQ - Extensible Dataset Registry (Phase 4)
Provides a centralized, extensible catalog of registered feature datasets,
their schemas, storage formats, and entity keys.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

from modeling.config import FEATURES_DATA_DIR

logger = logging.getLogger(__name__)


@dataclass
class DatasetMetadata:
    """Metadata describing a registered tabular or time-series dataset."""
    name: str
    file_path: Path
    file_format: str = "parquet"  # 'parquet' or 'csv'
    description: str = ""
    entity_id_columns: List[str] = field(default_factory=list)
    timestamp_column: Optional[str] = None
    default_grain: Optional[List[str]] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.file_path = Path(self.file_path)
        if not self.file_path.exists():
            logger.warning(f"Registered dataset '{self.name}' path does not currently exist: {self.file_path}")


class DatasetRegistry:
    """
    Centralized registry for managing datasets in the ML framework.
    Allows new datasets to be registered dynamically without modifying core pipeline code.
    """
    _instance: Optional["DatasetRegistry"] = None

    def __new__(cls) -> "DatasetRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry: Dict[str, DatasetMetadata] = {}
            cls._instance._initialize_default_datasets()
        return cls._instance

    def _initialize_default_datasets(self) -> None:
        """Pre-registers all verified Phase 3 feature datasets."""
        defaults = [
            DatasetMetadata(
                name="hotel_cancellation_features",
                file_path=FEATURES_DATA_DIR / "hotel" / "hotel_cancellation_features.parquet",
                file_format="parquet",
                description="Hotel booking cancellation risk dataset with pre-booking attributes.",
                entity_id_columns=[],
                timestamp_column="booking_date",
                default_grain=["booking_date"],
                tags=["hotel", "cancellation", "classification"],
            ),
            DatasetMetadata(
                name="flight_price_features",
                file_path=FEATURES_DATA_DIR / "flight_prices" / "flight_price_features.parquet",
                file_format="parquet",
                description="Domestic Indian flight prices across advance booking horizons.",
                entity_id_columns=["route"],
                timestamp_column=None,
                default_grain=["route", "days_left"],
                tags=["flights", "pricing", "regression"],
            ),
            DatasetMetadata(
                name="customer_demand_features",
                file_path=FEATURES_DATA_DIR / "customer_demand" / "customer_demand_features.parquet",
                file_format="parquet",
                description="Customer travel search events dataset with temporal lead days.",
                entity_id_columns=["user_id", "destination_id"],
                timestamp_column="search_date",
                default_grain=["destination_id", "inventory_type", "search_date"],
                tags=["demand", "searches", "forecasting"],
            ),
            DatasetMetadata(
                name="inventory_features",
                file_path=FEATURES_DATA_DIR / "inventory" / "inventory_features.parquet",
                file_format="parquet",
                description="Inventory availability snapshots tracking bookable capacity over time.",
                entity_id_columns=["inventory_id"],
                timestamp_column="snapshot_date",
                default_grain=["inventory_id", "travel_date", "snapshot_date"],
                tags=["inventory", "availability", "forecasting"],
            ),
            DatasetMetadata(
                name="flight_operations_features",
                file_path=FEATURES_DATA_DIR / "flights" / "flight_operations_features.parquet",
                file_format="parquet",
                description="Flight operational delay and cancellation records (prototype sample).",
                entity_id_columns=["airline", "flight_number"],
                timestamp_column=None,
                default_grain=["airline", "route"],
                tags=["operations", "delays", "prototype"],
            ),
            DatasetMetadata(
                name="supplier_profitability_features",
                file_path=FEATURES_DATA_DIR / "supplier" / "supplier_profitability_features.parquet",
                file_format="parquet",
                description="Supplier contract offers, costs, and terms (decision support).",
                entity_id_columns=["offer_id", "supplier_id"],
                timestamp_column="travel_date",
                default_grain=["supplier_id", "destination_id"],
                tags=["supplier", "procurement", "analytics"],
            ),
            DatasetMetadata(
                name="market_demand_features",
                file_path=FEATURES_DATA_DIR / "market" / "market_demand_features.parquet",
                file_format="parquet",
                description="Market seasonality, holidays, and weather indicators (feature store).",
                entity_id_columns=["destination_id"],
                timestamp_column="travel_date",
                default_grain=["destination_id", "travel_date"],
                tags=["market", "seasonality", "features"],
            ),
            DatasetMetadata(
                name="destination_demand_supply_features",
                file_path=FEATURES_DATA_DIR / "market" / "destination_demand_supply_features.parquet",
                file_format="parquet",
                description="Synthesized destination demand-to-supply ratios (optimization inputs).",
                entity_id_columns=["destination_id", "inventory_type"],
                timestamp_column=None,
                default_grain=["destination_id", "inventory_type"],
                tags=["optimization", "ratios"],
            ),
        ]
        for meta in defaults:
            self._registry[meta.name] = meta

    def register(self, metadata: DatasetMetadata, overwrite: bool = False) -> None:
        """
        Registers a new dataset. Rejects duplicate registrations unless overwrite=True.
        """
        if metadata.name in self._registry and not overwrite:
            raise ValueError(
                f"Dataset '{metadata.name}' is already registered. Set overwrite=True to update."
            )
        if not metadata.file_path.exists():
            raise FileNotFoundError(f"Cannot register dataset: file not found at {metadata.file_path}")

        self._registry[metadata.name] = metadata
        logger.info(f"Registered dataset: '{metadata.name}' ({metadata.file_path})")

    def get(self, name: str) -> DatasetMetadata:
        """Retrieves metadata for a registered dataset."""
        if name not in self._registry:
            raise KeyError(
                f"Dataset '{name}' is not registered. Available: {list(self._registry.keys())}"
            )
        return self._registry[name]

    def exists(self, name: str) -> bool:
        """Checks if a dataset is registered."""
        return name in self._registry

    def unregister(self, name: str) -> bool:
        """Unregisters a dataset."""
        if name in self._registry:
            del self._registry[name]
            logger.info(f"Unregistered dataset: '{name}'")
            return True
        return False

    def list_datasets(self) -> List[str]:
        """Lists all registered dataset names."""
        return list(self._registry.keys())

    def reset(self) -> None:
        """Resets the registry to default datasets."""
        self._registry.clear()
        self._initialize_default_datasets()
