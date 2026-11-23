"""
TBO InventoryIQ - Model Selection Engine (Phase 4)
Applies task-specific decision rules and business constraints to select
the champion model, strictly verifying baseline outperformance.
"""

from typing import Dict, Any, Tuple
import pandas as pd
import logging

from modeling.config import TaskType, METRIC_DIRECTION_IS_HIGHER_BETTER
from modeling.registry.task_registry import TaskConfig

logger = logging.getLogger(__name__)


def select_champion_model(
    task_config: TaskConfig,
    comparison_df: pd.DataFrame,
    baseline_model_names: Tuple[str, ...] = ("dummy", "naive", "linear_regression", "logistic_regression"),
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Selects the winning model for a task based on task-specific criteria.
    Guarantees that a complex algorithm is only chosen if it demonstrably beats the baseline.
    
    Returns:
      (champion_model_name, selection_rationale, champion_summary_dict)
    """
    if comparison_df.empty:
        raise ValueError(f"No model comparison results available for task '{task_config.task_name}'.")

    primary = task_config.primary_metric
    primary_col = f"mean_{primary}"
    is_higher_better = METRIC_DIRECTION_IS_HIGHER_BETTER.get(primary, False)

    # Sort comparison table so best model is at index 0
    sorted_df = comparison_df.sort_values(
        by=primary_col,
        ascending=(not is_higher_better),
    ).reset_index(drop=True)

    top_row = sorted_df.iloc[0]
    top_model = str(top_row["model_name"])
    top_score = float(top_row[primary_col])

    # Find the best baseline score
    baseline_rows = sorted_df[sorted_df["model_name"].isin(baseline_model_names)]
    baseline_score = None
    baseline_name = "N/A"
    if not baseline_rows.empty:
        best_b = baseline_rows.iloc[0]
        baseline_name = str(best_b["model_name"])
        baseline_score = float(best_b[primary_col])

    # Check baseline outperformance
    beats_baseline = True
    if baseline_score is not None and top_model not in baseline_model_names:
        if is_higher_better and top_score <= baseline_score:
            beats_baseline = False
        elif not is_higher_better and top_score >= baseline_score:
            beats_baseline = False

    # Formulate selection rationale
    if not beats_baseline:
        logger.warning(
            f"Advanced model '{top_model}' failed to outperform baseline '{baseline_name}' "
            f"({top_score} vs {baseline_score}). Reverting to baseline."
        )
        champion_model = baseline_name
        rationale = (
            f"Advanced candidate models failed to outperform baseline '{baseline_name}'. "
            f"Baseline preserved to maintain parsimony."
        )
        champion_row = baseline_rows.iloc[0].to_dict()
    else:
        champion_model = top_model
        if baseline_score is not None:
            delta = abs(top_score - baseline_score)
            pct_imp = (delta / abs(baseline_score)) * 100 if baseline_score != 0 else 0.0
            rationale = (
                f"Selected '{top_model}' achieving best mean {primary}={top_score:.4f} "
                f"(improvement of {delta:.4f} / {pct_imp:.2f}% over {baseline_name} {primary}={baseline_score:.4f})."
            )
        else:
            rationale = f"Selected '{top_model}' achieving best mean {primary}={top_score:.4f}."
        champion_row = top_row.to_dict()

    logger.info(f"Task '{task_config.task_name}' Champion: {champion_model}. Rationale: {rationale}")
    return champion_model, rationale, champion_row
