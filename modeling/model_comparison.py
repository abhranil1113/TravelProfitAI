"""
TBO InventoryIQ - Model Comparison Engine (Phase 4)
Aggregates cross-validation results across baselines and candidate models,
producing comparative metric tables and ranking summaries.
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np

from modeling.config import METRIC_DIRECTION_IS_HIGHER_BETTER
from modeling.registry.task_registry import TaskConfig
from modeling.cross_validator import CrossValidationResult


class ModelComparisonEngine:
    """
    Compares candidate models for a task across fold metrics, mean performance,
    variance, and training/inference latency.
    """
    def __init__(self, task_config: TaskConfig):
        self.task_config = task_config
        self.results: Dict[str, CrossValidationResult] = {}

    def add_result(self, cv_result: CrossValidationResult) -> None:
        """Adds a model's CV result to the comparison set."""
        self.results[cv_result.model_name] = cv_result

    def build_comparison_dataframe(self) -> pd.DataFrame:
        """
        Builds a summary DataFrame comparing all trained candidate models.
        Sorted by the task's primary metric in the appropriate direction.
        """
        if not self.results:
            return pd.DataFrame()

        rows = []
        for name, res in self.results.items():
            rows.append(res.to_dict())

        df_comp = pd.DataFrame(rows)
        primary_col = f"mean_{self.task_config.primary_metric}"

        if primary_col in df_comp.columns:
            is_higher = METRIC_DIRECTION_IS_HIGHER_BETTER.get(self.task_config.primary_metric, False)
            df_comp = df_comp.sort_values(by=primary_col, ascending=(not is_higher)).reset_index(drop=True)

        return df_comp

    def build_fold_results_dataframe(self) -> pd.DataFrame:
        """
        Builds a granular DataFrame containing individual fold results across all models.
        """
        fold_rows = []
        for name, res in self.results.items():
            for fold_dict in res.fold_metrics:
                row = {
                    "task_name": self.task_config.task_name,
                    "model_name": name,
                    **fold_dict,
                }
                fold_rows.append(row)

        return pd.DataFrame(fold_rows)
