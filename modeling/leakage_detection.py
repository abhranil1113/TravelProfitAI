"""
TBO InventoryIQ - Target Leakage & Prediction Cutoff Detection (Phase 4)
Verifies that no target labels, target transformations, post-event outcomes,
or check-in assignments leak into the predictor matrix X.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import logging

from modeling.registry.task_registry import TaskConfig

logger = logging.getLogger(__name__)

# Known post-event or circular leakage variables by task
KNOWN_LEAKAGE_MAP: Dict[str, List[str]] = {
    "hotel_cancellation": [
        "is_canceled",
        "reservation_status",
        "reservation_status_date",
        "assigned_room_type",
        "room_type_changed",
        "market_segment_historical_cancel_rate",
        "deposit_type_historical_cancel_rate",
        "booking_changes",
    ],
    "flight_price": [
        "price",
        "price_log",
        "price_record_id",
    ],
    "demand_forecasting": [
        "clicked",
        "booking_completed",
        "has_funnel_anomaly",
        "future_search_volume_7d",
    ],
    "inventory_forecasting": [
        "future_available_quantity",
        "future_booked_quantity",
        "actual_stockout",
        "inventory_sold_out_indicator",
    ],
}


def audit_task_leakage(
    task_config: TaskConfig,
    X: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Audits candidate predictor columns in X against task-specific leakage rules.
    Raises ValueError if critical target leakage is detected.
    """
    feature_names = set(X.columns)
    leaked_features = []

    # 1. Target column in predictors
    if task_config.target_column in feature_names:
        leaked_features.append({
            "feature": task_config.target_column,
            "reason": "Direct target label present in predictor matrix.",
            "severity": "CRITICAL",
        })

    # 2. Known post-event outcomes
    known_leaks = KNOWN_LEAKAGE_MAP.get(task_config.task_name, [])
    for leak in known_leaks:
        if leak in feature_names:
            leaked_features.append({
                "feature": leak,
                "reason": "Post-event operational outcome or direct target transformation.",
                "severity": "CRITICAL",
            })

    # 3. Explicitly excluded columns
    for excl in task_config.excluded_columns:
        if excl in feature_names:
            leaked_features.append({
                "feature": excl,
                "reason": "Explicitly excluded column present in feature matrix.",
                "severity": "CRITICAL",
            })

    has_critical_leakage = any(item["severity"] == "CRITICAL" for item in leaked_features)

    audit_result = {
        "task_name": task_config.task_name,
        "is_clean": len(leaked_features) == 0,
        "has_critical_leakage": has_critical_leakage,
        "leaked_features": leaked_features,
        "features_audited_count": len(feature_names),
    }

    if has_critical_leakage or len(leaked_features) > 0:
        leak_names = [item["feature"] for item in leaked_features]
        raise ValueError(
            f"Target leakage or unauthorized feature detected for task '{task_config.task_name}': {leak_names}. "
            f"Training aborted to prevent invalid model results."
        )

    return audit_result
