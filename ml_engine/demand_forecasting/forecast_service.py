"""
ml_engine/demand_forecasting/forecast_service.py

Production demand forecasting service.
Predicts future 7-day search volume observations using the 15-feature model.
Handles unseen destinations safely without fabricating synthetic historical baselines.
Uses consistent lowercase inventory_type matching trained transformers.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from ml_engine.exceptions import ModelInferenceError, UnsupportedPredictionError
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.schemas import PredictionTask, PredictionRequest, PredictionResult, InferenceStatus

logger = logging.getLogger(__name__)


class DemandForecastService:
    """Service predicting customer search volume at t+7 for destination and inventory type."""

    TASK_NAME = PredictionTask.DEMAND_FORECASTING.value

    def __init__(
        self,
        registry: ModelArtifactRegistry,
        searches_df: Optional[pd.DataFrame] = None,
        optimization_timestamp: Optional[str] = None,
    ):
        self.registry = registry
        self.searches_df = searches_df if searches_df is not None else pd.DataFrame()
        self.optimization_timestamp = optimization_timestamp or "2026-06-15"
        self.estimator, self.preprocessor, self.metadata = self.registry.get_model(self.TASK_NAME)
        self.expected_features: List[str] = self.metadata.get("feature_names", [
            "destination_id", "inventory_type", "search_volume", "total_travellers",
            "avg_search_price", "lag_1", "lag_7", "lag_14", "rolling_mean_7",
            "rolling_mean_14", "rolling_std_7", "day_of_week", "is_weekend", "month", "quarter"
        ])
        self._feature_cache: Dict[Tuple[str, str], Dict[str, Any]] = self._build_historical_feature_panel()
        self._prediction_cache: Dict[Tuple[str, str], Optional[float]] = {}

    def _build_historical_feature_panel(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Constructs point-in-time lag and rolling panel features strictly prior to T_opt."""
        cache = {}
        if self.searches_df.empty:
            return cache

        df = self.searches_df.copy()
        if "search_date" in df.columns:
            df["search_date_dt"] = pd.to_datetime(df["search_date"])
            cutoff_dt = pd.to_datetime(self.optimization_timestamp)
            df = df[df["search_date_dt"] <= cutoff_dt]

        if df.empty:
            return cache

        target_date = pd.to_datetime(self.optimization_timestamp) + pd.Timedelta(days=7)
        day_of_week = int(target_date.dayofweek)
        is_weekend = int(day_of_week >= 5)
        month = int(target_date.month)
        quarter = int(target_date.quarter)

        grouped = df.groupby(["destination_id", "inventory_type"])
        for (dest, itype), group in grouped:
            dest_key = (str(dest), str(itype).lower())
            daily = group.groupby("search_date_dt").agg(
                vol=("search_id", "count"),
                travellers=("travellers_count", "sum"),
                price=("search_price", "mean")
            ).sort_index()

            if daily.empty:
                continue

            last_row = daily.iloc[-1]
            s_vol = float(last_row["vol"])
            t_trav = float(last_row["travellers"])
            a_price = float(last_row["price"]) if np.isfinite(last_row["price"]) else 5000.0

            vol_series = daily["vol"]
            lag_1 = float(vol_series.iloc[-1]) if len(vol_series) >= 1 else 0.0
            lag_7 = float(vol_series.iloc[-7]) if len(vol_series) >= 7 else lag_1
            lag_14 = float(vol_series.iloc[-14]) if len(vol_series) >= 14 else lag_7

            r_mean_7 = float(vol_series.tail(7).mean()) if len(vol_series) >= 1 else lag_1
            r_mean_14 = float(vol_series.tail(14).mean()) if len(vol_series) >= 1 else r_mean_7
            r_std_7 = float(vol_series.tail(7).std()) if len(vol_series) >= 2 else 0.0
            if not np.isfinite(r_std_7):
                r_std_7 = 0.0

            cache[dest_key] = {
                "destination_id": str(dest),
                "inventory_type": str(itype).lower(),
                "search_volume": s_vol,
                "total_travellers": t_trav,
                "avg_search_price": a_price,
                "lag_1": lag_1,
                "lag_7": lag_7,
                "lag_14": lag_14,
                "rolling_mean_7": r_mean_7,
                "rolling_mean_14": r_mean_14,
                "rolling_std_7": r_std_7,
                "day_of_week": day_of_week,
                "is_weekend": is_weekend,
                "month": month,
                "quarter": quarter,
            }

        return cache

    def predict_search_volume(self, destination_id: str, inventory_type: str) -> Optional[float]:
        """
        Executes genuine ML inference for destination and inventory type.
        Returns None when no prior search history exists.
        """
        key = (str(destination_id), str(inventory_type).lower())
        if key in self._prediction_cache:
            return self._prediction_cache[key]

        if key not in self._feature_cache:
            logger.info("No prior customer searches found for %s. Demand prediction unsupported.", key)
            self._prediction_cache[key] = None
            return None

        feat_dict = self._feature_cache[key]
        row_df = pd.DataFrame([feat_dict])[self.expected_features]

        try:
            X_trans = self.preprocessor.transform(row_df) if self.preprocessor is not None else row_df
            raw_pred = self.estimator.predict(X_trans)
            val = float(raw_pred[0]) if hasattr(raw_pred, "__len__") else float(raw_pred)
            val = max(0.0, val) if np.isfinite(val) else 0.0

            self._prediction_cache[key] = val
            return val
        except Exception as exc:
            logger.error("Demand prediction inference failed for %s: %s", key, exc)
            raise ModelInferenceError(f"Demand inference failed for {key}: {exc}") from exc

    def handle_prediction_request(self, request: PredictionRequest) -> PredictionResult:
        """PredictionRouter adapter implementing the unified prediction interface."""
        dest_id = request.features.get("destination_id")
        inv_type = request.features.get("inventory_type", "hotel")

        if not dest_id:
            raise UnsupportedPredictionError("Missing 'destination_id' in prediction features")

        pred_val = self.predict_search_volume(str(dest_id), str(inv_type))
        if pred_val is None:
            return PredictionResult(
                task=request.task,
                status=InferenceStatus.UNSUPPORTED,
                prediction=None,
                prediction_type="MODEL",
                model_name=self.metadata.get("model_name", "naive"),
                model_version=self.metadata.get("saved_timestamp"),
                artifact_checksum=self.metadata.get("_artifact_sha256"),
                checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
                is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
                error_message=f"No customer search history available for destination '{dest_id}'",
                metadata={
                    "destination_id": str(dest_id),
                    "inventory_type": str(inv_type).lower(),
                    "checksum_trust_source": self.metadata.get("_checksum_trust_source"),
                },
            )

        return PredictionResult(
            task=request.task,
            status=InferenceStatus.SUCCESS,
            prediction=pred_val,
            prediction_type="MODEL",
            model_name=self.metadata.get("model_name", "naive"),
            model_version=self.metadata.get("saved_timestamp"),
            artifact_checksum=self.metadata.get("_artifact_sha256"),
            checksum_verified=bool(self.metadata.get("_checksum_verified", False)),
            is_independently_trusted=bool(self.metadata.get("_is_independently_trusted", False)),
            metadata={
                "destination_id": str(dest_id),
                "inventory_type": str(inv_type).lower(),
                "checksum_trust_source": self.metadata.get("_checksum_trust_source"),
            },
        )
