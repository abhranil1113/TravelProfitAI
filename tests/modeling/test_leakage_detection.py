"""
Tests for Data Leakage Detection.
Verifies that target variables, target proxies, and quarantined post-event features
are detected and raise errors, while clean feature matrices pass without issues.
"""

import pytest
import pandas as pd
from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.leakage_detection import audit_task_leakage


def test_leakage_target_in_features():
    cfg = TaskConfig(
        task_name="hotel_cancellation",
        dataset_name="hotel_cancellation_features",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="is_canceled",
        feature_columns=["lead_time_days"],
        numerical_columns=["lead_time_days"],
    )
    X = pd.DataFrame({
        "lead_time_days": [10, 20],
        "is_canceled": [0, 1],
    })

    with pytest.raises(ValueError, match="Target leakage detected"):
        audit_task_leakage(task_config=cfg, X=X)


def test_leakage_quarantined_post_event_features():
    cfg = TaskConfig(
        task_name="hotel_cancellation",
        dataset_name="hotel_cancellation_features",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="is_canceled",
        feature_columns=["lead_time_days"],
        numerical_columns=["lead_time_days"],
    )
    X = pd.DataFrame({
        "lead_time_days": [10, 20],
        "reservation_status": ["Check-Out", "Canceled"],
    })

    with pytest.raises(ValueError, match="Target leakage detected"):
        audit_task_leakage(task_config=cfg, X=X)


def test_clean_features_no_leakage():
    cfg = TaskConfig(
        task_name="hotel_cancellation",
        dataset_name="hotel_cancellation_features",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="is_canceled",
        feature_columns=["lead_time_days", "adr"],
        numerical_columns=["lead_time_days", "adr"],
    )
    X = pd.DataFrame({
        "lead_time_days": [10, 20],
        "adr": [100.0, 150.0],
    })

    audit = audit_task_leakage(task_config=cfg, X=X)
    assert audit["is_clean"] is True
    assert audit["has_critical_leakage"] is False
    assert len(audit["leaked_features"]) == 0
