"""
ml_engine/preprocessing/split_dataset.py

Temporal split and chronological embargo utilities.
Implements the 7-day chronological separation rules established in Stage 4 audits.
"""

from typing import Tuple, Optional
import pandas as pd


class TemporalEmbargoSplitter:
    """
    Splits time-series tabular datasets using global chronological ordering
    and enforces a strict calendar embargo between training and test sets.
    """

    @staticmethod
    def split_with_embargo(
        df: pd.DataFrame,
        date_column: str,
        split_date: str,
        embargo_days: int = 7,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Splits data such that train <= split_date - embargo_days and test >= split_date.
        Prevents lookahead leakage across the embargo buffer.
        """
        dates = pd.to_datetime(df[date_column])
        cutoff_dt = pd.to_datetime(split_date)
        train_cutoff = cutoff_dt - pd.Timedelta(days=embargo_days)

        train_df = df[dates <= train_cutoff].copy()
        test_df = df[dates >= cutoff_dt].copy()

        return train_df, test_df
