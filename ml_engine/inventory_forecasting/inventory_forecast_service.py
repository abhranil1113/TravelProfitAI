"""
ml_engine/inventory_forecasting/inventory_forecast_service.py

Production inventory forecasting service.
Predicts remaining available inventory and depletion trajectory using the 25-feature snapshot model.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.schemas import PredictionTask, PredictionRequest, PredictionResult, InferenceStatus

logger = logging.getLogger(__name__)


class InventoryForecastService:
    """Service predicting future available units and capacity depletion."""

    TASK_NAME = PredictionTask.INVENTORY_FORECASTING.value

    def __init__(self, registry: ModelArtifactRegistry):
        self.registry = registry
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [
            "inventory_id", "inventory_type", "supplier_id", "origin_id",
            "destination_id", "unit_type", "travel_date", "snapshot_date",
            "days_to_travel", "total_capacity", "booked_quantity",
            "available_quantity", "occupancy_rate", "inventory_utilization_rate",
            "availability_rate", "availability_percentage", "availability_bucket",
            "days_since_prev_snapshot", "change_in_booked_quantity",
            "change_in_available_quantity", "booking_velocity_units_per_day",
            "inventory_depletion_velocity", "high_occupancy_indicator",
            "low_availability_indicator", "rapid_depletion_indicator"
        ])

    def predict_future_available_quantity(self, snapshot_record: Dict[str, Any]) -> Optional[float]:
        """
        Predicts remaining capacity bounded within [0, total_capacity].
        """
        missing = [f for f in self.expected_features if f not in snapshot_record]
        if missing:
            logger.info("Snapshot record missing required features: %s", missing)
            return None

        row_df = pd.DataFrame([snapshot_record])[self.expected_features]

        try:
            X_trans = self.preprocessor.transform(row_df) if self.preprocessor is not None else row_df
            raw_pred = self.estimator.predict(X_trans)
            val = float(raw_pred[0]) if hasattr(raw_pred, "__len__") else float(raw_pred)

            if not np.isfinite(val):
                return None

            total_cap = float(snapshot_record.get("total_capacity", 1000.0))
            return float(np.clip(val, 0.0, total_cap))
        except Exception as exc:
            logger.error("Inventory forecast inference failed: %s", exc)
            raise ModelInferenceError(f"Inventory inference failed: {exc}") from exc

    def handle_prediction_request(self, request: PredictionRequest) -> PredictionResult:
        """PredictionRouter adapter implementing the unified prediction interface."""
        pred = self.predict_future_available_quantity(request.features)
        if pred is None:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                model_name=self.metadata.get("model_name"),
                error_message="Snapshot lacks required features for inventory forecasting.",
            )

        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS,
            prediction=pred,
            model_name=self.metadata.get("model_name"),
            metadata={"target_column": "future_available_quantity"},
        )
