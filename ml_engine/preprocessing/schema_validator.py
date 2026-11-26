"""
ml_engine/preprocessing/schema_validator.py

Feature schema validation, column ordering, and data-quality checks for inference payloads.
Ensures strict adherence to Phase 4 trained model feature contracts.
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
    """

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
    def validate_record_types(
        record: Dict[str, Any],
        numeric_features: Optional[List[str]] = None,
        categorical_features: Optional[List[str]] = None,
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Validates types and detects NaNs or infinite values.
        """
        invalid_types = {}

        if numeric_features:
            for num_feat in numeric_features:
                if num_feat in record and record[num_feat] is not None:
                    val = record[num_feat]
                    try:
                        f_val = float(val)
                        if not np.isfinite(f_val):
                            invalid_types[num_feat] = f"Non-finite numeric value: {val}"
                    except (ValueError, TypeError):
                        invalid_types[num_feat] = f"Cannot convert {type(val).__name__} to float"

        return len(invalid_types) == 0, invalid_types

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
