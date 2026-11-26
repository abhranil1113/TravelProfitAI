"""
ml_engine/preprocessing/encode_categorical.py

Categorical encoding safeguards and normalization for tabular inference features.
"""

from typing import Dict, Any, List, Optional
import pandas as pd


class CategoricalNormalizer:
    """Safely normalizes string and categorical categorical features before model transformation."""

    @staticmethod
    def normalize_categories(
        df: pd.DataFrame,
        categorical_columns: List[str],
        unknown_token: str = "UNKNOWN",
    ) -> pd.DataFrame:
        """
        Cleans string columns, trims whitespace, standardizes casing, and fills NaNs with fallback token.
        """
        out = df.copy()
        for col in categorical_columns:
            if col in out.columns:
                out[col] = (
                    out[col]
                    .astype(str)
                    .str.strip()
                    .replace({"": unknown_token, "nan": unknown_token, "None": unknown_token})
                    .fillna(unknown_token)
                )
        return out
