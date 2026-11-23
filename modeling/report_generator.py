"""
TBO InventoryIQ - Report Generation Engine (Phase 4)
Generates markdown and JSON performance summaries, model comparison matrices,
and the final Phase 4 execution audit report.
"""

from typing import Dict, Any, List
from pathlib import Path
import json
import pandas as pd

from modeling.config import REPORTS_DIR


def format_markdown_table(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Renders a pandas DataFrame as a GitHub-flavored Markdown table without external dependencies."""
    if df.empty:
        return "*No records.*"
    truncated = df.head(max_rows)
    headers = [str(c) for c in truncated.columns]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_lines = []
    for _, row in truncated.iterrows():
        vals = [str(row[c]).replace("|", "/") for c in truncated.columns]
        data_lines.append("| " + " | ".join(vals) + " |")
    return "\n".join([header_line, sep_line] + data_lines)


def export_task_reports(
    task_name: str,
    comparison_df: pd.DataFrame,
    fold_results_df: pd.DataFrame,
    final_evaluation: Dict[str, Any],
) -> Dict[str, Path]:
    """
    Exports CSV and JSON reports for a specific prediction task.
    """
    task_dir = REPORTS_DIR / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    comp_csv = task_dir / "model_comparison.csv"
    cv_csv = task_dir / "cv_results.csv"
    eval_json = task_dir / "final_evaluation.json"

    comparison_df.to_csv(comp_csv, index=False)
    fold_results_df.to_csv(cv_csv, index=False)
    with open(eval_json, "w", encoding="utf-8") as f:
        json.dump(final_evaluation, f, indent=2)

    return {
        "model_comparison_csv": comp_csv,
        "cv_results_csv": cv_csv,
        "final_evaluation_json": eval_json,
    }


def generate_model_comparison_summary(
    task_summaries: Dict[str, Dict[str, Any]],
) -> Path:
    """
    Compiles cross-task model comparison summary markdown document.
    """
    summary_path = REPORTS_DIR / "model_comparison_summary.md"

    md = [
        "# TBO InventoryIQ — Phase 4 Model Comparison & Benchmark Summary",
        "**AI-Powered Travel Inventory & Profit Optimization Platform**  ",
        "**Date:** November 23, 2026  ",
        "**Status:** COMPLETE & BENCHMARKED  \n",
        "---",
        "## Executive Summary",
        "This report consolidates cross-validation benchmarks and offline holdout evaluations "
        "across the four eligible travel prediction tasks. Each task was evaluated across "
        "heuristic baselines, linear/logistic models, Random Forest, XGBoost, and LightGBM.\n",
    ]

    for task_name, summary in task_summaries.items():
        comp_df = summary.get("comparison_df", pd.DataFrame())
        champ = summary.get("champion_model", "N/A")
        rationale = summary.get("rationale", "")

        md.append(f"### {task_name.replace('_', ' ').title()}")
        md.append(f"**Selected Champion Model:** `{champ}`  ")
        md.append(f"**Selection Rationale:** {rationale}  \n")

        if not comp_df.empty:
            md.append("#### Cross-Validation Benchmark Table")
            display_cols = [c for c in comp_df.columns if c not in ["task_name", "total_duration_sec"]]
            md.append(format_markdown_table(comp_df[display_cols]))
            md.append("\n")

    content = "\n".join(md)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(content)

    return summary_path
