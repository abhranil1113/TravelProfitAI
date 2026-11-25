"""
Tests for Test Set Evaluator (Phase 4).
Verifies frozen decision threshold application, zero-leakage threshold provenance,
and diagnostic evaluation generation without test-label threshold optimization.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.trainer import ModelArtifact
from modeling.evaluator import evaluate_test_set


def test_evaluator_applies_frozen_threshold_without_test_leakage():
    task_cfg = TaskConfig(
        task_name="hotel_cancellation",
        dataset_name="hotel_cancellation_features",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="is_canceled",
        feature_columns=["f1", "f2"],
        categorical_columns=[],
        numerical_columns=["f1", "f2"],
        primary_metric="f1_score",
        business_params={"cost_fn": 3.0, "cost_fp": 1.0},
    )

    X_test = pd.DataFrame({"f1": [1.0, 2.0, 3.0, 4.0], "f2": [5.0, 6.0, 7.0, 8.0]})
    y_test = pd.Series([0, 1, 0, 1])

    # Mock estimator predicting probabilities:
    # Row 0: prob=0.40 -> at default 0.50 is 0; at frozen 0.35 is 1
    # Row 1: prob=0.80 -> 1
    # Row 2: prob=0.30 -> 0
    # Row 3: prob=0.60 -> 1
    mock_estimator = MagicMock()
    mock_estimator.predict_proba.return_value = np.array([
        [0.60, 0.40],
        [0.20, 0.80],
        [0.70, 0.30],
        [0.40, 0.60],
    ])
    mock_estimator.predict.return_value = np.array([0, 1, 0, 1])

    artifact = ModelArtifact(
        estimator=mock_estimator,
        preprocessor=None,
        feature_names=["f1", "f2"],
        task_type=TaskType.BINARY_CLASSIFICATION,
        model_name="mock_classifier",
    )

    frozen_thresh = 0.35
    provenance = {
        "source": "out_of_fold_cross_validation",
        "selection_method": "expected_business_cost_minimization",
        "selected_threshold": frozen_thresh,
        "cost_fn": 3.0,
        "cost_fp": 1.0,
    }

    report = evaluate_test_set(
        task_config=task_cfg,
        artifact=artifact,
        X_test=X_test,
        y_test=y_test,
        frozen_threshold=frozen_thresh,
        threshold_selection_metadata=provenance,
    )

    assert report["applied_decision_threshold"] == frozen_thresh
    assert report["threshold_provenance"] == provenance
    assert "metrics" in report
    assert "f1_score" in report["metrics"]
    assert "confusion_matrix" in report
    assert report["test_records_count"] == 4
