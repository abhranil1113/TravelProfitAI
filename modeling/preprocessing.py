"""
TBO InventoryIQ - Fold-Fitted Preprocessing Pipelines (Phase 4)
Builds Scikit-learn ColumnTransformer pipelines fitted strictly on training folds
to eliminate data leakage between train and validation sets.
"""

from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OrdinalEncoder, OneHotEncoder


def build_preprocessor(
    numerical_cols: List[str],
    categorical_cols: List[str],
    scale_numeric: bool = False,
    use_one_hot: bool = False,
) -> ColumnTransformer:
    """
    Constructs an unfitted ColumnTransformer tailored to the estimator type.
    
    For tree-based estimators (Random Forest, XGBoost, LightGBM):
      - scale_numeric=False (trees are scale-invariant)
      - use_one_hot=False (OrdinalEncoder avoids dimensionality explosion on route/airport IDs)
    
    For linear estimators (Logistic Regression, Linear Regression):
      - scale_numeric=True (ensures gradient stability)
      - use_one_hot=False or True depending on cardinality
    """
    transformers = []

    # 1. Numerical Pipeline
    if numerical_cols:
        num_steps = [
            ("imputer", SimpleImputer(strategy="median")),
        ]
        if scale_numeric:
            num_steps.append(("scaler", StandardScaler()))
        num_pipeline = Pipeline(steps=num_steps)
        transformers.append(("num", num_pipeline, numerical_cols))

    # 2. Categorical Pipeline
    if categorical_cols:
        cat_steps = [
            ("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
        ]
        if use_one_hot:
            cat_steps.append((
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ))
        else:
            cat_steps.append((
                "encoder",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    encoded_missing_value=-1,
                ),
            ))
        cat_pipeline = Pipeline(steps=cat_steps)
        transformers.append(("cat", cat_pipeline, categorical_cols))

    return ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=False,
    )


def partition_features(
    X: pd.DataFrame,
    override_cat: Optional[List[str]] = None,
    override_num: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """
    Partitions DataFrame columns into numerical and categorical feature lists.
    """
    if override_cat is not None and override_num is not None:
        cat_cols = [c for c in override_cat if c in X.columns]
        num_cols = [c for c in override_num if c in X.columns]
        return num_cols, cat_cols

    num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in num_cols]
    return num_cols, cat_cols
