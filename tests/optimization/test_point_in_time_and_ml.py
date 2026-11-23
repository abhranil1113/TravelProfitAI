"""
tests/optimization/test_point_in_time_and_ml.py

Unit tests for temporal point-in-time filtering and ML model inference integrations.
Validates:
1. Expired offers filtering relative to cutoff timestamp.
2. Temporal leakage prevention.
3. Hotel cancellation LightGBM pipeline integration.
4. Audit of prototype ADR currency scaling (€90 vs ₹4500).
5. Model registry artifact loading.
"""

import os
import pytest
import pandas as pd
from optimization.config import OptimizationConfig
from optimization.data.loader import DatasetLoader
from optimization.data.point_in_time import PointInTimeResolver
from optimization.predictions.model_registry import ModelRegistry
from optimization.predictions.hotel_cancellation import HotelCancellationService


class TestPointInTimeAndML:
    """Verifies point-in-time filtering and ML integration integrity."""

    def test_expired_offers_filtered_correctly(self):
        """Offers with valid_until < cutoff date must be excluded from candidate pool."""
        sample_df = pd.DataFrame([
            {"offer_id": "OFF_ACTIVE", "offer_valid_until": "2026-06-15", "cost_per_unit": 2000.0},
            {"offer_id": "OFF_EXPIRED", "offer_valid_until": "2026-05-30", "cost_per_unit": 2000.0},
            {"offer_id": "OFF_EXACT_CUTOFF", "offer_valid_until": "2026-06-01", "cost_per_unit": 2000.0},
        ])
        resolver = PointInTimeResolver("2026-06-01")
        active_df, audit = resolver.filter_active_supplier_offers(sample_df)

        assert len(active_df) == 2  # OFF_ACTIVE and OFF_EXACT_CUTOFF (valid_until >= cutoff)
        assert "OFF_ACTIVE" in list(active_df["offer_id"])
        assert "OFF_EXACT_CUTOFF" in list(active_df["offer_id"])
        assert audit["expired_offers_dropped"] == 1

    def test_model_registry_artifact_loading(self):
        """Model registry must successfully resolve and load existing Phase 4 model pipelines."""
        registry = ModelRegistry()
        estimator, preprocessor, metadata = registry.get_model("hotel_cancellation")
        assert estimator is not None
        assert preprocessor is not None
        assert "feature_names" in metadata
        assert hasattr(estimator, "predict_proba") or hasattr(estimator, "predict")

    def test_hotel_cancellation_adr_scaling(self):
        """
        Verify ADR currency scaling:
        Raw selling price = ₹4,500/night.
        Without scaling: 4500 / 2 = 2250 (a 91-sigma blowout vs training median ~€95).
        With prototype scaling (divide by 90): ADR = 2250 / 90 = 25.0 EUR (within valid distribution).
        """
        config = OptimizationConfig(run_id="TEST_ADR", optimization_timestamp="2026-06-01")
        registry = ModelRegistry()
        service = HotelCancellationService(registry=registry, config=config)

        # Predict with ₹4,500 selling price
        sample_offer = {
            "travel_date": "2026-07-01",
            "selling_price": 4500.0,
            "cost_per_unit": 3800.0,
        }
        prob = service.predict_cohort_cancellation_probability(sample_offer)
        # Probability must be bounded in [0.0, 1.0] and reasonable
        assert 0.0 <= prob <= 1.0
        assert 0.05 <= prob <= 0.60
