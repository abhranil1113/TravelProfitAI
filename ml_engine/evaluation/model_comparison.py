"""
ml_engine/evaluation/model_comparison.py

Model comparison and promotion readiness evaluation utilities.
"""

from typing import Dict, Any, List, Optional
import pandas as pd


class ModelComparator:
    """Compares baseline, champion, and candidate model metrics."""

    @staticmethod
    def compare_metrics(
        champion_metrics: Dict[str, float],
        candidate_metrics: Dict[str, float],
        primary_metric: str = "mae",
        lower_is_better: bool = True,
        min_improvement_pct: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Evaluates whether a candidate model out-performs the champion.
        """
        champ_val = champion_metrics.get(primary_metric)
        cand_val = candidate_metrics.get(primary_metric)

        if champ_val is None or cand_val is None:
            return {
                "is_promotable": False,
                "reason": f"Primary metric '{primary_metric}' missing in one of the models.",
                "champion_value": champ_val,
                "candidate_value": cand_val,
            }

        if lower_is_better:
            diff = champ_val - cand_val
            pct_improvement = (diff / max(1e-9, abs(champ_val))) * 100.0
            is_promotable = pct_improvement >= min_improvement_pct
        else:
            diff = cand_val - champ_val
            pct_improvement = (diff / max(1e-9, abs(champ_val))) * 100.0
            is_promotable = pct_improvement >= min_improvement_pct

        return {
            "is_promotable": is_promotable,
            "primary_metric": primary_metric,
            "champion_value": champ_val,
            "candidate_value": cand_val,
            "absolute_difference": round(diff, 4),
            "percentage_improvement": round(pct_improvement, 2),
            "recommendation": "PROMOTE" if is_promotable else "RETAIN_CHAMPION",
        }
