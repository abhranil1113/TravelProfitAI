"""
TBO InventoryIQ - Notebook Generator (Phase 4)
Generates the four standard Jupyter Notebooks for Phase 4 modeling tasks.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = BASE_DIR / "notebooks"
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)


def create_notebook(nb_path: Path, title: str, task_name: str, description: str, extra_cells_code: list):
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                f"# TBO InventoryIQ — {title}\n",
                f"**Phase 4: Machine Learning Development & Offline Evaluation**\n\n",
                f"{description}\n\n",
                "---\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import sys\n",
                "from pathlib import Path\n",
                "BASE_DIR = Path('..').resolve()\n",
                "if str(BASE_DIR) not in sys.path:\n",
                "    sys.path.insert(0, str(BASE_DIR))\n\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "import matplotlib.pyplot as plt\n",
                "import seaborn as sns\n\n",
                "from modeling.registry.task_registry import TaskRegistry\n",
                "from modeling.registry.dataset_registry import DatasetRegistry\n",
                "from modeling.target_builder import prepare_task_dataset\n",
                "from modeling.pipeline import run_task_pipeline\n",
                "from modeling.model_persistence import load_model_artifact\n\n",
                "print('Environment and modeling modules loaded successfully.')\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. Task Configuration & Dataset Inspection\n",
                f"Retrieve registered task `{task_name}` from `TaskRegistry` and load modeling dataset.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                f"registry = TaskRegistry()\n",
                f"task_cfg = registry.get('{task_name}')\n",
                "print(f'Task: {task_cfg.task_name} | Type: {task_cfg.task_type.value} | Target: {task_cfg.target_column}')\n",
                "print(f'Validation Strategy: {task_cfg.validation_strategy.value} (splits={task_cfg.n_splits})')\n",
                "print(f'Excluded Features ({len(task_cfg.excluded_columns)}): {task_cfg.excluded_columns}')\n\n",
                "X, y, df_full = prepare_task_dataset(task_cfg)\n",
                "print(f'Prepared dataset: X shape = {X.shape}, y shape = {y.shape}')\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. Execute Modeling Pipeline\n",
                "Runs fold-fitted preprocessing, baselines, Random Forest, XGBoost, LightGBM, and hyperparameter tuning.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                f"# Execute pipeline using reusable framework module\n",
                f"pipeline_results = run_task_pipeline('{task_name}', n_iter_tuning=2)\n",
                "champion_model = pipeline_results['champion_model']\n",
                "print(f'Champion Model: {champion_model}')\n",
                "print(f'Selection Rationale: {pipeline_results[\"rationale\"]}')\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. Model Benchmark Comparison\n",
                "Comparison of candidate algorithms across cross-validation folds.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "comp_df = pipeline_results['comparison_df']\n",
                "display_cols = [c for c in comp_df.columns if c not in ['task_name', 'total_duration_sec']]\n",
                "print(comp_df[display_cols].to_string(index=False))\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4. Final Offline Test Evaluation & Diagnostics\n",
                "Evaluates the selected champion model on the untouched test holdout set.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "test_eval = pipeline_results['test_evaluation']\n",
                "print('Test Holdout Metrics:')\n",
                "for k, v in test_eval['metrics'].items():\n",
                "    print(f'  {k:20s}: {v}')\n\n",
                f"artifact, meta = load_model_artifact('{task_name}')\n",
                "print(f'Successfully reloaded persisted champion artifact: {artifact.model_name}')\n",
            ],
        },
    ]

    for c in extra_cells_code:
        cells.append(c)

    nb = {
        "cells": cells,
        "metadata": {
            "language_info": {"name": "python", "version": "3.10.0"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    print(f"Created notebook: {nb_path}")


def main():
    # 1. Hotel Cancellation
    create_notebook(
        NOTEBOOKS_DIR / "10_hotel_cancellation_modeling.ipynb",
        "Hotel Cancellation Prediction",
        "hotel_cancellation",
        "Predicts hotel booking cancellation risk at reservation creation time with pre-booking features and operational check-in leakage quarantine.",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## 5. Decision Threshold & Business Handoff\n", "Evaluates decision threshold trade-offs between cancellation false positives and false negatives.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "if 'threshold_sensitivity' in test_eval:\n",
                    "    th_df = pd.DataFrame(test_eval['threshold_sensitivity'])\n",
                    "    print(th_df.to_string(index=False))\n",
                ],
            },
        ],
    )

    # 2. Flight Price
    create_notebook(
        NOTEBOOKS_DIR / "11_flight_price_modeling.ipynb",
        "Flight Price Prediction",
        "flight_price",
        "Predicts flight quote prices across advance booking horizons and departure classes with residual diagnostics.",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## 5. Booking Horizon Breakdown\n", "Evaluates regression errors across advance booking horizons (1-7d, 8-14d, 15+d).\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "if 'horizon_mae_inr' in test_eval:\n",
                    "    print('MAE by Booking Horizon:')\n",
                    "    for h, err in test_eval['horizon_mae_inr'].items():\n",
                    "        print(f'  {h:20s}: Rs. {err:,.2f}')\n",
                ],
            },
        ],
    )

    # 3. Demand Forecasting
    create_notebook(
        NOTEBOOKS_DIR / "12_demand_forecasting.ipynb",
        "Customer Demand Forecasting",
        "demand_forecasting",
        "Forecasts travel search demand volume 7 days ahead on a regular time-series panel with lag features and embargo gap validation.",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## 5. Forecast Error Diagnostics\n", "Analyzes WAPE, sMAPE, and directional forecast bias.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "if 'forecast_diagnostics' in test_eval:\n",
                    "    print('Forecast Diagnostics:')\n",
                    "    for k, v in test_eval['forecast_diagnostics'].items():\n",
                    "        print(f'  {k:25s}: {v}')\n",
                ],
            },
        ],
    )

    # 4. Inventory Forecasting
    create_notebook(
        NOTEBOOKS_DIR / "13_inventory_forecasting.ipynb",
        "Inventory Availability & Stockout Forecasting",
        "inventory_forecasting",
        "Forecasts future available inventory quantities and predicts impending stockout events with critical threshold recall.",
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## 5. Stockout Detection Analysis\n", "Evaluates stockout detection recall against the 5-unit safety stockout threshold.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "if 'stockout_diagnostics' in test_eval:\n",
                    "    print('Stockout Diagnostics:')\n",
                    "    for k, v in test_eval['stockout_diagnostics'].items():\n",
                    "        print(f'  {k:25s}: {v}')\n",
                ],
            },
        ],
    )


if __name__ == "__main__":
    main()
