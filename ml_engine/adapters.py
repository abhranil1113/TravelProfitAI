"""
ml_engine/adapters.py

Integration adapters connecting the central ML Engine with the Optimization Engine
and backend services while preserving existing contracts.
Routes all requests through MLEngine to ensure centralized validation, metrics, and timeouts.
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

from ml_engine.engine import MLEngine
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.schemas import PredictionTask, PredictionRequest, InferenceStatus

logger = logging.getLogger(__name__)


class OptimizationMLAdapter:
    """
    Adapter providing standard optimization prediction interfaces backed by the central ML Engine.
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
        self._owns_engine = (engine is None)
        self.engine = engine or MLEngine.create_default(
            registry=self.registry,
            searches_df=searches_df,
            optimization_timestamp=optimization_timestamp,
        )

    def close(self) -> None:
        """Shuts down underlying MLEngine if owned by this adapter instance."""
        if getattr(self, "_owns_engine", False) and self.engine is not None:
            self.engine.shutdown(wait=False)

    def __enter__(self) -> "OptimizationMLAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def predict_demand_search_volume(self, destination_id: str, inventory_type: str) -> Optional[float]:
        """
        Maps demand forecasting query to centralized engine.
        Returns None for unsupported or missing history.
        """
        req = PredictionRequest(
            task=PredictionTask.DEMAND_FORECASTING,
            features={
                "destination_id": str(destination_id),
                "inventory_type": str(inventory_type).lower(),
            },
            entity_id=f"dest_{destination_id}_{inventory_type}",
        )
        res = self.engine.predict(req)
        if res.status == InferenceStatus.SUCCESS and res.prediction is not None:
            return float(res.prediction)
        return None

    def predict_flight_ceiling_price(self, offer_dict: Dict[str, Any]) -> Optional[float]:
        """
        Maps flight price ceiling query to centralized engine.
        Returns None for unsupported routes, carriers, or missing attributes.
        """
        req = PredictionRequest(
            task=PredictionTask.FLIGHT_PRICE,
            features=offer_dict,
            entity_id=str(offer_dict.get("offer_id", "flight_offer")),
        )
        res = self.engine.predict(req)
        if res.status == InferenceStatus.SUCCESS and res.prediction is not None:
            return float(res.prediction)
        return None

    def predict_hotel_cancellation_risk(self, offer_dict: Dict[str, Any]) -> Optional[float]:
        """
        Maps hotel cancellation probability query to centralized engine.
        Returns None when passenger booking cohort fields are absent.
        """
        req = PredictionRequest(
            task=PredictionTask.HOTEL_CANCELLATION,
            features=offer_dict,
            entity_id=str(offer_dict.get("offer_id", "hotel_offer")),
        )
        res = self.engine.predict(req)
        if res.status == InferenceStatus.SUCCESS and res.prediction is not None:
            return float(res.prediction)
        return None

    def predict_inventory_available_quantity(self, snapshot_dict: Dict[str, Any]) -> Optional[float]:
        """
        Maps inventory depletion query to centralized engine.
        Returns None when required snapshot metrics are absent.
        """
        req = PredictionRequest(
            task=PredictionTask.INVENTORY_FORECASTING,
            features=snapshot_dict,
            entity_id=str(snapshot_dict.get("inventory_id", "inventory_snapshot")),
        )
        res = self.engine.predict(req)
        if res.status == InferenceStatus.SUCCESS and res.prediction is not None:
            return float(res.prediction)
        return None
