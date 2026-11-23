"""
Comprehensive script to execute all empirical evaluations required for
Phase 4 Final ML Integrity Audit:
1. Route-based GroupKFold vs KFold on flight price prediction
2. Inventory stockout classification metrics (Precision, Recall, F1, CM, FP/FN)
3. Demand forecasting panel verification (grain, counts, zero percentage, horizon, embargo)
4. Persisted champion artifact verification
"""

import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, GroupKFold, train_test_split
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
from modeling.target_builder import prepare_task_dataset
from modeling.preprocessing import build_preprocessor, partition_features
from modeling.model_factory import create_model
from modeling.model_persistence import load_model_artifact
from modeling.metrics import safe_mape, safe_wape, safe_smape


def run_flight_price_audit():
    print("=" * 60)
    print("AUDIT: Flight Price KFold vs GroupKFold (Route-Based)")
    print("=" * 60)
    reg = TaskRegistry()
    cfg = reg.get("flight_price")
    X, y, df_full = prepare_task_dataset(cfg)
    groups = df_full["route"].to_numpy()

    # Sample 30,000 records for consistency with previous CV profiling
    np.random.seed(RANDOM_SEED)
    sample_idx = np.random.choice(len(X), size=30000, replace=False)
    X_s = X.iloc[sample_idx].copy()
    y_s = y.iloc[sample_idx].copy()
    groups_s = groups[sample_idx]

    models_to_test = ["linear_regression", "random_forest", "xgboost", "lightgbm"]

    # 1. KFold (5-fold)
    kfold = KFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    kfold_results = {}
    for m_name in models_to_test:
        maes, rmses, r2s, mapes, wapes = [], [], [], [], []
        for train_i, val_i in kfold.split(X_s, y_s):
            X_tr, y_tr = X_s.iloc[train_i], y_s.iloc[train_i]
            X_va, y_va = X_s.iloc[val_i], y_s.iloc[val_i]
            num_cols, cat_cols = partition_features(X_tr)
            prep = build_preprocessor(num_cols, cat_cols, scale_numeric=(m_name == "linear_regression"))
            X_tr_t = prep.fit_transform(X_tr)
            X_va_t = prep.transform(X_va)
            model = create_model(m_name, TaskType.REGRESSION, random_state=RANDOM_SEED)
            model.fit(X_tr_t, y_tr)
            preds = model.predict(X_va_t)
            maes.append(mean_absolute_error(y_va, preds))
            rmses.append(root_mean_squared_error(y_va, preds))
            r2s.append(r2_score(y_va, preds))
            mapes.append(safe_mape(y_va.to_numpy(), preds)[0])
            wapes.append(safe_wape(y_va.to_numpy(), preds)[0])
        kfold_results[m_name] = {
            "mae": np.mean(maes), "std_mae": np.std(maes),
            "rmse": np.mean(rmses), "r2": np.mean(r2s),
            "mape": np.mean(mapes), "wape": np.mean(wapes),
        }
        print(f"KFold [{m_name}]: MAE = {np.mean(maes):.2f} +/- {np.std(maes):.2f}, R2 = {np.mean(r2s):.4f}")

    # 2. GroupKFold (5-fold by route)
    gfold = GroupKFold(n_splits=5)
    gfold_results = {}
    for m_name in models_to_test:
        maes, rmses, r2s, mapes, wapes = [], [], [], [], []
        for train_i, val_i in gfold.split(X_s, y_s, groups=groups_s):
            X_tr, y_tr = X_s.iloc[train_i], y_s.iloc[train_i]
            X_va, y_va = X_s.iloc[val_i], y_s.iloc[val_i]
            num_cols, cat_cols = partition_features(X_tr)
            prep = build_preprocessor(num_cols, cat_cols, scale_numeric=(m_name == "linear_regression"))
            X_tr_t = prep.fit_transform(X_tr)
            X_va_t = prep.transform(X_va)
            model = create_model(m_name, TaskType.REGRESSION, random_state=RANDOM_SEED)
            model.fit(X_tr_t, y_tr)
            preds = model.predict(X_va_t)
            maes.append(mean_absolute_error(y_va, preds))
            rmses.append(root_mean_squared_error(y_va, preds))
            r2s.append(r2_score(y_va, preds))
            mapes.append(safe_mape(y_va.to_numpy(), preds)[0])
            wapes.append(safe_wape(y_va.to_numpy(), preds)[0])
        gfold_results[m_name] = {
            "mae": np.mean(maes), "std_mae": np.std(maes),
            "rmse": np.mean(rmses), "r2": np.mean(r2s),
            "mape": np.mean(mapes), "wape": np.mean(wapes),
        }
        print(f"GroupKFold [{m_name}]: MAE = {np.mean(maes):.2f} +/- {np.std(maes):.2f}, R2 = {np.mean(r2s):.4f}")

    return {"kfold": kfold_results, "group_kfold": gfold_results}


