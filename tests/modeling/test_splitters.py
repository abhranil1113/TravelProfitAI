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
