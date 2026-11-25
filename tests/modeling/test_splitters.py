"""
Tests for Data Splitters.
Verifies StratifiedKFold, KFold, TimeSeriesSplit, and domain scenario horizon splitters.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.config import ValidationStrategy
from modeling.splitters import (
    get_cross_validation_splitter,
    split_flight_price_horizons,
)


def test_get_stratified_kfold():
    splitter = get_cross_validation_splitter(
        strategy=ValidationStrategy.STRATIFIED_KFOLD,
        n_splits=3,
        random_state=42,
    )
    X = np.ones((60, 2))
    y = np.array([0] * 40 + [1] * 20)

    splits = list(splitter.split(X, y))
    assert len(splits) == 3

    for train_idx, val_idx in splits:
        val_y = y[val_idx]
        ratio = (val_y == 1).sum() / len(val_y)
        assert np.isclose(ratio, 20 / 60, atol=0.05)


def test_get_kfold():
    splitter = get_cross_validation_splitter(
        strategy=ValidationStrategy.KFOLD,
        n_splits=4,
        random_state=42,
    )
    X = np.ones((40, 2))
    splits = list(splitter.split(X))
    assert len(splits) == 4
    for train_idx, val_idx in splits:
        assert len(val_idx) == 10


def test_get_time_series_split():
    splitter = get_cross_validation_splitter(
        strategy=ValidationStrategy.TIME_SERIES_SPLIT,
        n_splits=3,
        gap=1,
    )
    X = np.arange(50).reshape(-1, 1)
    splits = list(splitter.split(X))
    assert len(splits) == 3

    for train_idx, test_idx in splits:
        assert train_idx.max() < test_idx.min()


def test_split_flight_price_horizons():
    df = pd.DataFrame({
        "days_left": [30, 20, 12, 10, 5, 1],
        "price": [3000, 3500, 4200, 4600, 7000, 9500],
    })
    subsets = split_flight_price_horizons(df)
    assert "advance_booking" in subsets
    assert "intermediate" in subsets
    assert "immediate_departure" in subsets
    assert len(subsets["advance_booking"]) == 2  # 30, 20
    assert len(subsets["intermediate"]) == 2     # 12, 10
    assert len(subsets["immediate_departure"]) == 2 # 5, 1


def test_chronological_splitter():
    from modeling.splitters import ChronologicalSplitter
    splitter = ChronologicalSplitter(n_splits=3)
    X = np.arange(100).reshape(-1, 1)
    splits = list(splitter.split(X))
    assert len(splits) == 3
    for train_idx, val_idx in splits:
        assert train_idx.max() < val_idx.min()
        assert len(train_idx) > 0 and len(val_idx) > 0


def test_purged_group_time_series_split():
    from modeling.splitters import PurgedGroupTimeSeriesSplit
    splitter = PurgedGroupTimeSeriesSplit(n_splits=3, embargo_gap=2)
    # 20 consecutive days across 2 entities
    dates = [f"2026-01-{i:02d}" for i in range(1, 21)] * 2
    X = pd.DataFrame({"feat": np.arange(len(dates))})
    splits = list(splitter.split(X, groups=dates))
    assert len(splits) > 0
    for train_idx, val_idx in splits:
        train_dates = set([dates[i] for i in train_idx])
        val_dates = set([dates[i] for i in val_idx])
        # Ensure zero overlap
        assert len(train_dates.intersection(val_dates)) == 0
        # Ensure train max date + embargo_gap <= val min date
        max_train = max(train_dates)
        min_val = min(val_dates)
        assert max_train < min_val


def test_purged_group_time_series_split_requires_groups():
    from modeling.splitters import PurgedGroupTimeSeriesSplit
    splitter = PurgedGroupTimeSeriesSplit(n_splits=3, embargo_gap=2)
    X = pd.DataFrame({"feat": np.arange(20)})
    with pytest.raises(ValueError, match="requires 'groups' containing calendar dates"):
        list(splitter.split(X, groups=None))


def test_purged_group_time_series_split_calendar_embargo_arithmetic():
    from modeling.splitters import PurgedGroupTimeSeriesSplit
    embargo_days = 7
    splitter = PurgedGroupTimeSeriesSplit(n_splits=3, embargo_gap=embargo_days)
    # Generate daily dates for 30 days
    date_range = pd.date_range("2026-01-01", periods=30, freq="D")
    dates = pd.Series(date_range)
    X = pd.DataFrame({"feat": np.arange(30)})
    splits = list(splitter.split(X, groups=dates))
    assert len(splits) > 0
    for train_idx, val_idx in splits:
        train_d = pd.to_datetime(dates.iloc[train_idx])
        val_d = pd.to_datetime(dates.iloc[val_idx])
        last_train = train_d.max()
        first_val = val_d.min()
        # Exact calendar date arithmetic: first validation date must strictly exceed last_train + embargo_days
        assert first_val > last_train + pd.Timedelta(days=embargo_days)

