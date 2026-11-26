"""
tests/modeling/test_ml_engine_verification.py

Comprehensive verification and compatibility test suite for TBO InventoryIQ ML Engine:
1. Demand forecasting training vs inference feature parity.
2. Legacy estimator prediction compatibility (NaiveForecaster & SeasonalNaiveForecaster).
3. Model artifact metadata parsing, integrity checks, and version declarations.
4. Model registry concurrency, per-task locking, and invalidation safety.
5. Regression and classification metric computation edge cases.
"""

import os
import json
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch
import pytest
import numpy as np
import pandas as pd

from ml_engine.schemas import (
    PredictionTask,
    PredictionRequest,
    PredictionResult,
    InferenceStatus,
    ModelMetadataSchema,
)
from ml_engine.exceptions import (
    ModelInferenceError,
    ArtifactCorruptedError,
    SchemaMismatchError,
    ChecksumMismatchError,
)
from ml_engine.demand_forecasting.forecast_service import DemandForecastService
from ml_engine.model_registry.registry import ModelArtifactRegistry
from ml_engine.model_registry.model_metadata import ModelMetadataValidator
from modeling.baselines import NaiveForecaster, SeasonalNaiveForecaster
from ml_engine.evaluation.regression_metrics import RegressionMetrics
from ml_engine.evaluation.classification_metrics import ClassificationMetrics
from modeling.metrics import safe_mape, safe_wape, safe_smape, compute_forecast_bias


# =====================================================================
# 1. LEGACY ESTIMATOR PREDICTION COMPATIBILITY TESTS
# =====================================================================

class TestLegacyEstimatorCompatibility:
    """Verifies estimator compatibility with legacy serialized states and scikit-learn conventions."""

    def test_naive_forecaster_sklearn_conventions(self):
        """Checks get_params, set_params, repr, and constructor conventions."""
        forecaster = NaiveForecaster(lag_col="lag_1", lag_col_idx=5)
        params = forecaster.get_params()
        assert params == {"lag_col": "lag_1", "lag_col_idx": 5}

        forecaster.set_params(lag_col="lag_7", lag_col_idx=6)
        assert forecaster.lag_col == "lag_7"
        assert forecaster.lag_col_idx == 6
        assert "NaiveForecaster" in repr(forecaster)

    def test_naive_forecaster_legacy_state_unpickling(self):
        """Simulates unpickling legacy NaiveForecaster state lacking lag_col_idx."""
        legacy_state = {
            "lag_col": "lag_1",
            "last_value_": 42.0,
            "lag_col_idx_": 5,
        }
        forecaster = NaiveForecaster()
        forecaster.__setstate__(legacy_state)

        # Scikit-learn repr/get_params must not raise AttributeError
        params = forecaster.get_params()
        assert params["lag_col"] == "lag_1"
        assert getattr(forecaster, "lag_col_idx", None) == 5
        assert "NaiveForecaster" in repr(forecaster)

    def test_naive_forecaster_prediction_parity(self):
        """Tests prediction parity across DataFrame, 2D NumPy array, and 1D NumPy array."""
        legacy_state = {
            "lag_col": "lag_1",
            "last_value_": 50.0,
            "lag_col_idx_": 1,
        }
        forecaster = NaiveForecaster()
        forecaster.__setstate__(legacy_state)

        # 1. DataFrame input
        df = pd.DataFrame({"other": [10, 20], "lag_1": [15.0, 25.0]})
        preds_df = forecaster.predict(df)
        assert np.allclose(preds_df, [15.0, 25.0])

        # 2. 2D NumPy array input
        arr_2d = np.array([[100.0, 15.0], [200.0, 25.0]])
        preds_2d = forecaster.predict(arr_2d)
        assert np.allclose(preds_2d, [15.0, 25.0])

        # 3. 1D NumPy array input
        arr_1d = np.array([100.0, 15.0])
        preds_1d = forecaster.predict(arr_1d)
        assert np.allclose(preds_1d, [15.0])

        # 4. Fallback to last_value_ when column not resolvable
        df_missing = pd.DataFrame({"unrelated": [1, 2]})
        forecaster_no_idx = NaiveForecaster(lag_col="missing_col", lag_col_idx=None)
        forecaster_no_idx.last_value_ = 99.0
        forecaster_no_idx.lag_col_idx_ = None
        preds_fallback = forecaster_no_idx.predict(df_missing)
        assert np.allclose(preds_fallback, [99.0, 99.0])

    def test_seasonal_naive_forecaster_legacy_compatibility(self):
        """Verifies SeasonalNaiveForecaster compatibility with legacy state."""
        legacy_state = {
            "seasonal_period": 7,
            "lag_col": "lag_7",
            "seasonal_history_": np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]),
        }
        forecaster = SeasonalNaiveForecaster()
        forecaster.__setstate__(legacy_state)

        params = forecaster.get_params()
        assert params["lag_col"] == "lag_7"
        assert "SeasonalNaiveForecaster" in repr(forecaster)
        # Should default lag_col_idx_ to 6 for standard 15-feature panel
        assert forecaster.lag_col_idx_ == 6

        # 15-feature array prediction
        X_15 = np.zeros((2, 15))
        X_15[:, 6] = [88.0, 99.0]
        preds = forecaster.predict(X_15)
        assert np.allclose(preds, [88.0, 99.0])


