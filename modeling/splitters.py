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


class ChronologicalSplitter:
    """
    Deterministic chronological cross-validation splitter (expanding window).
    Never shuffles; partitions data strictly preserving chronological ordering.
    """
    def __init__(self, n_splits: int = 5):
        self.n_splits = n_splits

    def split(self, X, y=None, groups=None) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        n_samples = len(X)
        indices = np.arange(n_samples)
        val_size = max(1, int(n_samples / (self.n_splits + 1)))
        for i in range(self.n_splits):
            train_end = val_size * (i + 1)
            val_end = min(train_end + val_size, n_samples)
            if i == self.n_splits - 1:
                val_end = n_samples
            train_idx = indices[:train_end]
            val_idx = indices[train_end:val_end]
            if len(val_idx) > 0 and len(train_idx) > 0:
                yield train_idx, val_idx

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits


class PurgedGroupTimeSeriesSplit:
    """
    Purged & Embargoed Time-Series Cross-Validator for grouped/entity-major panels.
    Partitions across unique global calendar dates with a mandatory purge/embargo gap
    so that training target horizons (e.g. t + 7d) never overlap into validation features.
    """
    def __init__(self, n_splits: int = 5, embargo_gap: int = 7):
        self.n_splits = n_splits
        self.embargo_gap = embargo_gap

    def split(self, X, y=None, groups=None) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        if groups is None:
            raise ValueError(
                "PurgedGroupTimeSeriesSplit requires 'groups' parameter containing calendar dates or timestamps."
            )

        n_samples = len(X)
        indices = np.arange(n_samples)
        
        group_s = pd.Series(groups).reset_index(drop=True)
        dates = pd.to_datetime(group_s)
        unique_dates = pd.Series(sorted(dates.unique()))
        n_dates = len(unique_dates)

        if n_dates < (self.n_splits + 1):
            raise ValueError(f"Insufficient unique dates ({n_dates}) for {self.n_splits} splits with embargo.")

        val_size_days = max(1, int(n_dates / (self.n_splits + 1)))

        for i in range(self.n_splits):
            train_end_idx = val_size_days * (i + 1)
            train_dates = unique_dates.iloc[:train_end_idx]
            last_train_date = train_dates.iloc[-1]

            # Calculate embargo boundary using actual calendar date arithmetic (not row counts)
            embargo_cutoff_date = last_train_date + pd.Timedelta(days=self.embargo_gap)

            # Validation dates must strictly start AFTER embargo_cutoff_date
            remaining_val_dates = unique_dates[unique_dates > embargo_cutoff_date]
            if remaining_val_dates.empty:
                break

            if i == self.n_splits - 1:
                val_dates = remaining_val_dates
            else:
                val_dates = remaining_val_dates.iloc[:val_size_days]

            if val_dates.empty:
                break

            train_mask = dates.isin(train_dates).to_numpy()
            val_mask = dates.isin(val_dates).to_numpy()

            train_idx = indices[train_mask]
            val_idx = indices[val_mask]

            if len(train_idx) > 0 and len(val_idx) > 0:
                yield train_idx, val_idx

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits


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

    elif strategy == ValidationStrategy.CHRONOLOGICAL_SPLIT:
        return ChronologicalSplitter(n_splits=n_splits)

    elif strategy == ValidationStrategy.TIME_SERIES_SPLIT:
        # Time-series splits must NEVER shuffle; uses embargo gap when specified
        if gap > 0:
            return PurgedGroupTimeSeriesSplit(n_splits=n_splits, embargo_gap=gap)
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
