"""
TBO InventoryIQ - Cross-Validation Engine (Phase 4)
Executes reproducible K-Fold and TimeSeries cross-validation,
recording fold-level metrics, variance, and timing diagnostics.
"""

from typing import Dict, Any, List, Optional, Tuple
import time
import numpy as np
import pandas as pd
import logging

from modeling.config import TaskType, ValidationStrategy, RANDOM_SEED
from modeling.registry.task_registry import TaskConfig
from modeling.preprocessing import build_preprocessor, partition_features
from modeling.splitters import get_cross_validation_splitter
from modeling.model_factory import create_model
from modeling.trainer import train_single_model, ModelArtifact
from modeling.metrics import compute_metrics, MetricResult
from modeling.leakage_detection import audit_task_leakage

logger = logging.getLogger(__name__)


class CrossValidationResult:
    """Encapsulates the aggregated results and fold-level statistics of a CV run."""
    def __init__(
        self,
        task_name: str,
        model_name: str,
        fold_metrics: List[Dict[str, float]],
        mean_metrics: Dict[str, float],
        std_metrics: Dict[str, float],
        mean_fit_time: float,
        mean_inference_time: float,
        total_duration: float,
        n_splits: int,
        oof_predictions: Optional[np.ndarray] = None,
    ):
        self.task_name = task_name
        self.model_name = model_name
        self.fold_metrics = fold_metrics
        self.mean_metrics = mean_metrics
        self.std_metrics = std_metrics
        self.mean_fit_time = round(mean_fit_time, 4)
        self.mean_inference_time = round(mean_inference_time, 6)
        self.total_duration = round(total_duration, 2)
        self.n_splits = n_splits
        self.oof_predictions = oof_predictions

    def to_dict(self) -> Dict[str, Any]:
        """Converts CV summary into a flat dictionary suitable for reporting."""
        row = {
            "task_name": self.task_name,
            "model_name": self.model_name,
            "n_splits": self.n_splits,
            "mean_fit_time_sec": self.mean_fit_time,
            "mean_inference_time_sec": self.mean_inference_time,
            "total_duration_sec": self.total_duration,
        }
        for metric, val in self.mean_metrics.items():
            row[f"mean_{metric}"] = val
            row[f"std_{metric}"] = self.std_metrics.get(metric, 0.0)
        return row


