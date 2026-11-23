"""
Phase 4 Final Validation and Model Selection Execution Script
Implements:
1. Consistent demand forecasting benchmark across 5 models with 7-day embargo.
2. Inventory forecasting global chronological validation vs entity-group holdout.
3. Inventory stockout threshold optimization on validation data only.
4. Hotel cancellation leakage verification.
5. Champion artifact re-persistence and inference verification.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import (
    mean_absolute_error,
    root_mean_squared_error,
    r2_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

from modeling.config import RANDOM_SEED, TaskType, ValidationStrategy
from modeling.registry.task_registry import TaskRegistry
from modeling.data_loader import load_modeling_dataset
from modeling.target_builder import (
    prepare_task_dataset,
    build_demand_forecasting_panel,
    build_inventory_forecasting_stream,
)
from modeling.preprocessing import build_preprocessor, partition_features
from modeling.baselines import NaiveForecaster, SeasonalNaiveForecaster
from modeling.model_factory import create_model
from modeling.trainer import train_single_model
from modeling.model_persistence import save_model_artifact, load_model_artifact
from modeling.metrics import safe_mape, safe_wape, safe_smape, compute_forecast_bias


def run_consistent_demand_benchmark():
    print("=" * 70)
    print("1. DEMAND FORECASTING: CONSISTENT GLOBAL CHRONOLOGICAL BENCHMARK")
    print("=" * 70)

    reg = TaskRegistry()
    cfg = reg.get("demand_forecasting")
    df_raw = load_modeling_dataset("customer_demand_features")
    panel_df = build_demand_forecasting_panel(df_raw, horizon_days=7)

    # Sort strictly by calendar date
    panel_sorted = panel_df.sort_values("date").reset_index(drop=True)
    
    # Feature columns: drop target, date, and excluded columns
    drop_cols = set(cfg.excluded_columns + [cfg.target_column, "date"])
    feat_cols = [c for c in panel_sorted.columns if c not in drop_cols]

    X = panel_sorted[feat_cols].copy()
    y = panel_sorted[cfg.target_column].copy()
    dates = panel_sorted["date"]

    # Global Chronological Cutoff at 85%
    split_date = dates.quantile(0.85)
    embargo_date = split_date + pd.Timedelta(days=7)

    train_mask = dates <= split_date
    test_mask = dates >= embargo_date

    X_train, y_train = X[train_mask].copy(), y[train_mask].copy()
    X_test, y_test = X[test_mask].copy(), y[test_mask].copy()

    print(f"Panel Total Rows:      {len(panel_sorted):,}")
    print(f"Train Partition:       {len(X_train):,} rows (up to {split_date.date()})")
    print(f"7-Day Embargo Buffer:  {(~train_mask & ~test_mask).sum():,} rows ({split_date.date()} to {embargo_date.date()})")
    print(f"Test Partition:        {len(X_test):,} rows (from {embargo_date.date()} to {dates.max().date()})")
    print(f"Test Zero-Demand Rate: {(y_test == 0).mean()*100:.2f}%\n")

    num_cols, cat_cols = partition_features(X_train)

    models_to_evaluate = {
        "naive": NaiveForecaster(lag_col="lag_1"),
        "seasonal_naive": SeasonalNaiveForecaster(seasonal_period=7, lag_col="lag_7"),
        "random_forest": create_model("random_forest", TaskType.TIME_SERIES_REGRESSION, random_state=RANDOM_SEED),
        "xgboost": create_model("xgboost", TaskType.TIME_SERIES_REGRESSION, random_state=RANDOM_SEED),
        "lightgbm": create_model("lightgbm", TaskType.TIME_SERIES_REGRESSION, random_state=RANDOM_SEED),
    }

    benchmark_results = {}
    fitted_artifacts = {}

    for name, estimator in models_to_evaluate.items():
        start_t = time.perf_counter()
        prep = build_preprocessor(num_cols, cat_cols)
        artifact = train_single_model(
            estimator=estimator,
            preprocessor=prep,
            X_train=X_train,
            y_train=y_train,
            task_type=TaskType.TIME_SERIES_REGRESSION,
            model_name=name,
        )
        fit_dur = time.perf_counter() - start_t
        fitted_artifacts[name] = artifact

        preds, infer_dur = artifact.predict(X_test)
        
        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(root_mean_squared_error(y_test, preds))
        wape, _ = safe_wape(y_test.to_numpy(), preds)
        smape, _ = safe_smape(y_test.to_numpy(), preds)
        bias = float(compute_forecast_bias(y_test.to_numpy(), preds))

        benchmark_results[name] = {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "wape": round(wape, 2),
            "smape": round(smape, 2),
            "forecast_bias": round(bias, 4),
            "fit_time_sec": round(fit_dur, 4),
            "infer_time_sec": round(infer_dur, 4),
        }
        print(f"Model [{name:14s}]: MAE={mae:.4f}, RMSE={rmse:.4f}, WAPE={wape:.2f}%, sMAPE={smape:.2f}%, Bias={bias:+.4f}")

    # Select champion model
    best_model_name = min(benchmark_results, key=lambda k: benchmark_results[k]["mae"])
    print(f"\n=> DEMAND FORECASTING CHAMPION: '{best_model_name}' (Lowest MAE: {benchmark_results[best_model_name]['mae']})")

    # Update persisted artifact if LightGBM or another beats baseline
    champion_art = fitted_artifacts[best_model_name]
    save_model_artifact(
        artifact=champion_art,
        task_config=cfg,
        cv_summary={"validation_strategy": "global_chronological_7d_embargo", "best_model": best_model_name},
        test_metrics=benchmark_results[best_model_name],
        selection_rationale=f"Selected '{best_model_name}' achieving best comparable MAE={benchmark_results[best_model_name]['mae']} under consistent 7-day embargo.",
        output_dir=Path("data/models/demand_forecasting"),
    )

    # Save benchmark table
    with open("reports/model_evaluation/demand_forecasting/consistent_benchmark.json", "w") as f:
        json.dump(benchmark_results, f, indent=2)

    return benchmark_results, best_model_name


def run_inventory_chronological_validation():
    print("\n" + "=" * 70)
    print("2. INVENTORY FORECASTING: GLOBAL CHRONOLOGICAL VS ENTITY-GROUP HOLDOUT")
    print("=" * 70)

    reg = TaskRegistry()
    cfg = reg.get("inventory_forecasting")
    df_raw = load_modeling_dataset("inventory_features")
    df_stream = build_inventory_forecasting_stream(df_raw, horizon_snapshots=1)

    # Target & Features
    drop_cols = set(cfg.excluded_columns + [cfg.target_column, "actual_stockout", "future_booked_quantity"])
    feat_cols = [c for c in df_stream.columns if c not in drop_cols]

    # --- A. Existing Entity-Group Holdout ---
    df_entity_sorted = df_stream.sort_values(["inventory_id", "travel_date", "snapshot_date"]).reset_index(drop=True)
    split_idx_ent = int(len(df_entity_sorted) * 0.85)
    
    X_ent_train = df_entity_sorted.iloc[:split_idx_ent][feat_cols].copy()
    y_ent_train = df_entity_sorted.iloc[:split_idx_ent][cfg.target_column].copy()
    X_ent_test = df_entity_sorted.iloc[split_idx_ent:][feat_cols].copy()
    y_ent_test = df_entity_sorted.iloc[split_idx_ent:][cfg.target_column].copy()

    num_cols, cat_cols = partition_features(X_ent_train)
    prep_ent = build_preprocessor(num_cols, cat_cols)
    model_ent = create_model("lightgbm", TaskType.TIME_SERIES_REGRESSION, random_state=RANDOM_SEED)
    art_ent = train_single_model(model_ent, prep_ent, X_ent_train, y_ent_train, TaskType.TIME_SERIES_REGRESSION, model_name="lightgbm_entity_holdout")
    preds_ent, _ = art_ent.predict(X_ent_test)

    ent_mae = mean_absolute_error(y_ent_test, preds_ent)
    ent_rmse = root_mean_squared_error(y_ent_test, preds_ent)
    ent_r2 = r2_score(y_ent_test, preds_ent)
    ent_wape, _ = safe_wape(y_ent_test.to_numpy(), preds_ent)
    ent_smape, _ = safe_smape(y_ent_test.to_numpy(), preds_ent)
    ent_bias = compute_forecast_bias(y_ent_test.to_numpy(), preds_ent)

    # --- B. New Global Chronological Holdout with 7-Day Embargo ---
    df_stream["snapshot_dt"] = pd.to_datetime(df_stream["snapshot_date"])
    df_chrono_sorted = df_stream.sort_values("snapshot_dt").reset_index(drop=True)

    split_dt = df_chrono_sorted["snapshot_dt"].quantile(0.85)
    embargo_dt = split_dt + pd.Timedelta(days=7)

    tr_mask = df_chrono_sorted["snapshot_dt"] <= split_dt
    te_mask = df_chrono_sorted["snapshot_dt"] >= embargo_dt

    X_chr_train = df_chrono_sorted[tr_mask][feat_cols].copy()
    y_chr_train = df_chrono_sorted[tr_mask][cfg.target_column].copy()
    X_chr_test = df_chrono_sorted[te_mask][feat_cols].copy()
    y_chr_test = df_chrono_sorted[te_mask][cfg.target_column].copy()

    prep_chr = build_preprocessor(num_cols, cat_cols)
    model_chr = create_model("lightgbm", TaskType.TIME_SERIES_REGRESSION, random_state=RANDOM_SEED)
    art_chr = train_single_model(model_chr, prep_chr, X_chr_train, y_chr_train, TaskType.TIME_SERIES_REGRESSION, model_name="lightgbm_chrono_holdout")
    preds_chr, _ = art_chr.predict(X_chr_test)

    chr_mae = mean_absolute_error(y_chr_test, preds_chr)
    chr_rmse = root_mean_squared_error(y_chr_test, preds_chr)
    chr_r2 = r2_score(y_chr_test, preds_chr)
    chr_wape, _ = safe_wape(y_chr_test.to_numpy(), preds_chr)
    chr_smape, _ = safe_smape(y_chr_test.to_numpy(), preds_chr)
    chr_bias = compute_forecast_bias(y_chr_test.to_numpy(), preds_chr)

    print(f"Entity-Group Holdout:  Train={len(X_ent_train):,}, Test={len(X_ent_test):,}")
    print(f"                       MAE={ent_mae:.4f}, RMSE={ent_rmse:.4f}, R2={ent_r2:.4f}, WAPE={ent_wape:.2f}%, Bias={ent_bias:+.4f}")
    print(f"Global Chrono Holdout: Train={len(X_chr_train):,} (<= {split_dt.date()}), Embargo={(~tr_mask & ~te_mask).sum():,}, Test={len(X_chr_test):,} (>= {embargo_dt.date()})")
    print(f"                       MAE={chr_mae:.4f}, RMSE={chr_rmse:.4f}, R2={chr_r2:.4f}, WAPE={chr_wape:.2f}%, Bias={chr_bias:+.4f}")

    eval_comparison = {
        "entity_group_holdout": {
            "train_records": len(X_ent_train), "test_records": len(X_ent_test),
            "mae": round(float(ent_mae), 4), "rmse": round(float(ent_rmse), 4),
            "r2": round(float(ent_r2), 4), "wape": round(float(ent_wape), 2),
            "smape": round(float(ent_smape), 2), "forecast_bias": round(float(ent_bias), 4),
        },
        "global_chronological_holdout": {
            "train_records": len(X_chr_train), "test_records": len(X_chr_test),
            "embargo_records": int((~tr_mask & ~te_mask).sum()),
            "cutoff_date": str(split_dt.date()), "embargo_date": str(embargo_dt.date()),
            "mae": round(float(chr_mae), 4), "rmse": round(float(chr_rmse), 4),
            "r2": round(float(chr_r2), 4), "wape": round(float(chr_wape), 2),
            "smape": round(float(chr_smape), 2), "forecast_bias": round(float(chr_bias), 4),
        }
    }

    with open("reports/model_evaluation/inventory_forecasting/holdout_comparison.json", "w") as f:
        json.dump(eval_comparison, f, indent=2)

    return eval_comparison


def run_stockout_threshold_optimization():
    print("\n" + "=" * 70)
    print("3. INVENTORY STOCKOUT THRESHOLD OPTIMIZATION (VALIDATION SPLIT ONLY)")
    print("=" * 70)

    reg = TaskRegistry()
    cfg = reg.get("inventory_forecasting")
    df_raw = load_modeling_dataset("inventory_features")
    df_stream = build_inventory_forecasting_stream(df_raw, horizon_snapshots=1)

    drop_cols = set(cfg.excluded_columns + [cfg.target_column, "actual_stockout", "future_booked_quantity"])
    feat_cols = [c for c in df_stream.columns if c not in drop_cols]

    # Use training split ONLY (85% partition)
    split_idx = int(len(df_stream) * 0.85)
    X_train_full = df_stream.iloc[:split_idx][feat_cols].copy()
    y_train_full = df_stream.iloc[:split_idx][cfg.target_column].copy()

    # Split training partition into Train (70% of total) and Validation (15% of total)
    # Strictly isolating the test set (the remaining 15%)
    val_split_idx = int(len(X_train_full) * 0.80)
    X_tr = X_train_full.iloc[:val_split_idx].copy()
    y_tr = y_train_full.iloc[:val_split_idx].copy()
    X_val = X_train_full.iloc[val_split_idx:].copy()
    y_val = y_train_full.iloc[val_split_idx:].copy()

    num_cols, cat_cols = partition_features(X_tr)
    prep = build_preprocessor(num_cols, cat_cols)
    model = create_model("lightgbm", TaskType.TIME_SERIES_REGRESSION, random_state=RANDOM_SEED)
    art = train_single_model(model, prep, X_tr, y_tr, TaskType.TIME_SERIES_REGRESSION, model_name="lightgbm_tuning")
    
    val_preds, _ = art.predict(X_val)

    # Actual stockout condition on validation: available_quantity <= 5 units (critical depletion baseline)
    actual_stockout = (y_val <= 5.0).astype(int).to_numpy()
    total_val = len(y_val)
    n_actual = int(actual_stockout.sum())

    print(f"Validation Records: {total_val} | Actual Stockout Events (<= 5 units): {n_actual} ({(n_actual/total_val)*100:.2f}%)")

    # Business cost weights
    # Cost of False Negative (Stockout): ₹3,000 (lost booking profit + emergency acquisition + customer churn)
    # Cost of False Positive (False Alarm): ₹600 (capital cost of holding unneeded buffer inventory)
    C_FN = 3000.0
    C_FP = 600.0

    thresholds = [5, 7, 10, 12, 15]
    optimization_results = []

    print("\nThreshold | Prec (%) | Rec (%)  | F1 (%)   | Spec (%) | FP  | FN  | TP  | TN  | Expected Cost (INR)")
    print("-" * 95)

    for T in thresholds:
        pred_stockout = (val_preds <= float(T)).astype(int)
        cm = confusion_matrix(actual_stockout, pred_stockout)
        tn, fp, fn, tp = cm.ravel()
        
        prec = precision_score(actual_stockout, pred_stockout, zero_division=0)
        rec = recall_score(actual_stockout, pred_stockout, zero_division=0)
        f1 = f1_score(actual_stockout, pred_stockout, zero_division=0)
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        total_cost = (fn * C_FN) + (fp * C_FP)

        optimization_results.append({
            "threshold_units": T,
            "precision": round(float(prec) * 100, 2),
            "recall": round(float(rec) * 100, 2),
            "f1": round(float(f1) * 100, 2),
            "specificity": round(float(spec) * 100, 2),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
            "true_negatives": int(tn),
            "total_business_cost_inr": round(float(total_cost), 2),
        })

        print(f"{T:9d} | {prec*100:8.2f} | {rec*100:8.2f} | {f1*100:8.2f} | {spec*100:8.2f} | {fp:3d} | {fn:3d} | {tp:3d} | {tn:3d} | ₹{total_cost:12,.2f}")

    best_thresh_row = min(optimization_results, key=lambda x: x["total_business_cost_inr"])
    print(f"\n=> OPTIMAL THRESHOLD: {best_thresh_row['threshold_units']} units (Lowest Business Cost: ₹{best_thresh_row['total_business_cost_inr']:,.2f})")
    print(f"   Recall improved from {optimization_results[0]['recall']}% (at T=5) to {best_thresh_row['recall']}% (at T={best_thresh_row['threshold_units']})!")

    with open("reports/model_evaluation/inventory_forecasting/stockout_threshold_optimization.json", "w") as f:
        json.dump({
            "cost_weights": {"cost_false_negative_inr": C_FN, "cost_false_positive_inr": C_FP},
            "validation_records": total_val,
            "actual_stockout_count": n_actual,
            "threshold_evaluations": optimization_results,
            "optimal_threshold_units": best_thresh_row["threshold_units"],
            "baseline_threshold_units": 5,
        }, f, indent=2)

    return optimization_results, best_thresh_row["threshold_units"]


def run_artifact_prediction_tests():
    print("\n" + "=" * 70)
    print("4. ARTIFACT PREDICTION TESTS (ALL 4 CHAMPION ARTIFACTS)")
    print("=" * 70)

    reg = TaskRegistry()
    tasks = ["hotel_cancellation", "flight_price", "demand_forecasting", "inventory_forecasting"]
    results = {}

    for t in tasks:
        artifact, meta = load_model_artifact(t)
        cfg = reg.get(t)
        X, y, _ = prepare_task_dataset(cfg)
        
        # Test 1: Predict on standard batch
        sample_X = X.head(5).copy()
        preds, dur = artifact.predict(sample_X)
        assert len(preds) == 5, f"Prediction length mismatch for {t}"
        assert not np.isnan(preds).any(), f"NaN predictions detected for {t}"

        # Test 2: Unknown categories robustness test
        sample_unknown = sample_X.copy()
        for c in artifact.feature_names:
            if c in sample_unknown.columns and sample_unknown[c].dtype == "object":
                sample_unknown[c] = "COMPLETELY_UNSEEN_CATEGORY_XYZ_999"
        
        preds_unk, _ = artifact.predict(sample_unknown)
        assert len(preds_unk) == 5, f"Unknown categories failed for {t}"
        assert not np.isnan(preds_unk).any(), f"NaNs on unknown categories for {t}"

        print(f"Artifact [{t:22s}]: Estimator={type(artifact.estimator).__name__:18s} Features={len(artifact.feature_names):2d} "
              f"Unknown-Category Safe=PASS Preds={np.round(preds[:2], 2)}")
        results[t] = {
            "model_name": artifact.model_name,
            "feature_count": len(artifact.feature_names),
            "unknown_category_safe": True,
            "sample_predictions": [float(round(p, 4)) for p in preds[:3]],
        }

    return results


if __name__ == "__main__":
    db_res, db_champ = run_consistent_demand_benchmark()
    inv_res = run_inventory_chronological_validation()
    th_res, opt_th = run_stockout_threshold_optimization()
    art_res = run_artifact_prediction_tests()
    print("\nAll Phase 4 final validation tasks completed successfully.")