def run_inventory_stockout_audit():
    print("\n" + "=" * 60)
    print("AUDIT: Inventory Stockout Classification Metrics")
    print("=" * 60)
    reg = TaskRegistry()
    cfg = reg.get("inventory_forecasting")
    X, y, df_full = prepare_task_dataset(cfg)
    threshold = cfg.business_params.get("stockout_threshold_units", 5.0)

    # Load persisted champion model
    artifact, metadata = load_model_artifact("inventory_forecasting")
    print(f"Loaded champion: {artifact.model_name}")

    # Holdout test set (last 15% temporal)
    split_idx = int(len(X) * 0.85)
    X_test = X.iloc[split_idx:].copy()
    y_test = y.iloc[split_idx:].copy()

    preds, infer_sec = artifact.predict(X_test)

    # Actual and Predicted Stockouts
    actual_stockout = (y_test <= threshold).astype(int).to_numpy()
    pred_stockout = (preds <= threshold).astype(int)

    cm = confusion_matrix(actual_stockout, pred_stockout)
    tn, fp, fn, tp = cm.ravel()
    prec = precision_score(actual_stockout, pred_stockout, zero_division=0)
    rec = recall_score(actual_stockout, pred_stockout, zero_division=0)
    f1 = f1_score(actual_stockout, pred_stockout, zero_division=0)

    print(f"Test Records: {len(y_test)}")
    print(f"Actual Stockouts (<= {threshold}): {actual_stockout.sum()} ({(actual_stockout.mean()*100):.2f}%)")
    print(f"Predicted Stockouts: {pred_stockout.sum()} ({(pred_stockout.mean()*100):.2f}%)")
    print(f"Confusion Matrix:\nTN={tn}, FP={fp}\nFN={fn}, TP={tp}")
    print(f"Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}")

    return {
        "test_count": len(y_test),
        "actual_stockout_count": int(actual_stockout.sum()),
        "predicted_stockout_count": int(pred_stockout.sum()),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "precision": float(round(prec, 4)),
        "recall": float(round(rec, 4)),
        "f1": float(round(f1, 4)),
    }


def run_demand_panel_audit():
    print("\n" + "=" * 60)
    print("AUDIT: Demand Forecasting Panel & Embargo")
    print("=" * 60)
    from modeling.data_loader import load_modeling_dataset
    from modeling.target_builder import build_demand_forecasting_panel

    df_raw = load_modeling_dataset("customer_demand_features")
    raw_count = len(df_raw)
    panel_df = build_demand_forecasting_panel(df_raw, horizon_days=7)
    panel_count = len(panel_df)

    zero_demand_count = (panel_df["search_volume"] == 0).sum()
    zero_demand_pct = (zero_demand_count / panel_count) * 100.0

    target_zeros = (panel_df["future_search_volume_7d"] == 0).sum()
    target_zeros_pct = (target_zeros / panel_count) * 100.0

    dest_count = panel_df["destination_id"].nunique()
    inv_types = panel_df["inventory_type"].unique().tolist()
    date_min = panel_df["date"].min()
    date_max = panel_df["date"].max()

    reg = TaskRegistry()
    cfg = reg.get("demand_forecasting")
    embargo_days = cfg.business_params.get("embargo_gap_days", 0)

    print(f"Raw Search Events: {raw_count:,}")
    print(f"Aggregated Daily Panel Rows: {panel_count:,}")
    print(f"Unique Destinations: {dest_count}, Inventory Types: {inv_types}")
    print(f"Date Range: {date_min} to {date_max}")
    print(f"Current Day Zero-Demand Pct: {zero_demand_pct:.2f}% ({zero_demand_count:,} rows)")
    print(f"Target (t+7) Zero-Demand Pct: {target_zeros_pct:.2f}% ({target_zeros:,} rows)")
    print(f"Forecast Horizon: {cfg.forecast_horizon} days")
    print(f"CV Embargo Gap: {embargo_days} days")

    return {
        "raw_event_count": raw_count,
        "panel_row_count": panel_count,
        "unique_destinations": dest_count,
        "inventory_types": inv_types,
        "date_min": str(date_min),
        "date_max": str(date_max),
        "current_zero_demand_pct": float(round(zero_demand_pct, 2)),
        "target_zero_demand_pct": float(round(target_zeros_pct, 2)),
        "forecast_horizon_days": cfg.forecast_horizon,
        "embargo_gap_days": embargo_days,
    }


def run_artifact_verification():
    print("\n" + "=" * 60)
    print("AUDIT: Persisted Champion Model Artifact Verification")
    print("=" * 60)
    tasks = ["hotel_cancellation", "flight_price", "demand_forecasting", "inventory_forecasting"]
    verified = {}
    for t in tasks:
        artifact, meta = load_model_artifact(t)
        est = artifact.estimator
        prep = artifact.preprocessor
        print(f"[{t}] Model: {artifact.model_name}")
        print(f"      Estimator type: {type(est).__name__}")
        print(f"      Preprocessor: {'ColumnTransformer' if prep else 'None'}")
        print(f"      Feature count: {len(artifact.feature_names)}")
        print(f"      Packages: {meta.get('packages', {})}")
        verified[t] = {
            "model_name": artifact.model_name,
            "estimator_type": type(est).__name__,
            "has_preprocessor": prep is not None,
            "feature_count": len(artifact.feature_names),
            "saved_timestamp": meta.get("saved_timestamp"),
        }
    return verified


if __name__ == "__main__":
    fp_res = run_flight_price_audit()
    so_res = run_inventory_stockout_audit()
    dp_res = run_demand_panel_audit()
    av_res = run_artifact_verification()

    audit_data = {
        "flight_price_audit": fp_res,
        "stockout_audit": so_res,
        "demand_panel_audit": dp_res,
        "artifact_verification": av_res,
    }

    with open("reports/model_evaluation/audit_metrics_dump.json", "w") as f:
        json.dump(audit_data, f, indent=2)
    print("\nAudit metrics successfully dumped to reports/model_evaluation/audit_metrics_dump.json")