def execute_cross_validation(
    task_config: TaskConfig,
    model_name: str,
    X: pd.DataFrame,
    y: pd.Series,
    groups: Optional[pd.Series] = None,
    model_kwargs: Optional[Dict[str, Any]] = None,
) -> CrossValidationResult:
    """
    Executes K-fold cross-validation with strict fold-level preprocessing,
    mandatory fail-closed leakage checks, and metric tracking.
    """
    # Mandatory fail-closed leakage check at CV entry point
    audit_task_leakage(task_config, X)

    total_start = time.perf_counter()
    m_kwargs = model_kwargs or {}
    n_splits = task_config.n_splits

    # 1. Obtain Cross-Validation Splitter
    is_time_based = task_config.validation_strategy in [
        ValidationStrategy.TIME_SERIES_SPLIT,
        ValidationStrategy.CHRONOLOGICAL_SPLIT,
    ]
    gap = task_config.business_params.get("embargo_gap_days", 0) if is_time_based else 0
    splitter = None
    if task_config.validation_strategy == ValidationStrategy.TIME_SERIES_SPLIT and groups is not None and gap > 0:
        from modeling.splitters import PurgedGroupTimeSeriesSplit
        n_unique_dates = len(pd.Series(groups).dropna().unique())
        if n_unique_dates >= (n_splits + 1):
            splitter = PurgedGroupTimeSeriesSplit(n_splits=n_splits, embargo_gap=gap)
    if splitter is None:
        splitter = get_cross_validation_splitter(
            task_config.validation_strategy,
            n_splits=n_splits,
            shuffle=(not is_time_based),
            random_state=RANDOM_SEED,
            gap=gap,
        )

    # 2. Partition Features
    num_cols, cat_cols = partition_features(
        X,
        override_cat=task_config.categorical_columns,
        override_num=task_config.numerical_columns,
    )

    scale_numeric = model_name in ["logistic_regression", "linear_regression"]
    is_classifier = task_config.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]

    fold_metrics_list = []
    fit_times = []
    inference_times = []
    oof_preds = np.zeros(len(X), dtype=float) if not is_classifier else np.zeros((len(X), len(np.unique(y))))

    logger.info(
        f"Starting {n_splits}-fold CV for '{task_config.task_name}' with model '{model_name}'..."
    )

    # Split generator passing calendar date groups if time-based
    split_gen = splitter.split(X, y if is_classifier else None, groups=groups)

    for fold_idx, (train_idx, val_idx) in enumerate(split_gen, start=1):
        X_train, y_train = X.iloc[train_idx].copy(), y.iloc[train_idx].copy()
        X_val, y_val = X.iloc[val_idx].copy(), y.iloc[val_idx].copy()

        # Build fresh preprocessor per fold (zero test leakage)
        preprocessor = build_preprocessor(
            num_cols,
            cat_cols,
            scale_numeric=scale_numeric,
            use_one_hot=False,
        )

        # Build fresh estimator
        estimator = create_model(model_name, task_config.task_type, **m_kwargs)

        # Train model
        artifact = train_single_model(
            estimator,
            preprocessor,
            X_train,
            y_train,
            task_config.task_type,
            model_name=model_name,
        )
        fit_times.append(artifact.fit_time_seconds)

        # Evaluate on validation fold
        val_preds, inf_time = artifact.predict(X_val)
        val_prob = artifact.predict_proba(X_val) if is_classifier else None
        inference_times.append(inf_time)

        # Record out-of-fold predictions
        if not is_classifier:
            oof_preds[val_idx] = val_preds
        elif val_prob is not None:
            if val_prob.shape[1] == oof_preds.shape[1]:
                oof_preds[val_idx] = val_prob
            elif hasattr(artifact.estimator, "classes_"):
                for col_i, cls_val in enumerate(artifact.estimator.classes_):
                    cls_idx = int(cls_val) if isinstance(cls_val, (int, np.integer)) and 0 <= int(cls_val) < oof_preds.shape[1] else None
                    if cls_idx is not None:
                        oof_preds[val_idx, cls_idx] = val_prob[:, col_i]

        # Compute all metrics for this fold
        metrics_dict = compute_metrics(
            task_config.task_type,
            y_val.to_numpy(),
            val_preds,
            y_prob=val_prob,
            business_params=task_config.business_params,
        )

        fold_row = {"fold": fold_idx}
        for k, v in metrics_dict.items():
            if np.isfinite(v.value):
                fold_row[k] = v.value
        fold_metrics_list.append(fold_row)

    total_elapsed = time.perf_counter() - total_start

    # Compute mean and standard deviation across folds
    df_folds = pd.DataFrame(fold_metrics_list).drop(columns=["fold"], errors="ignore")
    mean_metrics = {k: round(float(df_folds[k].mean()), 4) for k in df_folds.columns if pd.notnull(df_folds[k].mean())}
    std_metrics = {k: round(float(df_folds[k].std()), 4) for k in df_folds.columns if pd.notnull(df_folds[k].std())}

    logger.info(
        f"Completed CV for '{model_name}': primary={task_config.primary_metric}="
        f"{mean_metrics.get(task_config.primary_metric, 'N/A')} "
        f"(std: {std_metrics.get(task_config.primary_metric, 0.0)}) in {total_elapsed:.1f}s"
    )

    return CrossValidationResult(
        task_name=task_config.task_name,
        model_name=model_name,
        fold_metrics=fold_metrics_list,
        mean_metrics=mean_metrics,
        std_metrics=std_metrics,
        mean_fit_time=float(np.mean(fit_times)),
        mean_inference_time=float(np.mean(inference_times)),
        total_duration=total_elapsed,
        n_splits=n_splits,
        oof_predictions=oof_preds,
    )
