"""
Tests for Preprocessing Pipelines (build_preprocessor & partition_features).
Verifies imputation, scaling, ordinal encoding, and feature partitioning.
"""

import pytest
import numpy as np
import pandas as pd
from modeling.preprocessing import build_preprocessor, partition_features


def test_partition_features():
    df = pd.DataFrame({
        "num_a": [1.0, 2.0],
        "num_b": [10, 20],
        "cat_a": ["A", "B"],
        "cat_b": ["X", "Y"],
    })
    num_cols, cat_cols = partition_features(df)
    assert sorted(num_cols) == ["num_a", "num_b"]
    assert sorted(cat_cols) == ["cat_a", "cat_b"]


def test_build_preprocessor_transforms():
    num_cols = ["age", "fare"]
    cat_cols = ["cabin_class", "origin"]

    preprocessor = build_preprocessor(
        numerical_cols=num_cols,
        categorical_cols=cat_cols,
        scale_numeric=True,
    )

    train_df = pd.DataFrame({
        "age": [25.0, np.nan, 45.0, 30.0],
        "fare": [100.0, 200.0, np.nan, 150.0],
        "cabin_class": ["Economy", "Business", "Economy", "First"],
        "origin": ["DEL", "BOM", "BLR", "DEL"],
    })

    X_train_trans = preprocessor.fit_transform(train_df)
    assert X_train_trans.shape == (4, 4)
    # Check no NaNs remain after imputation
    assert not np.isnan(X_train_trans).any()


def test_preprocessor_unseen_categories():
    preprocessor = build_preprocessor(
        numerical_cols=[],
        categorical_cols=["city"],
    )

    train_df = pd.DataFrame({"city": ["DEL", "BOM", "BLR"]})
    test_df = pd.DataFrame({"city": ["HYD", "DEL", "UNKNOWN"]})

    preprocessor.fit(train_df)
    test_trans = preprocessor.transform(test_df)
    assert test_trans.shape == (3, 1)
    # Unseen categories encoded as -1 (unknown_value=-1)
    assert test_trans[0, 0] == -1.0
    assert test_trans[1, 0] != -1.0
