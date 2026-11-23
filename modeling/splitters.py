"""
TBO InventoryIQ - Cross-Validation & Scenario Splitters (Phase 4)
Provides deterministic splitting strategies: StratifiedKFold, KFold,
TimeSeriesSplit with embargo gaps, and domain scenario horizon evaluators.
"""

from typing import Generator, Tuple, Dict, Any, List, Optional
import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedKFold, KFold, TimeSeriesSplit

from modeling.config import ValidationStrategy, RANDOM_SEED


def get_cross_validation_splitter(
    strategy: ValidationStrategy,
    n_splits: int = 5,
    shuffle: bool = True,
    random_state: int = RANDOM_SEED,
    gap: int = 0,
):
    """
    Constructs the appropriate cross-validation splitting generator.
    """
    if strategy == ValidationStrategy.STRATIFIED_KFOLD:
        return StratifiedKFold(n_splits=n_splits, shuffle=shuffle, random_state=random_state)

    elif strategy == ValidationStrategy.KFOLD:
        return KFold(n_splits=n_splits, shuffle=shuffle, random_state=random_state)

    elif strategy == ValidationStrategy.TIME_SERIES_SPLIT:
        # Time-series splits must NEVER shuffle
        return TimeSeriesSplit(n_splits=n_splits, gap=gap)

    raise ValueError(f"Unsupported validation strategy: {strategy}")


def split_flight_price_horizons(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Partitions flight price records into Scenario-Based Horizon subsets:
    - advance_booking: days_left >= 15
    - intermediate: 8 <= days_left <= 14
    - immediate_departure: days_left <= 7
    """
    if "days_left" not in df.columns:
        raise KeyError("Column 'days_left' required for flight price horizon evaluation.")

    return {
        "advance_booking": df[df["days_left"] >= 15].copy(),
        "intermediate": df[(df["days_left"] >= 8) & (df["days_left"] <= 14)].copy(),
        "immediate_departure": df[df["days_left"] <= 7].copy(),
    }


def split_hotel_booking_date_stream(
    df: pd.DataFrame,
    train_end: str = "2016-11-06",
    val_end: str = "2017-02-03",
) -> Dict[str, pd.DataFrame]:
    """
    Partitions hotel cancellation records by reconstructed transaction booking_date
    into a realistic chronological arrival stream (70% train, 15% val, 15% test).
    """
    if "booking_date" not in df.columns:
        raise KeyError("Column 'booking_date' required for chronological booking stream evaluation.")

    train_mask = df["booking_date"] <= train_end
    val_mask = (df["booking_date"] > train_end) & (df["booking_date"] <= val_end)
    test_mask = df["booking_date"] > val_end

    return {
        "train": df[train_mask].copy(),
        "validation": df[val_mask].copy(),
        "test": df[test_mask].copy(),
    }
