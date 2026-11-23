"""
TBO InventoryIQ - Target & Modeling Dataset Builder (Phase 4)
Handles task-specific dataset preparation, time-series panel aggregation,
and multi-horizon future target construction with zero future lookahead.
"""

from typing import Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
import logging

from modeling.config import TaskType
from modeling.registry.task_registry import TaskConfig
from modeling.data_loader import load_modeling_dataset

logger = logging.getLogger(__name__)


def build_demand_forecasting_panel(
    df_searches: pd.DataFrame,
    horizon_days: int = 7,
) -> pd.DataFrame:
    """
    Transforms individual search event records into a regular time-series panel
    grouped by (destination_id, inventory_type, date) with engineered lags and future target.
    
    Target: future_search_volume_7d (search volume observed 7 days into the future).
    Leakage Protection: Only lags and rolling statistics up to time t are predictors.
    """
    # 1. Synthesize date if needed
    if "search_date" in df_searches.columns:
        date_series = pd.to_datetime(df_searches["search_date"])
    else:
        date_series = pd.to_datetime(
            df_searches["search_year"].astype(str) + "-" +
            df_searches["search_month"].astype(str).str.zfill(2) + "-" +
            df_searches["search_day"].astype(str).str.zfill(2)
        )

    df_work = df_searches.copy()
    df_work["date"] = date_series

    # 2. Aggregate to daily grain per (destination_id, inventory_type)
    daily = df_work.groupby(["destination_id", "inventory_type", "date"]).agg(
        search_volume=("search_id", "count"),
        total_travellers=("travellers_count", "sum") if "travellers_count" in df_work.columns else ("search_id", "count"),
        avg_search_price=("search_price_inr", "mean") if "search_price_inr" in df_work.columns else ("search_id", lambda x: 0.0),
    ).reset_index()

    # 3. Complete date grid per (destination_id, inventory_type)
    panel_records = []
    groups = daily.groupby(["destination_id", "inventory_type"])
    
    for (dest, inv_type), group in groups:
        group = group.sort_values("date").set_index("date")
        full_idx = pd.date_range(group.index.min(), group.index.max(), freq="D")
        reindexed = group.reindex(full_idx)
        reindexed["destination_id"] = dest
        reindexed["inventory_type"] = inv_type
        reindexed["search_volume"] = reindexed["search_volume"].fillna(0)
        reindexed["total_travellers"] = reindexed["total_travellers"].fillna(0)
        reindexed["avg_search_price"] = reindexed["avg_search_price"].ffill().bfill().fillna(0.0)

        # 4. Construct Lag Features (Only past observations t, t-1, t-7, t-14)
        vol = reindexed["search_volume"]
        reindexed["lag_1"] = vol.shift(1).fillna(0)
        reindexed["lag_7"] = vol.shift(7).fillna(0)
        reindexed["lag_14"] = vol.shift(14).fillna(0)
        reindexed["rolling_mean_7"] = vol.shift(1).rolling(7, min_periods=1).mean().fillna(0)
        reindexed["rolling_mean_14"] = vol.shift(1).rolling(14, min_periods=1).mean().fillna(0)
        reindexed["rolling_std_7"] = vol.shift(1).rolling(7, min_periods=1).std().fillna(0)

        # Calendar features
        reindexed["day_of_week"] = reindexed.index.dayofweek
        reindexed["is_weekend"] = (reindexed["day_of_week"] >= 5).astype(int)
        reindexed["month"] = reindexed.index.month
        reindexed["quarter"] = reindexed.index.quarter

        # 5. Target Construction: Future search volume at horizon h (shift -horizon)
        target_col = f"future_search_volume_{horizon_days}d"
        reindexed[target_col] = vol.shift(-horizon_days)

        panel_records.append(reindexed.reset_index().rename(columns={"index": "date"}))

    panel_df = pd.concat(panel_records, ignore_index=True)
    # Drop rows at the end of each series where future target is not yet observed
    panel_clean = panel_df.dropna(subset=[f"future_search_volume_{horizon_days}d"]).reset_index(drop=True)
    panel_clean[f"future_search_volume_{horizon_days}d"] = panel_clean[f"future_search_volume_{horizon_days}d"].astype(float)

    logger.info(
        f"Built demand forecasting panel: {len(panel_clean)} time-series records "
        f"across {len(groups)} series (horizon={horizon_days}d)."
    )
    return panel_clean


