"""
ml_engine/inventory_forecasting/inventory_forecast_service.py

Production inventory forecasting service.
Predicts remaining available inventory and depletion trajectory using the 25-feature snapshot model.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError, FeatureValidationError
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
        Deterministically computes single-snapshot ratio/date features when base quantities exist,
        and returns None if required lag/velocity or core snapshot features are missing.
        """
        record = dict(snapshot_record or {})
        base_reqs = [
            "inventory_id", "inventory_type", "supplier_id", "destination_id",
            "unit_type", "travel_date", "snapshot_date",
            "total_capacity", "booked_quantity", "available_quantity",
        ]
        if any(f not in record or record[f] is None for f in base_reqs):
            logger.info("Snapshot record missing core base inventory fields.")
            return None

        try:
            tot_cap = float(record["total_capacity"])
            booked_qty = float(record["booked_quantity"])
            avail_qty = float(record["available_quantity"])
        except (TypeError, ValueError):
            return None

        if "origin_id" not in record or record["origin_id"] is None:
            if str(record.get("inventory_type", "")).upper() == "HOTEL":
                record["origin_id"] = "None"

        if "days_to_travel" not in record or record["days_to_travel"] is None:
            try:
                t_dt = pd.to_datetime(record["travel_date"])
                s_dt = pd.to_datetime(record["snapshot_date"])
                record["days_to_travel"] = max(0.0, float((t_dt - s_dt).days))
            except Exception:
                pass

        occ_rate = (booked_qty / tot_cap) if tot_cap > 0 else 0.0
        avail_rate = (avail_qty / tot_cap) if tot_cap > 0 else 0.0
        record.setdefault("occupancy_rate", occ_rate)
        record.setdefault("inventory_utilization_rate", occ_rate)
        record.setdefault("availability_rate", avail_rate)
        record.setdefault("availability_percentage", avail_rate * 100.0)
        if "availability_bucket" not in record or record["availability_bucket"] is None:
            if avail_rate <= 0.15:
                record["availability_bucket"] = "Critical"
            elif avail_rate <= 0.35:
                record["availability_bucket"] = "Low"
            elif avail_rate <= 0.70:
                record["availability_bucket"] = "Moderate"
            else:
                record["availability_bucket"] = "High"
        if "high_occupancy_indicator" not in record or record["high_occupancy_indicator"] is None:
            record["high_occupancy_indicator"] = bool(occ_rate >= 0.8)
        if "low_availability_indicator" not in record or record["low_availability_indicator"] is None:
            record["low_availability_indicator"] = bool(avail_qty < 5)

        for bool_col in ("high_occupancy_indicator", "low_availability_indicator", "rapid_depletion_indicator"):
            if bool_col in record and isinstance(record[bool_col], str):
                record[bool_col] = record[bool_col].strip().lower() in ("true", "1", "yes")

        missing = [f for f in self.expected_features if f not in record or record[f] is None]
        if missing:
            logger.info("Snapshot record missing required features: %s", missing[:5])
            return None

        row_df = pd.DataFrame([record])[self.expected_features]

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
                prediction_type="MODEL",
                model_name=self.metadata.get("model_name"),
                model_version=self.metadata.get("saved_timestamp"),
                artifact_checksum=self.metadata.get("_artifact_sha256"),
                checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
                is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
                error_message="Snapshot lacks required engineered features for inventory forecasting.",
                metadata={"checksum_trust_source": self.metadata.get("_checksum_trust_source")},
            )

        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS,
            prediction=pred,
            prediction_type="MODEL",
            model_name=self.metadata.get("model_name"),
            model_version=self.metadata.get("saved_timestamp"),
            artifact_checksum=self.metadata.get("_artifact_sha256"),
            checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
            is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
            metadata={
                "target_column": "future_available_quantity",
                "checksum_trust_source": self.metadata.get("_checksum_trust_source"),
            },
        )
