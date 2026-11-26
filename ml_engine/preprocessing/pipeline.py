"""
ml_engine/preprocessing/pipeline.py

Preprocessing pipeline integration and missing-value imputation.
Coordinates feature schema alignment and Scikit-Learn transformer pipelines.
"""

import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd

from ml_engine.exceptions import FeatureValidationError, ModelInferenceError
from ml_engine.preprocessing.schema_validator import FeatureSchemaValidator

logger = logging.getLogger(__name__)


class MLPreprocessingPipeline:
    """
    Standardizes inference data preparation.
    Ensures that input dictionaries or DataFrames pass strict feature contracts,
    missing-value imputation controls, and serialization through trained preprocessors.
    """

    def __init__(
        self,
        expected_features: List[str],
        preprocessor: Optional[Any] = None,
        strict_validation: bool = True,
        allow_imputation: bool = False,
    ):
        self.expected_features = expected_features
        self.preprocessor = preprocessor
        self.strict_validation = strict_validation
        self.allow_imputation = allow_imputation

    def transform(self, input_data: Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]) -> Any:
        """
        Converts raw input records into validated, preprocessed feature matrices.
        Raises FeatureValidationError if features are missing and allow_imputation is False.
        """
        # Convert to DataFrame
        if isinstance(input_data, dict):
            df = pd.DataFrame([input_data])
        elif isinstance(input_data, list):
            df = pd.DataFrame(input_data)
        elif isinstance(input_data, pd.DataFrame):
            df = input_data.copy()
        else:
            raise FeatureValidationError(f"Unsupported input data type: {type(input_data).__name__}")

        # Check and align columns
        aligned_df = FeatureSchemaValidator.validate_and_align_dataframe(
            data=df,
            expected_features=self.expected_features,
            strict=self.strict_validation,
            fill_missing=self.allow_imputation,
            default_fill_value=0.0,
        )

        # Apply preprocessor if present
        if self.preprocessor is not None:
            try:
                transformed = self.preprocessor.transform(aligned_df)
                return transformed
            except Exception as exc:
                logger.error("Preprocessing transformer failed: %s", exc)
                raise ModelInferenceError(f"Feature transformation failed: {exc}") from exc

        return aligned_df
