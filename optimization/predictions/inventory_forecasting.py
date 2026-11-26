"""
optimization/predictions/inventory_forecasting.py

Inventory forecasting service using Phase 4 LightGBM champion model.
Predicts remaining future available quantity with strict feature schema enforcement
and structured error reporting.
"""

import logging
import math
from typing import Dict, Any, List, Optional
import pandas as pd
from optimization.predictions.model_registry import ModelRegistry
from optimization.config import OptimizationConfig
from optimization.exceptions import ModelInferenceError

logger = logging.getLogger(__name__)


class InventoryForecastingService:
    """Predicts future available inventory and depletion trajectory."""

    TASK_NAME = "inventory_forecasting"

    def __init__(self, registry: ModelRegistry, config: OptimizationConfig):
        self.registry = registry
        self.config = config
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [])

    def predict_future_available_quantity(
        self, snapshot_record: Dict[str, Any], raise_on_error: bool = False
    ) -> Optional[float]:
        """
        Predicts future remaining inventory.

        Distinguishes explicit prediction failures (returns None or raises ModelInferenceError)
        from genuine predictions of zero inventory (stockout, returns 0.0).

        Args:
            snapshot_record: Dictionary containing inventory snapshot attributes.
            raise_on_error: If True, raises ModelInferenceError instead of returning None on failure.

        Returns:
            Optional[float]: Non-negative predicted available quantity, or None if prediction is unavailable.
        """
        inv_id = str(snapshot_record.get("inventory_id", "UNKNOWN"))
        if not snapshot_record:
            logger.warning("Empty snapshot record provided for inventory forecasting.")
            if raise_on_error:
                raise ModelInferenceError("Empty snapshot record provided.")
            return None

        try:
            record = dict(snapshot_record)

            # Derive capacity and quantities if needed
            tot_cap = float(record.get("total_capacity") or record.get("available_quantity") or 0.0)
            avail_qty = float(record.get("available_quantity") or 0.0)
            booked_qty = float(record.get("booked_quantity") or max(0.0, tot_cap - avail_qty))

            occ_rate = (booked_qty / tot_cap) if tot_cap > 0 else 0.0
            avail_rate = (avail_qty / tot_cap) if tot_cap > 0 else 0.0

            # Derive standard features if missing
            defaults = {
                "inventory_id": inv_id,
                "inventory_type": record.get("inventory_type", "HOTEL"),
                "supplier_id": record.get("supplier_id", "UNKNOWN"),
                "origin_id": record.get("origin_id", "NONE"),
                "destination_id": record.get("destination_id", "NONE"),
                "unit_type": record.get("unit_type", "ROOM_NIGHT"),
                "travel_date": str(record.get("travel_date", "")),
                "snapshot_date": str(record.get("snapshot_date", "")),
                "days_to_travel": float(record.get("days_to_travel", 7.0)),
                "total_capacity": tot_cap,
                "booked_quantity": booked_qty,
                "available_quantity": avail_qty,
                "occupancy_rate": occ_rate,
                "inventory_utilization_rate": occ_rate,
                "availability_rate": avail_rate,
                "availability_percentage": avail_rate * 100.0,
                "availability_bucket": record.get("availability_bucket", "MEDIUM"),
                "days_since_prev_snapshot": float(record.get("days_since_prev_snapshot", 1.0)),
                "change_in_booked_quantity": float(record.get("change_in_booked_quantity", 0.0)),
                "change_in_available_quantity": float(record.get("change_in_available_quantity", 0.0)),
                "booking_velocity_units_per_day": float(record.get("booking_velocity_units_per_day", 0.0)),
                "inventory_depletion_velocity": float(record.get("inventory_depletion_velocity", 0.0)),
                "high_occupancy_indicator": record.get("high_occupancy_indicator", "FALSE" if occ_rate < 0.8 else "TRUE"),
                "low_availability_indicator": record.get("low_availability_indicator", "FALSE" if avail_qty >= 5 else "TRUE"),
                "rapid_depletion_indicator": record.get("rapid_depletion_indicator", "FALSE"),
            }

            for k, v in defaults.items():
                if k not in record or record[k] is None:
                    record[k] = v

            row_df = pd.DataFrame([record])

            # Verify and align all 25 expected features
            missing_cols = [c for c in self.expected_features if c not in row_df.columns]
            if missing_cols:
                logger.error(
                    "Inventory forecasting missing mandatory features for inventory_id=%s: %s",
                    inv_id, missing_cols
                )
                if raise_on_error:
                    raise ModelInferenceError(f"Missing mandatory features for inventory {inv_id}: {missing_cols}")
                return None

            row_aligned = row_df[self.expected_features]
            X_trans = self.preprocessor.transform(row_aligned)
            pred_raw = float(self.estimator.predict(X_trans)[0])

            if math.isnan(pred_raw) or math.isinf(pred_raw):
                logger.error("Inventory forecasting produced non-finite output for inventory_id=%s: %s", inv_id, pred_raw)
                if raise_on_error:
                    raise ModelInferenceError(f"Non-finite prediction {pred_raw} for inventory {inv_id}")
                return None

            # Non-negative clipping; pred == 0.0 is a legitimate stockout prediction
            pred_final = max(0.0, pred_raw)
            if pred_final == 0.0:
                logger.info("Inventory forecasting predicted legitimate stockout (0.0) for inventory_id=%s", inv_id)

            return pred_final

        except Exception as e:
            logger.error(
                "Inventory forecasting inference exception for inventory_id=%s: %s",
                inv_id, str(e), exc_info=True
            )
            if raise_on_error:
                raise ModelInferenceError(f"Inventory prediction failed for {inv_id}: {e}") from e
            return None
