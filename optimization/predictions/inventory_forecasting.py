"""
optimization/predictions/inventory_forecasting.py

Inventory forecasting service using Phase 4 LightGBM champion model.
Predicts remaining future available quantity.
"""

from typing import Dict, Any, List
import pandas as pd
from optimization.predictions.model_registry import ModelRegistry
from optimization.config import OptimizationConfig


class InventoryForecastingService:
    """Predicts future available inventory and depletion trajectory."""

    TASK_NAME = "inventory_forecasting"

    def __init__(self, registry: ModelRegistry, config: OptimizationConfig):
        self.registry = registry
        self.config = config
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [])

    def predict_future_available_quantity(self, snapshot_record: Dict[str, Any]) -> float:
        """
        Predicts future remaining inventory.
        """
        try:
            row_df = pd.DataFrame([snapshot_record])
            # Ensure all expected columns are present
            for col in self.expected_features:
                if col not in row_df.columns:
                    row_df[col] = 0
            row_aligned = row_df[self.expected_features]
            X_trans = self.preprocessor.transform(row_aligned)
            pred = float(self.estimator.predict(X_trans)[0])
            return max(0.0, pred)
        except Exception:
            # Fallback to current available quantity or configured default
            default_inv = getattr(self.config, "default_available_inventory", 10.0)
            return float(snapshot_record.get("available_quantity", default_inv))
