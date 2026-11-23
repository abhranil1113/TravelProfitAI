"""
TBO InventoryIQ - Statistical Analysis & Hypothesis Testing (Phase 2)
Implements outlier detection, Pearson/Spearman correlation matrices,
Cramér's V association, and parametric/non-parametric hypothesis tests.
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats


def detect_outliers_iqr(series: pd.Series, factor: float = 1.5) -> Dict[str, Any]:
    """
    Detects outliers using the Interquartile Range (Tukey's Fences) method.
    """
    clean_s = series.dropna()
    n = len(clean_s)
    if n == 0:
        return {"total_records": 0, "outlier_count": 0, "outlier_pct": 0.0}

    q25 = float(clean_s.quantile(0.25))
    q75 = float(clean_s.quantile(0.75))
    iqr = q75 - q25
    lower_bound = q25 - factor * iqr
    upper_bound = q75 + factor * iqr

    outliers = clean_s[(clean_s < lower_bound) | (clean_s > upper_bound)]
    outlier_count = len(outliers)

    return {
        "total_records": n,
        "q25": round(q25, 4),
        "q75": round(q75, 4),
        "iqr": round(iqr, 4),
        "lower_bound": round(lower_bound, 4),
        "upper_bound": round(upper_bound, 4),
        "outlier_count": outlier_count,
        "outlier_pct": round((outlier_count / n) * 100, 2),
    }


def detect_outliers_zscore(series: pd.Series, threshold: float = 3.0) -> Dict[str, Any]:
    """
    Detects outliers using standard Z-score deviations from the mean.
    """
    clean_s = series.dropna()
    n = len(clean_s)
    if n < 3 or clean_s.std() == 0:
        return {"total_records": n, "outlier_count": 0, "outlier_pct": 0.0}

    mean = float(clean_s.mean())
    std = float(clean_s.std())
    z_scores = np.abs((clean_s - mean) / std)
    outliers = clean_s[z_scores > threshold]
    outlier_count = len(outliers)

    return {
        "total_records": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "threshold": threshold,
        "outlier_count": outlier_count,
        "outlier_pct": round((outlier_count / n) * 100, 2),
    }


def compute_correlation_matrix(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    method: str = "pearson",
) -> pd.DataFrame:
    """
    Computes Pearson or Spearman correlation matrix for numerical features.
    """
    if columns is not None:
        target_df = df[columns].select_dtypes(include=[np.number])
    else:
        target_df = df.select_dtypes(include=[np.number])

    if target_df.empty:
        return pd.DataFrame()

    corr = target_df.corr(method=method)
    return corr.round(4)


def compute_chi2_and_cramers_v(
    df: pd.DataFrame,
    col1: str,
    col2: str,
    correction: bool = False,
) -> Dict[str, Any]:
    """
    Computes Chi-Square test of independence and Cramér's V measure of nominal association.
    """
    sub_df = df[[col1, col2]].dropna()
    if len(sub_df) == 0:
        return {"status": "empty_series", "cramers_v": 0.0}

    contingency_table = pd.crosstab(sub_df[col1], sub_df[col2])
    if contingency_table.size <= 1:
        return {"status": "insufficient_categories", "cramers_v": 0.0}

    chi2, p_val, dof, _ = stats.chi2_contingency(contingency_table, correction=correction)
    n = len(sub_df)
    min_dim = min(contingency_table.shape) - 1

    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else 0.0

    return {
        "feature_1": col1,
        "feature_2": col2,
        "chi2_statistic": round(float(chi2), 4),
        "p_value": float(p_val),
        "degrees_of_freedom": int(dof),
        "cramers_v": round(float(cramers_v), 4),
        "association_strength": (
            "Negligible" if cramers_v < 0.1 else
            "Weak" if cramers_v < 0.2 else
            "Moderate" if cramers_v < 0.4 else
            "Strong"
        ),
    }


def compare_means_difference(
    group1: pd.Series,
    group2: pd.Series,
    label1: str = "Group 1",
    label2: str = "Group 2",
) -> Dict[str, Any]:
    """
    Executes independent two-sample Student's t-test and non-parametric Mann-Whitney U test.
    """
    g1 = group1.dropna()
    g2 = group2.dropna()

    if len(g1) < 2 or len(g2) < 2:
        return {"status": "insufficient_sample_size"}

    # Welch's t-test (equal_var=False)
    t_stat, t_pval = stats.ttest_ind(g1, g2, equal_var=False)
    # Mann-Whitney U
    u_stat, u_pval = stats.mannwhitneyu(g1, g2, alternative="two-sided")

    return {
        "group_1_name": label1,
        "group_1_mean": round(float(g1.mean()), 4),
        "group_1_median": round(float(g1.median()), 4),
        "group_1_size": len(g1),
        "group_2_name": label2,
        "group_2_mean": round(float(g2.mean()), 4),
        "group_2_median": round(float(g2.median()), 4),
        "group_2_size": len(g2),
        "welch_t_stat": round(float(t_stat), 4),
        "welch_p_value": float(t_pval),
        "mann_whitney_u_stat": round(float(u_stat), 4),
        "mann_whitney_p_value": float(u_pval),
        "statistically_significant": bool(t_pval < 0.05),
    }


def compare_groups_anova_or_kruskal(
    groups: List[pd.Series],
    labels: List[str],
) -> Dict[str, Any]:
    """
    Executes One-Way ANOVA and non-parametric Kruskal-Wallis H-test across multiple groups.
    """
    valid_groups = [g.dropna() for g in groups if len(g.dropna()) >= 2]
    if len(valid_groups) < 2:
        return {"status": "insufficient_groups"}

    f_stat, f_pval = stats.f_oneway(*valid_groups)
    h_stat, h_pval = stats.kruskal(*valid_groups)

    return {
        "number_of_groups": len(valid_groups),
        "group_labels": labels[:len(valid_groups)],
        "anova_f_stat": round(float(f_stat), 4),
        "anova_p_value": float(f_pval),
        "kruskal_h_stat": round(float(h_stat), 4),
        "kruskal_p_value": float(h_pval),
        "statistically_significant": bool(f_pval < 0.05),
    }
