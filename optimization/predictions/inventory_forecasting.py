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

            required = [
                "inventory_id", "inventory_type", "supplier_id", "origin_id",
                "destination_id", "unit_type", "travel_date", "snapshot_date",
                "days_to_travel", "total_capacity", "booked_quantity",
                "available_quantity", "days_since_prev_snapshot",
                "change_in_booked_quantity", "change_in_available_quantity",
                "booking_velocity_units_per_day", "inventory_depletion_velocity",
            ]
            missing = [key for key in required if record.get(key) is None]
            if missing:
                if raise_on_error:
                    raise ModelInferenceError(
                        f"Missing authoritative inventory forecasting features for {inv_id}: {missing}"
                    )
                return None

            tot_cap = float(record["total_capacity"])
            avail_qty = float(record["available_quantity"])
            booked_qty = float(record["booked_quantity"])
            if tot_cap < 0 or avail_qty < 0 or booked_qty < 0:
                return None
            if avail_qty + booked_qty != tot_cap:
                if raise_on_error:
                    raise ModelInferenceError(
                        f"Inventory snapshot conservation failed for {inv_id}: "
                        f"{avail_qty} + {booked_qty} != {tot_cap}"
                    )
                return None

            occ_rate = (booked_qty / tot_cap) if tot_cap > 0 else 0.0
            avail_rate = (avail_qty / tot_cap) if tot_cap > 0 else 0.0
            if avail_rate <= 0.15:
                derived_bucket = "Critical"
            elif avail_rate <= 0.35:
                derived_bucket = "Low"
            elif avail_rate <= 0.70:
                derived_bucket = "Moderate"
            else:
                derived_bucket = "High"

            def _to_bool(val: Any, default_val: bool) -> bool:
                if val is None:
                    return default_val
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    return val.strip().lower() in ("true", "1", "yes")
                return bool(val)

            derived = {
                "inventory_id": inv_id,
                "total_capacity": tot_cap,
                "booked_quantity": booked_qty,
                "available_quantity": avail_qty,
                "occupancy_rate": occ_rate,
                "inventory_utilization_rate": occ_rate,
                "availability_rate": avail_rate,
                "availability_percentage": avail_rate * 100.0,
                "availability_bucket": derived_bucket,
                "high_occupancy_indicator": _to_bool(record.get("high_occupancy_indicator"), occ_rate >= 0.8),
                "low_availability_indicator": _to_bool(record.get("low_availability_indicator"), avail_qty < 5),
                "rapid_depletion_indicator": _to_bool(record.get("rapid_depletion_indicator"), False),
            }
            for key, value in derived.items():
                record[key] = value

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
