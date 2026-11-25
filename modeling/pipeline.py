"""
TBO InventoryIQ - Master ML Pipeline Orchestrator (Phase 4)
Executes end-to-end dataset preparation, leakage auditing, cross-validation,
hyperparameter tuning, model selection, holdout evaluation, persistence, and reporting.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import time
import logging
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

from modeling.config import TaskType, ValidationStrategy, RANDOM_SEED
from modeling.registry.task_registry import TaskRegistry, TaskConfig
from modeling.target_builder import prepare_task_dataset
from modeling.feature_validation import validate_modeling_features
from modeling.leakage_detection import audit_task_leakage
from modeling.model_factory import create_model
from modeling.preprocessing import build_preprocessor, partition_features
from modeling.trainer import train_single_model
from modeling.cross_validator import execute_cross_validation
from modeling.hyperparameter_tuning import tune_model_hyperparameters
from modeling.model_comparison import ModelComparisonEngine
from modeling.model_selection import select_champion_model
from modeling.evaluator import evaluate_test_set
from modeling.metrics import optimize_classification_threshold
from modeling.model_persistence import save_model_artifact
from modeling.report_generator import export_task_reports, generate_model_comparison_summary

logger = logging.getLogger(__name__)


def run_task_pipeline(
    task_name: str,
    n_iter_tuning: int = 5,
    sample_size: Optional[int] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes the complete machine learning lifecycle for a single registered task.
    """
    logger.info(f"================================================================")
    logger.info(f"Starting ML Pipeline Execution for Task: '{task_name}'")
    logger.info(f"================================================================")

    # 1. Retrieve Task Configuration
    registry = TaskRegistry()
    task_cfg = registry.get(task_name)

    # 2. Dataset Preparation & Target Construction
    X, y, df_full = prepare_task_dataset(task_cfg)

    # 3. Detect temporal structure and calendar date column
    is_temporal = task_cfg.validation_strategy in [
        ValidationStrategy.TIME_SERIES_SPLIT,
        ValidationStrategy.CHRONOLOGICAL_SPLIT,
    ]
    date_col = None
    for cand in ["date", "snapshot_date", "booking_date", "arrival_date"]:
        if cand in df_full.columns:
            date_col = cand
            break

    dates_full = pd.to_datetime(df_full[date_col]) if date_col is not None else None

    # 4. Train-Test Split (15% untouched holdout test set respecting temporal boundaries)
    # The holdout test set is determined on the FULL dataset to guarantee test stability.
    if is_temporal and dates_full is not None:
        unique_dates = pd.Series(np.sort(dates_full.unique()))
        n_unique = len(unique_dates)
        train_date_end_idx = int(n_unique * 0.85)
        train_end_date = unique_dates.iloc[train_date_end_idx]
        embargo_days = int(task_cfg.business_params.get("embargo_gap_days", 0))

        if embargo_days > 0:
            test_start_date = train_end_date + pd.Timedelta(days=embargo_days)
            train_mask = dates_full <= train_end_date
            test_mask = dates_full > test_start_date
        else:
            train_mask = dates_full <= train_end_date
            test_mask = dates_full > train_end_date

        train_indices = np.where(train_mask)[0]
        test_indices = np.where(test_mask)[0]

        X_train_full = X.iloc[train_indices].copy().reset_index(drop=True)
        y_train_full = y.iloc[train_indices].copy().reset_index(drop=True)
        X_test = X.iloc[test_indices].copy().reset_index(drop=True)
        y_test = y.iloc[test_indices].copy().reset_index(drop=True)
        groups_train_full = dates_full.iloc[train_indices].copy().reset_index(drop=True)
        test_dates = dates_full.iloc[test_indices]
        train_dates = dates_full.iloc[train_indices]

        date_ranges = {
            "date_column": date_col,
            "dataset_min_date": str(dates_full.min()),
            "dataset_max_date": str(dates_full.max()),
            "train_min_date": str(train_dates.min()),
            "train_max_date": str(train_dates.max()),
            "test_min_date": str(test_dates.min()),
            "test_max_date": str(test_dates.max()),
            "embargo_gap_days": embargo_days,
        }
    elif is_temporal:
        split_idx = int(len(X) * 0.85)
        train_indices = np.arange(split_idx)
        test_indices = np.arange(split_idx, len(X))
        X_train_full = X.iloc[train_indices].copy().reset_index(drop=True)
        y_train_full = y.iloc[train_indices].copy().reset_index(drop=True)
        X_test = X.iloc[test_indices].copy().reset_index(drop=True)
        y_test = y.iloc[test_indices].copy().reset_index(drop=True)
        groups_train_full = None
        date_ranges = {}
    else:
        is_classif = task_cfg.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]
        train_indices, test_indices = train_test_split(
            np.arange(len(X)),
            test_size=0.15,
            stratify=y if is_classif else None,
            random_state=RANDOM_SEED,
        )
        X_train_full = X.iloc[train_indices].copy().reset_index(drop=True)
        y_train_full = y.iloc[train_indices].copy().reset_index(drop=True)
        X_test = X.iloc[test_indices].copy().reset_index(drop=True)
        y_test = y.iloc[test_indices].copy().reset_index(drop=True)
        groups_train_full = None
        date_ranges = {}

    # 5. Apply Rapid Profiling Sampling strictly within Training Data (F-05 Remediation)
    # X_test is fixed and NEVER shifted or compressed by sample_size.
    if sample_size is not None and len(X_train_full) > sample_size:
        logger.info(
            f"Sampling {sample_size:,} training records from {len(X_train_full):,} for task '{task_name}'. "
            f"Holdout test set ({len(X_test):,} rows) remains fixed."
        )
        if is_temporal:
            X_train = X_train_full.iloc[-sample_size:].copy().reset_index(drop=True)
            y_train = y_train_full.iloc[-sample_size:].copy().reset_index(drop=True)
            groups_train = groups_train_full.iloc[-sample_size:].copy().reset_index(drop=True) if groups_train_full is not None else None
        else:
            is_classif = task_cfg.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]
            X_train, _, y_train, _ = train_test_split(
                X_train_full,
                y_train_full,
                train_size=sample_size,
                stratify=y_train_full if is_classif else None,
                random_state=RANDOM_SEED,
            )
            groups_train = None
    else:
        X_train = X_train_full
        y_train = y_train_full
        groups_train = groups_train_full

    logger.info(f"Train/Test split: Train={X_train.shape}, Test={X_test.shape}")

    # 6. Feature Validation & Leakage Detection (Fail-Closed Gates)
    val_report = validate_modeling_features(X_train, fail_closed=True)
    leakage_report = audit_task_leakage(task_cfg, X_train)

    # 7. Cross-Validation across Candidate Models (F-02, F-03: passing calendar date groups)
    comparison_engine = ModelComparisonEngine(task_cfg)
    candidate_models = task_cfg.candidate_models

    for model_name in candidate_models:
        cv_res = execute_cross_validation(
            task_cfg,
            model_name,
            X_train,
            y_train,
            groups=groups_train,
        )
        comparison_engine.add_result(cv_res)

    # 8. Hyperparameter Tuning for Advanced Tree Model (LightGBM or XGBoost) (F-04: passing groups)
    tuning_candidate = "lightgbm" if "lightgbm" in candidate_models else ("xgboost" if "xgboost" in candidate_models else None)
    best_tuned_params = {}
    if tuning_candidate and n_iter_tuning > 0:
        logger.info(f"Conducting hyperparameter tuning on top candidate '{tuning_candidate}'...")
        _, best_tuned_params, _ = tune_model_hyperparameters(
            task_cfg,
            tuning_candidate,
            X_train,
            y_train,
            groups=groups_train,
            n_iter=n_iter_tuning,
            cv_splits=3,
        )
        # Evaluate tuned model via cross-validation
        if best_tuned_params:
            tuned_name = f"{tuning_candidate}_tuned"
            cv_tuned = execute_cross_validation(
                task_cfg,
                tuning_candidate,
                X_train,
                y_train,
                groups=groups_train,
                model_kwargs=best_tuned_params,
            )
            cv_tuned.model_name = tuned_name
            comparison_engine.add_result(cv_tuned)

    # 9. Model Comparison & Champion Selection
    comp_df = comparison_engine.build_comparison_dataframe()
    fold_df = comparison_engine.build_fold_results_dataframe()
    champ_model, rationale, champ_summary = select_champion_model(task_cfg, comp_df)

    # 10. Train Final Champion Model on Full X_train and Evaluate on Untouched X_test
    logger.info(f"Training champion model '{champ_model}' on full training set ({len(X_train):,} rows)...")
    base_model_name = champ_model.replace("_tuned", "")
    model_params = best_tuned_params if "_tuned" in champ_model else {}

    num_cols, cat_cols = partition_features(X_train)
    scale_numeric = base_model_name in ["logistic_regression", "linear_regression"]
    final_preprocessor = build_preprocessor(num_cols, cat_cols, scale_numeric=scale_numeric)
    final_estimator = create_model(base_model_name, task_cfg.task_type, **model_params)

    champion_artifact = train_single_model(
        final_estimator,
        final_preprocessor,
        X_train,
        y_train,
        task_cfg.task_type,
        model_name=champ_model,
    )

    # 11. Freeze Decision Threshold on Out-of-Fold Validation Data (F-01 Remediation)
    frozen_threshold = None
    threshold_provenance = None
    if task_cfg.task_type == TaskType.BINARY_CLASSIFICATION:
        cost_fn = float(task_cfg.business_params.get("cost_fn", task_cfg.business_params.get("cost_false_negative", 3.0)))
        cost_fp = float(task_cfg.business_params.get("cost_fp", task_cfg.business_params.get("cost_false_positive", 1.0)))
        optimize_thresh = task_cfg.business_params.get("optimize_threshold", True)

        champ_res = comparison_engine.results.get(champ_model)
        if optimize_thresh and champ_res is not None and champ_res.oof_predictions is not None:
            oof_preds = champ_res.oof_predictions
            oof_probs = oof_preds[:, 1] if oof_preds.ndim == 2 else oof_preds
            valid_oof_mask = ~np.isnan(oof_probs) & (oof_probs > 0)
            if valid_oof_mask.sum() > 0:
                y_train_arr = y_train.to_numpy()
                thresh_opt = optimize_classification_threshold(
                    y_train_arr[valid_oof_mask],
                    oof_probs[valid_oof_mask],
                    cost_fn=cost_fn,
                    cost_fp=cost_fp,
                )
                frozen_threshold = float(thresh_opt["optimal_threshold"])
                threshold_provenance = {
                    "source": "out_of_fold_cross_validation",
                    "selection_method": "expected_business_cost_minimization",
                    "selected_threshold": frozen_threshold,
                    "cost_fn": cost_fn,
                    "cost_fp": cost_fp,
                    "oof_minimal_cost": thresh_opt.get("minimal_cost"),
                    "oof_baseline_cost_at_05": thresh_opt.get("baseline_cost_at_05"),
                    "oof_cost_savings_pct": thresh_opt.get("cost_savings_pct"),
                    "cv_model": champ_model,
                }
                logger.info(
                    f"Selected and frozen decision threshold T*={frozen_threshold:.4f} strictly from OOF validation "
                    f"(expected business cost minimization, cost_fn={cost_fn}, cost_fp={cost_fp})."
                )
            else:
                frozen_threshold = float(task_cfg.business_params.get("threshold", 0.50))
                threshold_provenance = {
                    "source": "default_business_param",
                    "selection_method": "fixed",
                    "selected_threshold": frozen_threshold,
                }
        else:
            frozen_threshold = float(task_cfg.business_params.get("threshold", 0.50))
            threshold_provenance = {
                "source": "default_business_param",
                "selection_method": "fixed",
                "selected_threshold": frozen_threshold,
            }

    # 12. Evaluate on untouched test set with frozen threshold (Zero Test Leakage)
    test_evaluation = evaluate_test_set(
        task_cfg,
        champion_artifact,
        X_test,
        y_test,
        frozen_threshold=frozen_threshold,
        threshold_selection_metadata=threshold_provenance,
    )

    # 13. Persist Champion Model Artifact (F-06, F-07, F-08 Remediation)
    save_model_artifact(
        champion_artifact,
        task_cfg,
        cv_summary=champ_summary,
        test_metrics=test_evaluation["metrics"],
        selection_rationale=rationale,
        output_dir=output_dir,
        dataset_records_count=len(df_full),
        date_ranges=date_ranges,
        threshold_provenance=threshold_provenance,
        df_for_content_hash=df_full,
    )

    # 14. Export Reports
    report_paths = export_task_reports(task_name, comp_df, fold_df, test_evaluation)

    logger.info(f"Task '{task_name}' pipeline successfully completed.")
    return {
        "task_name": task_name,
        "champion_model": champ_model,
        "champion_artifact": champion_artifact,
        "rationale": rationale,
        "comparison_df": comp_df,
        "fold_results_df": fold_df,
        "test_evaluation": test_evaluation,
        "report_paths": report_paths,
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "df_full": df_full,
        "train_indices": train_indices,
        "test_indices": test_indices,
        "date_ranges": date_ranges,
        "threshold_provenance": threshold_provenance,
        "frozen_threshold": frozen_threshold,
    }


def run_phase4_pipeline(
    task_names: Optional[List[str]] = None,
    n_iter_tuning: int = 5,
    sample_sizes: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Executes the entire Phase 4 ML development and benchmarking framework
    across all eligible tasks.
    """
    registry = TaskRegistry()
    tasks_to_run = task_names or ["hotel_cancellation", "flight_price", "demand_forecasting", "inventory_forecasting"]
    samples = sample_sizes or {}

    pipeline_results = {}
    for t_name in tasks_to_run:
        sample_n = samples.get(t_name, None)
        res = run_task_pipeline(t_name, n_iter_tuning=n_iter_tuning, sample_size=sample_n)
        pipeline_results[t_name] = res

    # Generate Cross-Task Summary
    generate_model_comparison_summary(pipeline_results)
    logger.info("All Phase 4 modeling pipelines executed successfully.")
    return pipeline_results


if __name__ == "__main__":
    run_phase4_pipeline()
