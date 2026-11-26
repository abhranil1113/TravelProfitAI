"""
ml_engine/preprocessing/schema_validator.py

Feature schema validation, column ordering, and data-quality checks for inference payloads.
Ensures strict adherence to Phase 4 trained model feature contracts without silent data corruption.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

from ml_engine.exceptions import FeatureValidationError, SchemaMismatchError

logger = logging.getLogger(__name__)


class FeatureSchemaValidator:
    """
    Validates input feature dictionaries or DataFrames against model metadata feature contracts.
    Rejects missing features, invalid types, NaNs, and infinite values when imputation is disabled.
    """

    @staticmethod
    def validate_features(
        features: Dict[str, Any],
        expected_features: List[str],
        numeric_features: Optional[List[str]] = None,
        categorical_features: Optional[List[str]] = None,
        strict: bool = True,
        allow_imputation: bool = False,
    ) -> Tuple[bool, List[str], Dict[str, str], Dict[str, Any]]:
        """
        Validates completeness, numeric finiteness, and categorical types for an observation.
        Returns:
            (is_valid, missing_features, invalid_types, invalid_values)
        """
        missing: List[str] = []
        invalid_types: Dict[str, str] = {}
        invalid_values: Dict[str, Any] = {}

        # 1. Check feature presence
        for feat in expected_features:
            if feat not in features or features[feat] is None:
                missing.append(feat)

        if missing and (strict and not allow_imputation):
            return False, missing, invalid_types, invalid_values

        # 2. Validate numeric features (must be finite, not NaN/Inf)
        num_cols = set(numeric_features) if numeric_features is not None else set()
        for k, v in features.items():
            if v is None:
                continue
            if k in num_cols or isinstance(v, (int, float, np.number)):
                try:
                    f_val = float(v)
                    if not np.isfinite(f_val):
                        invalid_values[k] = f"Non-finite numeric value (NaN or Inf): {v}"
                except (ValueError, TypeError):
                    invalid_types[k] = f"Cannot parse numeric value from type {type(v).__name__}: {v}"

        # 3. Validate categorical features
        cat_cols = set(categorical_features) if categorical_features is not None else set()
        for cat_feat in cat_cols:
            if cat_feat in features and features[cat_feat] is not None:
                val = features[cat_feat]
                if not isinstance(val, (str, int, float, bool)):
                    invalid_types[cat_feat] = f"Unexpected categorical type {type(val).__name__}: {val}"
                elif isinstance(val, str) and not val.strip():
                    invalid_values[cat_feat] = "Empty string value for categorical feature"

        is_valid = (len(missing) == 0 if not allow_imputation else True) and (len(invalid_types) == 0) and (len(invalid_values) == 0)
        return is_valid, missing, invalid_types, invalid_values

    @staticmethod
    def validate_and_align_dataframe(
        data: pd.DataFrame,
        expected_features: List[str],
        strict: bool = True,
        fill_missing: bool = False,
        default_fill_value: Any = 0.0,
    ) -> pd.DataFrame:
        """
        Validates column presence and aligns columns to the exact expected feature contract.
        Raises SchemaMismatchError if required features are absent and fill_missing is False.
        """
        missing = [f for f in expected_features if f not in data.columns]
        if missing:
            if strict and not fill_missing:
                raise SchemaMismatchError(
                    f"Input data is missing required features: {missing}",
                    missing_features=missing
                )
            for f in missing:
                data[f] = default_fill_value

        # Return strictly aligned columns in exact expected contract order
        return data[expected_features].copy()

    @staticmethod
    def assess_data_quality(record: Dict[str, Any], expected_features: List[str]) -> Dict[str, Any]:
        """
        Evaluates data quality metrics for an input observation.
        """
        total = len(expected_features)
        present = sum(1 for f in expected_features if f in record and record[f] is not None)
        missing_count = total - present
        completeness_ratio = float(present / total) if total > 0 else 1.0

        return {
            "total_expected_features": total,
            "present_features": present,
            "missing_features_count": missing_count,
            "completeness_ratio": round(completeness_ratio, 4),
            "is_complete": missing_count == 0,
        }
