"""
Tests for Model Selection and Champion Model Rules.
Verifies that champion selection adheres to metric directionality (maximize F1 vs minimize MAE)
and strictly enforces baseline outperformance checks.
"""

import pytest
import pandas as pd
from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.model_selection import select_champion_model


def test_select_champion_classification():
    task_cfg = TaskConfig(
        task_name="hotel_cancellation",
        dataset_name="dummy_ds",
        task_type=TaskType.BINARY_CLASSIFICATION,
        target_column="target",
        feature_columns=["f1"],
        primary_metric="f1_score",  # Higher is better
    )

    comparison_df = pd.DataFrame([
        {"model_name": "dummy", "mean_f1_score": 0.40, "std_f1_score": 0.01, "mean_accuracy": 0.60},
        {"model_name": "random_forest", "mean_f1_score": 0.75, "std_f1_score": 0.02, "mean_accuracy": 0.82},
        {"model_name": "lightgbm_tuned", "mean_f1_score": 0.82, "std_f1_score": 0.01, "mean_accuracy": 0.87},
    ])

    champion_name, rationale, champion_row = select_champion_model(
        task_config=task_cfg,
        comparison_df=comparison_df,
        baseline_model_names=("dummy",),
    )

    assert champion_name == "lightgbm_tuned"
    assert champion_row["mean_f1_score"] == 0.82
    assert "outperforms" in rationale.lower() or "selected" in rationale.lower()


def test_select_champion_regression():
    task_cfg = TaskConfig(
        task_name="flight_price",
        dataset_name="dummy_ds",
        task_type=TaskType.REGRESSION,
        target_column="price",
        feature_columns=["f1"],
        primary_metric="mae",  # Lower is better
    )

    comparison_df = pd.DataFrame([
        {"model_name": "dummy", "mean_mae": 5000.0, "std_mae": 50.0},
        {"model_name": "linear_regression", "mean_mae": 4200.0, "std_mae": 40.0},
        {"model_name": "xgboost", "mean_mae": 2400.0, "std_mae": 30.0},
    ])

    champion_name, rationale, champion_row = select_champion_model(
        task_config=task_cfg,
        comparison_df=comparison_df,
        baseline_model_names=("dummy", "linear_regression"),
    )

    assert champion_name == "xgboost"
    assert champion_row["mean_mae"] == 2400.0


def test_champion_selection_when_baseline_wins():
    # If advanced model fails to beat baseline
    task_cfg = TaskConfig(
        task_name="sparse_demand",
        dataset_name="dummy_ds",
        task_type=TaskType.TIME_SERIES_REGRESSION,
        target_column="count",
        feature_columns=["f1"],
        primary_metric="mae",  # Lower is better
    )

    comparison_df = pd.DataFrame([
        {"model_name": "naive", "mean_mae": 1.5, "std_mae": 0.1},
        {"model_name": "overfitted_rf", "mean_mae": 3.8, "std_mae": 0.3},
    ])

    champion_name, rationale, champion_row = select_champion_model(
        task_config=task_cfg,
        comparison_df=comparison_df,
        baseline_model_names=("naive",),
    )

    assert champion_name == "naive"
    assert champion_row["mean_mae"] == 1.5