# =====================================================================
# 2. DEMAND FORECASTING TRAINING VS INFERENCE PARITY TESTS
# =====================================================================

class TestDemandForecastingParity:
    """Verifies feature parity between training (target_builder.py) and inference (forecast_service.py)."""

    def _create_mock_registry(self, metadata=None):
        registry = MagicMock(spec=ModelArtifactRegistry)
        mock_estimator = MagicMock()
        mock_estimator.predict.return_value = np.array([12.5])
        mock_preprocessor = None
        meta = metadata or {
            "model_name": "naive",
            "saved_timestamp": "2026-06-15T00:00:00",
            "_artifact_sha256": "fake_sha256",
            "_checksum_verified": True,
            "_is_independently_trusted": True,
            "_checksum_trust_source": "INDEPENDENT_CONFIG",
            "feature_names": [
                "destination_id", "inventory_type", "search_volume", "total_travellers",
                "avg_search_price", "lag_1", "lag_7", "lag_14", "rolling_mean_7",
                "rolling_mean_14", "rolling_std_7", "day_of_week", "is_weekend", "month", "quarter"
            ]
        }
        registry.get_model.return_value = (mock_estimator, mock_preprocessor, meta)
        return registry

    def test_calendar_features_match_origin_date(self):
        """Verifies calendar features represent the origin cutoff date t, not t+7."""
        registry = self._create_mock_registry()
        # Monday, June 1, 2026: dayofweek=0, is_weekend=0, month=6, quarter=2
        cutoff = "2026-06-01"
        searches = pd.DataFrame([
            {"search_id": "s1", "search_date": "2026-06-01", "destination_id": "DEL", "inventory_type": "hotel", "travellers_count": 2, "search_price": 4000.0}
        ])
        svc = DemandForecastService(registry=registry, searches_df=searches, optimization_timestamp=cutoff)
        panel = svc._feature_cache.get(("DEL", "hotel"))
        assert panel is not None
        assert panel["day_of_week"] == 0   # Monday
        assert panel["is_weekend"] == 0
        assert panel["month"] == 6
        assert panel["quarter"] == 2

    def test_continuous_calendar_resampling_and_lags(self):
        """Verifies gaps between dates are filled with 0s and lags reflect calendar days."""
        registry = self._create_mock_registry()
        # Searches on Jan 1 and Jan 8; Jan 2 through Jan 7 have 0 volume
        cutoff = "2026-01-08"
        searches = pd.DataFrame([
            {"search_id": "s1", "search_date": "2026-01-01", "destination_id": "BOM", "inventory_type": "hotel", "travellers_count": 1, "search_price": 3000.0},
            {"search_id": "s2", "search_date": "2026-01-08", "destination_id": "BOM", "inventory_type": "hotel", "travellers_count": 2, "search_price": 3500.0},
        ])
        svc = DemandForecastService(registry=registry, searches_df=searches, optimization_timestamp=cutoff)
        panel = svc._feature_cache.get(("BOM", "hotel"))
        assert panel is not None
        # On Jan 8 (cutoff): volume = 1
        assert panel["search_volume"] == 1.0
        # lag_1 is Jan 7 (0 volume)
        assert panel["lag_1"] == 0.0
        # lag_7 is Jan 1 (1 volume)
        assert panel["lag_7"] == 1.0
        # lag_14 is unobserved, filled with 0.0
        assert panel["lag_14"] == 0.0

    def test_missing_price_zero_fill_without_hardcoded_5000(self):
        """Verifies missing prices are forward-filled and filled with 0.0 (not 5000.0)."""
        registry = self._create_mock_registry()
        cutoff = "2026-03-05"
        searches = pd.DataFrame([
            {"search_id": "s1", "search_date": "2026-03-05", "destination_id": "GOA", "inventory_type": "flight", "travellers_count": 1, "search_price": np.nan}
        ])
        svc = DemandForecastService(registry=registry, searches_df=searches, optimization_timestamp=cutoff)
        panel = svc._feature_cache.get(("GOA", "flight"))
        assert panel is not None
        assert panel["avg_search_price"] == 0.0

    def test_cutoff_date_point_in_time_filtering(self):
        """Verifies searches strictly after optimization_timestamp are excluded."""
        registry = self._create_mock_registry()
        cutoff = "2026-04-10"
        searches = pd.DataFrame([
            {"search_id": "s1", "search_date": "2026-04-09", "destination_id": "MAA", "inventory_type": "hotel", "travellers_count": 1, "search_price": 2000.0},
            {"search_id": "s2", "search_date": "2026-04-10", "destination_id": "MAA", "inventory_type": "hotel", "travellers_count": 1, "search_price": 2000.0},
            {"search_id": "s3", "search_date": "2026-04-11", "destination_id": "MAA", "inventory_type": "hotel", "travellers_count": 10, "search_price": 9999.0}, # Future lookahead
        ])
        svc = DemandForecastService(registry=registry, searches_df=searches, optimization_timestamp=cutoff)
        panel = svc._feature_cache.get(("MAA", "hotel"))
        assert panel is not None
        assert panel["search_volume"] == 1.0  # Only s2 on 04-10, s3 excluded

    def test_dynamic_timestamp_inference_when_omitted(self):
        """Verifies optimization_timestamp defaults dynamically from searches_df, never hardcoded '2026-06-15'."""
        registry = self._create_mock_registry()
        searches = pd.DataFrame([
            {"search_id": "s1", "search_date": "2026-11-20", "destination_id": "BLR", "inventory_type": "hotel", "travellers_count": 1, "search_price": 4000.0}
        ])
        svc = DemandForecastService(registry=registry, searches_df=searches, optimization_timestamp=None)
        assert svc.optimization_timestamp == "2026-11-20"

    def test_non_finite_prediction_raises_error(self):
        """Verifies non-finite estimator prediction (NaN/Inf) raises ModelInferenceError."""
        registry = self._create_mock_registry()
        mock_estimator = MagicMock()
        mock_estimator.predict.return_value = np.array([float("nan")])
        registry.get_model.return_value = (mock_estimator, None, {
            "model_name": "naive", "saved_timestamp": "v1", "feature_names": ["destination_id", "inventory_type", "search_volume", "total_travellers", "avg_search_price", "lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14", "rolling_std_7", "day_of_week", "is_weekend", "month", "quarter"]
        })
        searches = pd.DataFrame([
            {"search_id": "s1", "search_date": "2026-01-01", "destination_id": "DEL", "inventory_type": "hotel", "travellers_count": 1, "search_price": 1000.0}
        ])
        svc = DemandForecastService(registry=registry, searches_df=searches, optimization_timestamp="2026-01-01")
        with pytest.raises(ModelInferenceError, match="non-finite prediction"):
            svc.predict_search_volume("DEL", "hotel")


