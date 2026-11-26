"""
ml_engine/evaluation/backtesting.py

Rolling-origin and expanding-window chronological backtesting framework.
"""

from typing import List, Dict, Any, Tuple, Optional, Callable
import pandas as pd
import numpy as np


class ChronologicalBacktestWindow:
    """Represents a single backtesting fold with strict calendar embargo."""

    def __init__(self, fold_id: int, cutoff_date: str, train_indices: np.ndarray, test_indices: np.ndarray):
        self.fold_id = fold_id
        self.cutoff_date = cutoff_date
        self.train_indices = train_indices
        self.test_indices = test_indices


class BacktestingEngine:
    """Generates rolling-origin evaluation folds for time-series panel models."""

    @staticmethod
    def generate_expanding_windows(
        df: pd.DataFrame,
        date_column: str,
        initial_train_days: int = 60,
        step_days: int = 7,
        test_horizon_days: int = 7,
        embargo_days: int = 7,
    ) -> List[ChronologicalBacktestWindow]:
        """
        Creates expanding chronological training windows with calendar embargo buffer.
        """
        dates = pd.to_datetime(df[date_column]).sort_values()
        min_date = dates.min()
        max_date = dates.max()

        start_cutoff = min_date + pd.Timedelta(days=initial_train_days)
        current_cutoff = start_cutoff
        windows: List[ChronologicalBacktestWindow] = []
        fold_id = 1

        all_dates = pd.to_datetime(df[date_column])

        while current_cutoff + pd.Timedelta(days=test_horizon_days) <= max_date:
            train_end = current_cutoff - pd.Timedelta(days=embargo_days)
            test_start = current_cutoff
            test_end = current_cutoff + pd.Timedelta(days=test_horizon_days)

            train_idx = np.where(all_dates <= train_end)[0]
            test_idx = np.where((all_dates >= test_start) & (all_dates < test_end))[0]

            if len(train_idx) > 0 and len(test_idx) > 0:
                windows.append(
                    ChronologicalBacktestWindow(
                        fold_id=fold_id,
                        cutoff_date=str(current_cutoff.date()),
                        train_indices=train_idx,
                        test_indices=test_idx,
                    )
                )
                fold_id += 1

            current_cutoff += pd.Timedelta(days=step_days)

        return windows
