"""
TBO InventoryIQ - Master ML Pipeline Orchestrator (Phase 4)
Executes end-to-end dataset preparation, leakage auditing, cross-validation,
hyperparameter tuning, model selection, holdout evaluation, persistence, and reporting.
"""

from typing import Dict, Any, List, Optional
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
from modeling.model_persistence import save_model_artifact
from modeling.report_generator import export_task_reports, generate_model_comparison_summary

logger = logging.getLogger(__name__)


def run_task_pipeline(
    task_name: str,
    n_iter_tuning: int = 5,
    sample_size: Optional[int] = None,
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

    # Apply sampling if specified for rapid profiling (preserving full dataset for final runs)
    if sample_size is not None and len(X) > sample_size:
        logger.info(f"Sampling {sample_size:,} records from {len(X):,} for task '{task_name}'.")
        is_classif = task_cfg.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]
        X, _, y, _ = train_test_split(
            X, y,
            train_size=sample_size,
            stratify=y if is_classif else None,
            random_state=RANDOM_SEED,
        )

    # 3. Feature Validation & Leakage Detection
    val_report = validate_modeling_features(X)
    leakage_report = audit_task_leakage(task_cfg, X)

    # 4. Train-Test Split (15% untouched holdout test set)
    is_time_series = task_cfg.validation_strategy == ValidationStrategy.TIME_SERIES_SPLIT
    if is_time_series:
        split_idx = int(len(X) * 0.85)
        X_train, X_test = X.iloc[:split_idx].copy(), X.iloc[split_idx:].copy()
        y_train, y_test = y.iloc[:split_idx].copy(), y.iloc[split_idx:].copy()
    else:
        is_classif = task_cfg.task_type in [TaskType.BINARY_CLASSIFICATION, TaskType.MULTICLASS_CLASSIFICATION]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=0.15,
            stratify=y if is_classif else None,
            random_state=RANDOM_SEED,
        )

    logger.info(f"Train/Test split: Train={X_train.shape}, Test={X_test.shape}")

    # 5. Cross-Validation across Candidate Models
    comparison_engine = ModelComparisonEngine(task_cfg)
    candidate_models = task_cfg.candidate_models

    for model_name in candidate_models:
        cv_res = execute_cross_validation(task_cfg, model_name, X_train, y_train)
        comparison_engine.add_result(cv_res)

    # 6. Hyperparameter Tuning for Advanced Tree Model (LightGBM or XGBoost)
    tuning_candidate = "lightgbm" if "lightgbm" in candidate_models else ("xgboost" if "xgboost" in candidate_models else None)
    best_tuned_params = {}
    if tuning_candidate and n_iter_tuning > 0:
        logger.info(f"Conducting hyperparameter tuning on top candidate '{tuning_candidate}'...")
        _, best_tuned_params, _ = tune_model_hyperparameters(
            task_cfg,
            tuning_candidate,
            X_train,
            y_train,
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
                model_kwargs=best_tuned_params,
            )
            cv_tuned.model_name = tuned_name
            comparison_engine.add_result(cv_tuned)

    # 7. Model Comparison & Champion Selection
    comp_df = comparison_engine.build_comparison_dataframe()
    fold_df = comparison_engine.build_fold_results_dataframe()
    champ_model, rationale, champ_summary = select_champion_model(task_cfg, comp_df)

    # 8. Train Final Champion Model on Full X_train and Evaluate on Untouched X_test
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

    # Evaluate on untouched test set
    test_evaluation = evaluate_test_set(task_cfg, champion_artifact, X_test, y_test)

    # 9. Persist Champion Model Artifact
    save_model_artifact(
        champion_artifact,
        task_cfg,
        cv_summary=champ_summary,
        test_metrics=test_evaluation["metrics"],
        selection_rationale=rationale,
    )

    # 10. Export Reports
    report_paths = export_task_reports(task_name, comp_df, fold_df, test_evaluation)

    logger.info(f"Task '{task_name}' pipeline successfully completed.")
    return {
        "task_name": task_name,
        "champion_model": champ_model,
        "rationale": rationale,
        "comparison_df": comp_df,
        "fold_results_df": fold_df,
        "test_evaluation": test_evaluation,
        "report_paths": report_paths,
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