def build_inventory_forecasting_stream(
    df_inventory: pd.DataFrame,
    horizon_snapshots: int = 1,
    stockout_threshold: float = 5.0,
) -> pd.DataFrame:
    """
    Sorts sequential observation snapshots per (inventory_id, travel_date) chronologically
    and constructs the future available quantity target at horizon h (h snapshots ahead).
    
    Target: future_available_quantity.
    Auxiliary Label: actual_stockout (future_available_quantity <= stockout_threshold).
    """
    df_work = df_inventory.copy()
    sort_cols = ["inventory_id", "travel_date", "snapshot_date"]
    df_work = df_work.sort_values(sort_cols).reset_index(drop=True)

    # 1. Group by inventory identity and travel date to shift target
    grouped = df_work.groupby(["inventory_id", "travel_date"])
    
    # Future available quantity h snapshots ahead
    df_work["future_available_quantity"] = grouped["available_quantity"].shift(-horizon_snapshots)
    df_work["future_booked_quantity"] = grouped["booked_quantity"].shift(-horizon_snapshots)
    
    # Stockout classification label
    df_work["actual_stockout"] = (
        df_work["future_available_quantity"] <= stockout_threshold
    ).astype(int)

    # 2. Exclude final snapshot where future outcome is unobserved
    valid_df = df_work.dropna(subset=["future_available_quantity"]).reset_index(drop=True)
    
    logger.info(
        f"Built inventory forecasting stream: {len(valid_df)} snapshot transitions "
        f"across {grouped.ngroups} inventory items (stockout_rate={(valid_df['actual_stockout'].mean()*100):.2f}%)."
    )
    return valid_df


def prepare_task_dataset(
    task_config: TaskConfig,
    df_raw: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Centralized dataset preparation function. Loads raw/feature data, applies
    task-specific target construction, strips quarantined leakage columns,
    and returns (X, y, full_processed_df).
    """
    if df_raw is None:
        df_raw = load_modeling_dataset(task_config.dataset_name)

    df = df_raw.copy()

    # 1. Task-Specific Panel / Target Transformations
    if task_config.task_name == "demand_forecasting":
        horizon = task_config.forecast_horizon or 7
        df = build_demand_forecasting_panel(df, horizon_days=horizon)

    elif task_config.task_name == "inventory_forecasting":
        horizon = task_config.forecast_horizon or 1
        threshold = task_config.business_params.get("stockout_threshold_units", 5.0)
        df = build_inventory_forecasting_stream(df, horizon_snapshots=horizon, stockout_threshold=threshold)

    # 2. Verify target column exists
    if task_config.target_column not in df.columns:
        raise KeyError(
            f"Target column '{task_config.target_column}' not found in prepared dataset for task '{task_config.task_name}'. "
            f"Available columns: {list(df.columns)}"
        )

    # 3. Extract Target y
    y = df[task_config.target_column].copy()
    if task_config.task_type == TaskType.BINARY_CLASSIFICATION:
        y = y.astype(int)
    elif task_config.task_type in [TaskType.REGRESSION, TaskType.TIME_SERIES_REGRESSION]:
        y = y.astype(float)

    # 4. Filter Predictor Matrix X
    # Exclude target, specified exclusions, and post-booking leakage
    drop_cols = set(task_config.excluded_columns + [task_config.target_column])
    
    # Also drop non-predictor columns added in target builders
    if "actual_stockout" in df.columns and task_config.target_column != "actual_stockout":
        drop_cols.add("actual_stockout")
    if "future_booked_quantity" in df.columns:
        drop_cols.add("future_booked_quantity")
    if "date" in df.columns:
        drop_cols.add("date")

    feature_cols = [c for c in df.columns if c not in drop_cols]
    if task_config.feature_columns:
        feature_cols = [c for c in task_config.feature_columns if c in df.columns and c not in drop_cols]

    X = df[feature_cols].copy()

    logger.info(
        f"Prepared task '{task_config.task_name}': X={X.shape}, y={y.shape} "
        f"({task_config.task_type.value})"
    )
    return X, y, df
