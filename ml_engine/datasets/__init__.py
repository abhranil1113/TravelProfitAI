"""
ml_engine/datasets/__init__.py

Entrypoint for ML dataset wrappers and schema-aware data loaders.
"""

from ml_engine.datasets.cancellation_dataset import CancellationDataset
from ml_engine.datasets.flight_demand_dataset import FlightDemandDataset
from ml_engine.datasets.hotel_demand_dataset import HotelDemandDataset
from ml_engine.datasets.price_dataset import PriceDataset

__all__ = [
    "CancellationDataset",
    "FlightDemandDataset",
    "HotelDemandDataset",
    "PriceDataset",
]
