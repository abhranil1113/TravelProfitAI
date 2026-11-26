"""
ml_engine/adapters.py

Integration adapters connecting the central ML Engine with the Optimization Engine
and backend services while preserving existing contracts.
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

from ml_engine.engine import MLEngine
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.demand_forecasting.forecast_service import DemandForecastService
from ml_engine.price_prediction.price_prediction_service import PricePredictionService
from ml_engine.risk_prediction.risk_prediction_service import RiskPredictionService
from ml_engine.inventory_forecasting.inventory_forecast_service import InventoryForecastService
from ml_engine.schemas import PredictionTask, PredictionRequest

logger = logging.getLogger(__name__)


class OptimizationMLAdapter:
    """
    Adapter providing standard optimization prediction interfaces backed by the ML Engine.
    Allows candidate_builder and solvers to interact seamlessly with centralized ML models.
    """

    def __init__(
        self,
        engine: Optional[MLEngine] = None,
        registry: Optional[ModelArtifactRegistry] = None,
        searches_df: Optional[pd.DataFrame] = None,
        optimization_timestamp: Optional[str] = None,
    ):
        self.registry = registry or ModelArtifactRegistry()
        self.engine = engine or MLEngine.create_default(
            registry=self.registry,
            searches_df=searches_df,
            optimization_timestamp=optimization_timestamp,
        )

        self.demand_service = DemandForecastService(
            registry=self.registry,
            searches_df=searches_df,
            optimization_timestamp=optimization_timestamp,
        )
        self.price_service = PricePredictionService(registry=self.registry)
        self.risk_service = RiskPredictionService(registry=self.registry)
        self.inventory_service = InventoryForecastService(registry=self.registry)

    def predict_demand_search_volume(self, destination_id: str, inventory_type: str) -> Optional[float]:
        """Maps demand forecasting query to centralized engine/service."""
        return self.demand_service.predict_search_volume(destination_id, inventory_type)

    def predict_flight_ceiling_price(self, offer_dict: Dict[str, Any]) -> Optional[float]:
        """Maps flight price ceiling query to centralized engine/service."""
        return self.price_service.predict_market_price(offer_dict)

    def predict_hotel_cancellation_risk(self, offer_dict: Dict[str, Any]) -> Optional[float]:
        """Maps hotel cancellation probability query to centralized engine/service."""
        return self.risk_service.predict_cancellation_probability(offer_dict)

    def predict_inventory_available_quantity(self, snapshot_dict: Dict[str, Any]) -> Optional[float]:
        """Maps inventory depletion query to centralized engine/service."""
        return self.inventory_service.predict_future_available_quantity(snapshot_dict)