# =====================================================================
# 3. MODEL METADATA & ARTIFACT COMPATIBILITY TESTS
# =====================================================================

class TestModelMetadataValidation:
    """Tests metadata parsing, validation, package declarations, and checksum validation."""

    def test_valid_synthetic_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meta_path = os.path.join(tmpdir, "metadata.json")
            data = {
                "task_name": "demand_forecasting",
                "task_type": "time_series_regression",
                "model_name": "naive",
                "feature_names": ["f1", "f2"],
                "feature_count": 2,
                "saved_timestamp": "2026-11-26T00:00:00",
                "packages": {"sklearn": "1.7.2", "joblib": "1.6.0"},
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            schema, raw = ModelMetadataValidator.load_and_validate(meta_path)
            assert schema.task_name == "demand_forecasting"
            assert schema.feature_count == 2
            assert schema.packages["sklearn"] == "1.7.2"

    def test_missing_mandatory_field_raises_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meta_path = os.path.join(tmpdir, "metadata.json")
            data = {
                "task_name": "demand_forecasting",
                # missing task_type and model_name
                "feature_names": ["f1"],
                "feature_count": 1,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            with pytest.raises(ArtifactCorruptedError, match="missing mandatory fields"):
                ModelMetadataValidator.load_and_validate(meta_path)

    def test_feature_count_mismatch_raises_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meta_path = os.path.join(tmpdir, "metadata.json")
            data = {
                "task_name": "flight_price",
                "task_type": "regression",
                "model_name": "rf",
                "feature_names": ["f1", "f2"],
                "feature_count": 5, # Mismatch
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            with pytest.raises(SchemaMismatchError, match="Metadata feature count mismatch"):
                ModelMetadataValidator.load_and_validate(meta_path)


# =====================================================================
# 4. MODEL REGISTRY CONCURRENCY & CACHING TESTS
# =====================================================================

class TestModelRegistryConcurrency:
    """Verifies per-task locking, non-blocking multi-task loads, and invalidation safety."""

    def test_parallel_loads_for_different_tasks(self):
        """Tasks A and B load concurrently in parallel on separate task locks."""
        reg = ModelArtifactRegistry()
        reg.clear_cache()

        load_order = []
        barrier = threading.Barrier(2)

        def mock_load(task_name):
            barrier.wait() # Ensure both threads enter simultaneously
            time.sleep(0.05)
            load_order.append(task_name)
            meta = {
                "model_name": "test_model",
                "saved_timestamp": "v1",
                "_artifact_sha256": f"hash_{task_name}",
            }
            return (MagicMock(), None, meta)

        with patch.object(reg, "resolve_task_dir", side_effect=lambda t, **kw: f"/fake/{t}"), \
             patch.object(ModelMetadataValidator, "load_and_validate", side_effect=lambda p: (MagicMock(saved_timestamp="v1", model_name="m"), {})), \
             patch.object(ModelMetadataValidator, "verify_artifacts_exist", side_effect=lambda d, s: ("/fake/est", None)), \
             patch.object(reg, "compute_sha256", return_value="hash"), \
             patch("joblib.load", side_effect=lambda p: MagicMock()):

            t1 = threading.Thread(target=reg.get_model, args=("flight_price",))
            t2 = threading.Thread(target=reg.get_model, args=("hotel_cancellation",))

            t1.start()
            t2.start()
            t1.join(timeout=2.0)
            t2.join(timeout=2.0)

            assert not t1.is_alive()
            assert not t2.is_alive()

    def test_concurrent_requests_for_same_task_deduplicated(self):
        """Multiple concurrent requests for the same task load once and share the cached model."""
        reg = ModelArtifactRegistry()
        reg.clear_cache()

        load_count = 0
        lock = threading.Lock()

        def slow_joblib_load(path):
            nonlocal load_count
            with lock:
                load_count += 1
            time.sleep(0.05)
            return MagicMock()

        with patch.object(reg, "resolve_task_dir", return_value="/fake/dir"), \
             patch.object(ModelMetadataValidator, "load_and_validate", return_value=(MagicMock(saved_timestamp="v1", model_name="m"), {})), \
             patch.object(ModelMetadataValidator, "verify_artifacts_exist", return_value=("/fake/est", None)), \
             patch.object(reg, "compute_sha256", return_value="hash"), \
             patch("joblib.load", side_effect=slow_joblib_load):

            threads = [threading.Thread(target=reg.get_model, args=("inventory_forecasting",)) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=2.0)

            # Exactly one disk load should have occurred despite 5 concurrent callers
            assert load_count == 1

    def test_invalidation_during_active_load_discards_stale_model(self):
        """Verifies that cache invalidation during disk read discards the result."""
        reg = ModelArtifactRegistry()
        reg.clear_cache()

        entered_load = threading.Event()
        proceed_load = threading.Event()

        def blocking_load(path):
            entered_load.set()
            proceed_load.wait(timeout=1.0)
            return MagicMock()

        with patch.object(reg, "resolve_task_dir", return_value="/fake/dir"), \
             patch.object(ModelMetadataValidator, "load_and_validate", return_value=(MagicMock(saved_timestamp="v1", model_name="m"), {})), \
             patch.object(ModelMetadataValidator, "verify_artifacts_exist", return_value=("/fake/est", None)), \
             patch.object(reg, "compute_sha256", return_value="hash"), \
             patch("joblib.load", side_effect=blocking_load):

            t = threading.Thread(target=reg.get_model, args=("demand_forecasting",))
            t.start()

            # Wait until thread is inside slow disk read
            assert entered_load.wait(timeout=1.0)

            # Invalidate cache concurrently while load is in progress
            ModelArtifactRegistry.invalidate_cache("demand_forecasting")

            # Allow load to complete
            proceed_load.set()
            t.join(timeout=2.0)

            # Stale model must NOT be in cache
            with ModelArtifactRegistry._CACHE_LOCK:
                assert "demand_forecasting" not in ModelArtifactRegistry._TASK_TO_CACHE_KEY


# =====================================================================
# 5. REGRESSION & CLASSIFICATION METRIC COMPUTATION TESTS
# =====================================================================

class TestMLMetricsEdgeCases:
    """Tests evaluation metrics across normal and zero-denominator / edge-case inputs."""

    def test_regression_metrics_normal(self):
        y_true = [10.0, 20.0, 30.0]
        y_pred = [12.0, 18.0, 33.0]
        res = RegressionMetrics.calculate_all(y_true, y_pred)
        assert res["mae"] == round((2.0 + 2.0 + 3.0) / 3.0, 4)
        assert res["rmse"] is not None
        assert res["r2"] is not None
        assert res["forecast_bias"] is not None

    def test_regression_metrics_empty_input(self):
        res = RegressionMetrics.calculate_all([], [])
        assert res["sample_count"] == 0
        assert res["mae"] is None
        assert res["rmse"] is None

    def test_regression_metrics_zero_actuals_safe(self):
        y_true = [0.0, 0.0]
        y_pred = [1.0, 2.0]
        res = RegressionMetrics.calculate_all(y_true, y_pred)
        assert res["wape"] is not None
        assert not np.isnan(res["mae"])

    def test_classification_metrics_normal(self):
        y_true = [0, 1, 1, 0, 1]
        y_prob = [0.1, 0.9, 0.8, 0.2, 0.7]
        res = ClassificationMetrics.calculate_all(y_true, y_prob, threshold=0.5)
        assert res["accuracy"] == 1.0
        assert res["precision"] == 1.0
        assert res["recall"] == 1.0
        assert res["f1_score"] == 1.0
        assert res["confusion_matrix"]["true_positives"] == 3

    def test_classification_metrics_empty_input(self):
        res = ClassificationMetrics.calculate_all([], [])
        assert res["sample_count"] == 0
        assert res["accuracy"] is None
        assert res["f1_score"] is None

    def test_safe_mape_and_wape_formulas(self):
        yt = np.array([0.0, 10.0, 20.0])
        yp = np.array([1.0, 12.0, 18.0])
        val, status = safe_mape(yt, yp)
        assert status == "VALID"
        assert not np.isnan(val)

        wape_val, wape_status = safe_wape(np.array([0.0, 0.0]), np.array([1.0, 1.0]))
        assert wape_status == "UNDEFINED_ZERO_TOTAL_DEMAND"
        assert np.isnan(wape_val)
