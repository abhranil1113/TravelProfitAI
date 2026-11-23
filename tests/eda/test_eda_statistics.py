"""
Tests for Statistical Analysis Module
Verifies outlier detection, correlations, Cramér's V, and hypothesis tests.
"""

import pytest
import pandas as pd
import numpy as np
from eda.statistical_analysis import (
    detect_outliers_iqr,
    detect_outliers_zscore,
    compute_correlation_matrix,
    compute_chi2_and_cramers_v,
    compare_means_difference,
    compare_groups_anova_or_kruskal,
)


def test_detect_outliers_iqr():
    """Verify IQR outlier detection."""
    # Data with obvious outliers: -100 and 1000
    s = pd.Series([10, 12, 11, 13, 12, 14, 11, 10, -100, 1000])
    res = detect_outliers_iqr(s, factor=1.5)
    assert res["outlier_count"] == 2
    assert res["outlier_pct"] == 20.0
    assert res["lower_bound"] < 10
    assert res["upper_bound"] > 14


def test_detect_outliers_zscore():
    """Verify Z-score outlier detection."""
    np.random.seed(42)
    s = pd.Series(np.random.normal(loc=100, scale=5, size=200))
    s.iloc[0] = 500.0  # Massive outlier
    res = detect_outliers_zscore(s, threshold=3.0)
    assert res["outlier_count"] >= 1


def test_compute_correlation_matrix():
    """Verify Pearson correlation matrix calculation."""
    df = pd.DataFrame({
        "x": [1, 2, 3, 4, 5],
        "y": [2, 4, 6, 8, 10],  # Perfectly correlated
        "z": [5, 4, 3, 2, 1],  # Perfectly negatively correlated
    })
    corr = compute_correlation_matrix(df, method="pearson")
    assert corr.loc["x", "y"] == 1.0
    assert corr.loc["x", "z"] == -1.0


def test_compute_chi2_and_cramers_v():
    """Verify categorical association test."""
    df = pd.DataFrame({
        "segment": ["Online", "Online", "Corporate", "Corporate"],
        "canceled": [1, 1, 0, 0],
    })
    res = compute_chi2_and_cramers_v(df, "segment", "canceled", correction=False)
    assert res["feature_1"] == "segment"
    assert res["feature_2"] == "canceled"
    assert res["cramers_v"] == 1.0  # Perfect association
    assert res["association_strength"] == "Strong"


def test_compare_means_difference():
    """Verify independent two-sample t-test and Mann-Whitney U test."""
    g1 = pd.Series([10, 11, 12, 10, 11])
    g2 = pd.Series([50, 52, 51, 49, 53])
    res = compare_means_difference(g1, g2, "Low Group", "High Group")
    assert res["statistically_significant"] is True
    assert res["welch_p_value"] < 0.001
    assert res["mann_whitney_p_value"] < 0.05


def test_compare_groups_anova_or_kruskal():
    """Verify ANOVA and Kruskal-Wallis across multiple groups."""
    g1 = pd.Series([10, 11, 12])
    g2 = pd.Series([20, 21, 22])
    g3 = pd.Series([30, 31, 32])
    res = compare_groups_anova_or_kruskal([g1, g2, g3], ["G1", "G2", "G3"])
    assert res["number_of_groups"] == 3
    assert res["statistically_significant"] is True
