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
        if optimization_timestamp is not None:
            self.optimization_timestamp = str(optimization_timestamp)
        elif not self.searches_df.empty and "search_date" in self.searches_df.columns:
            valid_dates = pd.to_datetime(self.searches_df["search_date"], errors="coerce").dropna()
            self.optimization_timestamp = valid_dates.max().strftime("%Y-%m-%d") if not valid_dates.empty else pd.Timestamp.now().strftime("%Y-%m-%d")
        else:
            self.optimization_timestamp = pd.Timestamp.now().strftime("%Y-%m-%d")

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
            df["search_date_dt"] = pd.to_datetime(df["search_date"], errors="coerce")
            if hasattr(df["search_date_dt"].dt, "tz") and df["search_date_dt"].dt.tz is not None:
                df["search_date_dt"] = df["search_date_dt"].dt.tz_localize(None)
            df["search_date_dt"] = df["search_date_dt"].dt.normalize()
            df = df.dropna(subset=["search_date_dt"])

            cutoff_dt = pd.to_datetime(self.optimization_timestamp, errors="coerce")
            if hasattr(cutoff_dt, "tz") and cutoff_dt.tz is not None:
                cutoff_dt = cutoff_dt.tz_localize(None)
            cutoff_dt = cutoff_dt.normalize()
            df = df[df["search_date_dt"] <= cutoff_dt]

        if df.empty:
            return cache

        # Origin date calendar features (matching modeling/target_builder.py training semantics)
        origin_date = pd.to_datetime(self.optimization_timestamp, errors="coerce")
        day_of_week = int(origin_date.dayofweek)
        is_weekend = int(day_of_week >= 5)
        month = int(origin_date.month)
        quarter = int(origin_date.quarter)

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

            # Complete calendar daily grid up to cutoff_dt (matching training target_builder)
            start_date = daily.index.min()
            full_idx = pd.date_range(start=start_date, end=cutoff_dt, freq="D")
            daily_reindexed = daily.reindex(full_idx)
            daily_reindexed["vol"] = daily_reindexed["vol"].fillna(0.0)
            daily_reindexed["travellers"] = daily_reindexed["travellers"].fillna(0.0)
            daily_reindexed["price"] = daily_reindexed["price"].ffill().fillna(0.0)

            last_row = daily_reindexed.iloc[-1]
            s_vol = float(last_row["vol"])
            t_trav = float(last_row["travellers"])
            a_price = float(last_row["price"]) if np.isfinite(last_row["price"]) else 0.0

            vol_series = daily_reindexed["vol"]
            lag_1_series = vol_series.shift(1).fillna(0.0)
            lag_7_series = vol_series.shift(7).fillna(0.0)
            lag_14_series = vol_series.shift(14).fillna(0.0)
            r_mean_7_series = vol_series.shift(1).rolling(7, min_periods=1).mean().fillna(0.0)
            r_mean_14_series = vol_series.shift(1).rolling(14, min_periods=1).mean().fillna(0.0)
            r_std_7_series = vol_series.shift(1).rolling(7, min_periods=1).std().fillna(0.0)

            lag_1 = float(lag_1_series.iloc[-1])
            lag_7 = float(lag_7_series.iloc[-1])
            lag_14 = float(lag_14_series.iloc[-1])
            r_mean_7 = float(r_mean_7_series.iloc[-1])
            r_mean_14 = float(r_mean_14_series.iloc[-1])
            r_std_7 = float(r_std_7_series.iloc[-1])

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
            if not np.isfinite(val):
                raise ModelInferenceError(f"Demand estimator produced non-finite prediction '{val}' for {key}")
            val = max(0.0, val)

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
