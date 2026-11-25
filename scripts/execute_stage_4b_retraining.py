"""
TBO InventoryIQ - Stage 4B Controlled Retraining & Evaluation Harness
Executes complete candidate model training across all four predictive tasks,
saves artifacts in isolated candidate directories (preserving existing champions),
and performs comprehensive champion-vs-candidate-vs-baseline comparisons.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import sys
import json
import time
import logging
import numpy as np
import pandas as pd

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from modeling.config import TaskType, ValidationStrategy, RANDOM_SEED, MODELS_DIR
from modeling.registry.task_registry import TaskRegistry
from modeling.pipeline import run_task_pipeline
from modeling.model_persistence import load_model_artifact
from modeling.evaluator import evaluate_test_set
from modeling.metrics import (
    compute_metrics,
    optimize_classification_threshold,
    compute_stockout_metrics,
    safe_wape,
    compute_forecast_bias,
)
from modeling.baselines import create_baseline_model

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Stage4B_Retraining")


def evaluate_flight_price_horizons(
    candidate_artifact,
    champion_artifact,
    X_test: pd.DataFrame,
    X_test_champ: pd.DataFrame,
    y_test: pd.Series,
    task_cfg,
) -> Dict[str, Any]:
    """Evaluates flight price models across 1-7d, 8-14d, and 15+d horizons."""
    logger.info("Evaluating Flight Price performance across booking horizons...")
    if "days_left" not in X_test.columns:
        logger.warning("'days_left' column not found in flight price test features.")
        return {}

    days_left = X_test["days_left"]
    horizons = {
        "immediate_departure_1_7d": (days_left <= 7),
        "intermediate_8_14d": ((days_left >= 8) & (days_left <= 14)),
        "advance_booking_15plus_d": (days_left >= 15),
    }

    cand_preds, _ = candidate_artifact.predict(X_test)
    champ_preds, _ = champion_artifact.predict(X_test_champ)
    y_test_arr = y_test.to_numpy()

    horizon_results = {}
    for h_name, mask in horizons.items():
        sub_mask = mask.to_numpy()
        n_sub = int(sub_mask.sum())
        if n_sub == 0:
            continue

        sub_y = y_test_arr[sub_mask]
        sub_cand_p = cand_preds[sub_mask]
        sub_champ_p = champ_preds[sub_mask]

        cand_metrics = compute_metrics(task_cfg.task_type, sub_y, sub_cand_p)
        champ_metrics = compute_metrics(task_cfg.task_type, sub_y, sub_champ_p)

        cand_bias = compute_forecast_bias(sub_y, sub_cand_p)
        champ_bias = compute_forecast_bias(sub_y, sub_champ_p)

        horizon_results[h_name] = {
            "record_count": n_sub,
            "candidate": {
                "mae": cand_metrics["mae"].value,
                "rmse": cand_metrics["rmse"].value,
                "r2": cand_metrics["r2"].value,
                "wape": cand_metrics["wape"].value,
                "bias": round(cand_bias, 4),
            },
            "champion": {
                "mae": champ_metrics["mae"].value,
                "rmse": champ_metrics["rmse"].value,
                "r2": champ_metrics["r2"].value,
                "wape": champ_metrics["wape"].value,
                "bias": round(champ_bias, 4),
            },
        }

    return horizon_results


def evaluate_inventory_subgroups(
    candidate_artifact,
    champion_artifact,
    X_test: pd.DataFrame,
    X_test_champ: pd.DataFrame,
    y_test: pd.Series,
    df_full: pd.DataFrame,
    test_indices: np.ndarray,
    task_cfg,
    stockout_threshold: float = 5.0,
) -> Dict[str, Any]:
    """Evaluates inventory forecasting models independently for ROOM_NIGHT and SEAT."""
    logger.info("Evaluating Inventory Forecasting performance by inventory type...")
    test_df = df_full.iloc[test_indices].copy().reset_index(drop=True)
    if "inventory_type" not in test_df.columns:
        logger.warning("'inventory_type' not found in test metadata DataFrame.")
        return {}

    cand_preds, _ = candidate_artifact.predict(X_test)
    champ_preds, _ = champion_artifact.predict(X_test_champ)
    y_test_arr = y_test.to_numpy()

    subgroup_results = {}
    for inv_type in ["ROOM_NIGHT", "SEAT", "HOTEL", "FLIGHT"]:
        mask = (test_df["inventory_type"] == inv_type).to_numpy()
        n_sub = int(mask.sum())
        if n_sub == 0:
            continue

        sub_y = y_test_arr[mask]
        sub_cand_p = cand_preds[mask]
        sub_champ_p = champ_preds[mask]

        cand_m = compute_metrics(task_cfg.task_type, sub_y, sub_cand_p, business_params={"stockout_threshold_units": stockout_threshold})
        champ_m = compute_metrics(task_cfg.task_type, sub_y, sub_champ_p, business_params={"stockout_threshold_units": stockout_threshold})

        subgroup_results[inv_type] = {
            "record_count": n_sub,
            "candidate": {
                "mae": cand_m["mae"].value,
                "rmse": cand_m["rmse"].value,
                "wape": cand_m["wape"].value,
                "stockout_recall": cand_m.get("stockout_recall", type('', (), {'value': np.nan})()).value,
                "stockout_precision": cand_m.get("stockout_precision", type('', (), {'value': np.nan})()).value,
                "stockout_f1": cand_m.get("stockout_f1", type('', (), {'value': np.nan})()).value,
            },
            "champion": {
                "mae": champ_m["mae"].value,
                "rmse": champ_m["rmse"].value,
                "wape": champ_m["wape"].value,
                "stockout_recall": champ_m.get("stockout_recall", type('', (), {'value': np.nan})()).value,
                "stockout_precision": champ_m.get("stockout_precision", type('', (), {'value': np.nan})()).value,
                "stockout_f1": champ_m.get("stockout_f1", type('', (), {'value': np.nan})()).value,
            },
        }

    return subgroup_results


def evaluate_demand_baselines(
    candidate_artifact,
    champion_artifact,
    X_test: pd.DataFrame,
    X_test_champ: pd.DataFrame,
    y_test: pd.Series,
    task_cfg,
) -> Dict[str, Any]:
    """Compares candidate against naive and seasonal naive baselines."""
    y_test_arr = y_test.to_numpy()
    cand_preds, _ = candidate_artifact.predict(X_test)
    champ_preds, _ = champion_artifact.predict(X_test_champ)

    # Naive baseline (lag_1 persistence)
    naive_preds = X_test["lag_1"].to_numpy() if "lag_1" in X_test.columns else np.zeros(len(y_test_arr))
    # Seasonal naive baseline (lag_7 persistence)
    snaive_preds = X_test["lag_7"].to_numpy() if "lag_7" in X_test.columns else np.zeros(len(y_test_arr))

    results = {}
    for name, preds in [
        ("candidate", cand_preds),
        ("champion", champ_preds),
        ("naive_baseline", naive_preds),
        ("seasonal_naive_baseline", snaive_preds),
    ]:
        m = compute_metrics(task_cfg.task_type, y_test_arr, preds)
        bias = compute_forecast_bias(y_test_arr, preds)
        results[name] = {
            "mae": m["mae"].value,
            "rmse": m["rmse"].value,
            "wape": m["wape"].value,
            "r2": m["r2"].value,
            "bias": round(bias, 4),
        }
    return results


def run_stage_4b() -> Dict[str, Any]:
    """Executes Stage 4B retraining and champion evaluation across all 4 tasks."""
    logger.info("==========================================================================")
    logger.info("EXECUTING STAGE 4B: CONTROLLED ML RETRAINING & EVALUATION")
    logger.info("==========================================================================")

    registry = TaskRegistry()
    tasks = ["hotel_cancellation", "flight_price", "demand_forecasting", "inventory_forecasting"]
    candidates_root = WORKSPACE_ROOT / "data" / "models" / "candidates"
    candidates_root.mkdir(parents=True, exist_ok=True)

    stage4b_summary = {}

    for task_name in tasks:
        logger.info(f"\n>>> [Stage 4B] Starting Task: '{task_name}' <<<")
        task_cfg = registry.get(task_name)
        candidate_dir = candidates_root / task_name

        # 1. Retrain Candidate Model using Corrected Pipeline
        # Output directory is explicitly set to candidates_root / task_name (NEVER overwriting existing champion)
        pipe_res = run_task_pipeline(
            task_name=task_name,
            n_iter_tuning=5,
            sample_size=None,  # Full dataset execution
            output_dir=candidate_dir,
        )

        cand_artifact = pipe_res["champion_artifact"]
        cand_eval = pipe_res["test_evaluation"]
        cand_model_name = pipe_res["champion_model"]
        X_test = pipe_res["X_test"]
        y_test = pipe_res["y_test"]
        df_full = pipe_res["df_full"]
        test_indices = pipe_res["test_indices"]
        threshold_provenance = pipe_res["threshold_provenance"]
        frozen_thresh = pipe_res["frozen_threshold"]

        # 2. Load Existing Champion Model
        logger.info(f"Loading existing champion model for '{task_name}'...")
        champ_artifact, champ_metadata = load_model_artifact(task_name)
        champ_model_name = champ_metadata["model_name"]

        # 3. Align Test Features for Existing Champion (using df_full if champion expects legacy features)
        missing_champ_features = [col for col in champ_artifact.feature_names if col not in X_test.columns]
        if missing_champ_features:
            logger.info(
                f"Existing champion for '{task_name}' requires legacy features: {missing_champ_features}. "
                f"Aligning from df_full test partition for comparative evaluation."
            )
            X_test_champ = df_full.iloc[test_indices][champ_artifact.feature_names].copy().reset_index(drop=True)
        else:
            X_test_champ = X_test[champ_artifact.feature_names].copy().reset_index(drop=True)

        champ_eval = evaluate_test_set(
            task_cfg,
            champ_artifact,
            X_test_champ,
            y_test,
            frozen_threshold=frozen_thresh,
            threshold_selection_metadata={"note": "Evaluated on Stage 4B test holdout with original champion features"},
        )

        # 4. Task-Specific Deep-Dive Evaluations
        deep_dive = {}
        if task_name == "flight_price":
            deep_dive["horizons"] = evaluate_flight_price_horizons(
                cand_artifact, champ_artifact, X_test, X_test_champ, y_test, task_cfg
            )
        elif task_name == "inventory_forecasting":
            stockout_th = float(task_cfg.business_params.get("stockout_threshold_units", 5.0))
            deep_dive["subgroups"] = evaluate_inventory_subgroups(
                cand_artifact, champ_artifact, X_test, X_test_champ, y_test, df_full, test_indices, task_cfg, stockout_th
            )
        elif task_name == "demand_forecasting":
            deep_dive["baselines_and_subgroups"] = evaluate_demand_baselines(
                cand_artifact, champ_artifact, X_test, X_test_champ, y_test, task_cfg
            )

        # 5. Formulate Champion vs Candidate Recommendation
        primary = task_cfg.primary_metric
        cand_score = cand_eval["metrics"].get(primary)
        champ_score = champ_eval["metrics"].get(primary)

        # Task-specific recommendation logic
        if task_name == "hotel_cancellation":
            # Leakage eliminated: candidate has valid booking-time features, while old champion had full-dataset target leak
            rec = "PROMOTE CANDIDATE"
            rec_reason = (
                f"Candidate '{cand_model_name}' (F1={cand_score:.4f}) is fully leak-free (target encoding columns removed, "
                f"decision threshold T*={frozen_thresh:.4f} frozen from OOF). "
                f"Previous champion '{champ_model_name}' had artificial inflation from full-dataset target encodings."
            )
        elif task_name == "demand_forecasting":
            # Time-series purged panel
            cand_mae = cand_eval["metrics"].get("mae")
            champ_mae = champ_eval["metrics"].get("mae")
            if cand_mae <= champ_mae:
                rec = "PROMOTE CANDIDATE"
                rec_reason = f"Candidate achieves superior MAE ({cand_mae:.4f} vs {champ_mae:.4f}) with 7d calendar embargo."
            else:
                rec = "REQUIRES FURTHER INVESTIGATION"
                rec_reason = f"Candidate MAE ({cand_mae:.4f}) vs Champion ({champ_mae:.4f}). Candidate trained on clean chronological panel."
        elif task_name == "flight_price":
            cand_mae = cand_eval["metrics"].get("mae")
            champ_mae = champ_eval["metrics"].get("mae")
            if cand_mae <= champ_mae:
                rec = "PROMOTE CANDIDATE"
                rec_reason = f"Candidate achieves superior MAE ({cand_mae:.2f} vs {champ_mae:.2f})."
            else:
                rec = "RETAIN EXISTING CHAMPION"
                rec_reason = f"Existing champion achieved lower MAE ({champ_mae:.2f} vs {cand_mae:.2f})."
        elif task_name == "inventory_forecasting":
            cand_mae = cand_eval["metrics"].get("mae")
            champ_mae = champ_eval["metrics"].get("mae")
            if cand_mae <= champ_mae:
                rec = "PROMOTE CANDIDATE"
                rec_reason = f"Candidate achieves superior MAE ({cand_mae:.4f} vs {champ_mae:.4f}) with aligned stockout threshold."
            else:
                rec = "RETAIN EXISTING CHAMPION"
                rec_reason = f"Existing champion achieved lower MAE ({champ_mae:.4f} vs {cand_mae:.4f})."

        task_summary = {
            "task_name": task_name,
            "candidate_model_name": cand_model_name,
            "candidate_artifact_path": str(candidate_dir),
            "champion_model_name": champ_model_name,
            "primary_metric": primary,
            "candidate_metrics": cand_eval["metrics"],
            "champion_metrics": champ_eval["metrics"],
            "test_records_count": len(X_test),
            "threshold_provenance": threshold_provenance,
            "frozen_threshold": frozen_thresh,
            "deep_dive": deep_dive,
            "recommendation": rec,
            "recommendation_rationale": rec_reason,
            "comparison_df": pipe_res["comparison_df"].to_dict(orient="records"),
        }
        stage4b_summary[task_name] = task_summary
        logger.info(f"Task '{task_name}' Completed. Recommendation: {rec}")

    # 6. Save Stage 4B Evaluation Results
    output_json_path = WORKSPACE_ROOT / "reports" / "model_evaluation" / "stage_4b_retraining_results.json"
    with open(output_json_path, "w", encoding="utf-8") as f:
        # Convert non-serializable items
        def sanitize(obj):
            if isinstance(obj, (np.floating, float)):
                return None if np.isnan(obj) else float(obj)
            if isinstance(obj, (np.integer, int)):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [sanitize(v) for v in obj]
            return str(obj)

        json.dump(sanitize(stage4b_summary), f, indent=2)

    logger.info(f"\n==========================================================================")
    logger.info(f"STAGE 4B COMPLETE. Results written to: {output_json_path}")
    logger.info(f"==========================================================================")
    return stage4b_summary


if __name__ == "__main__":
    run_stage_4b()
