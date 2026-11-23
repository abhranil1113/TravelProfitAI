"""
TBO InventoryIQ - Outlier Detection Module
Identifies numerical anomalies using the Interquartile Range (IQR) technique and domain thresholding.
"""

from typing import Dict, List, Any, Tuple
import pandas as pd
import numpy as np


def detect_outliers_iqr(
    series: pd.Series,
    multiplier: float = 1.5,
) -> Tuple[int, float, float, float, float, float]:
    """
    Computes IQR bounds and returns (outlier_count, q25, q75, iqr, lower_bound, upper_bound).
    """
    clean_s = series.dropna()
    if len(clean_s) == 0:
        return 0, 0.0, 0.0, 0.0, 0.0, 0.0

    q25 = float(clean_s.quantile(0.25))
    q75 = float(clean_s.quantile(0.75))
    iqr = q75 - q25
    lower_bound = float(q25 - multiplier * iqr)
    upper_bound = float(q75 + multiplier * iqr)

    outliers = (clean_s < lower_bound) | (clean_s > upper_bound)
    return int(outliers.sum()), q25, q75, iqr, lower_bound, upper_bound


def analyze_dataset_outliers(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Analyzes numerical distributions and detects outliers across key travel metrics.
    """
    records = []

    # Target field definitions: (dataset_name, column_name, domain_reason, domain_lower, domain_upper)
    targets = [
        ("flight_prices", "price", "Airfare pricing dynamic variations (Economy vs Business)", 500.0, 150000.0),
        ("flight_prices", "duration", "Flight duration range including multi-stop routes", 0.5, 60.0),
        ("hotel_bookings", "adr", "Hotel Average Daily Rate per room night", 0.0, 1000.0),
        ("hotel_bookings", "lead_time", "Booking advance booking lead time in days", 0.0, 730.0),
        ("supplier_offers", "purchase_cost", "Contracted inventory wholesale unit cost", 500.0, 100000.0),
        ("supplier_offers", "selling_price", "Target resale price for hotel & flight inventory", 700.0, 150000.0),
        ("supplier_offers", "available_quantity", "Allocated supplier room/seat batch allotment", 1.0, 500.0),
        ("inventory_availability", "booked_quantity", "Snapshot cumulative confirmed bookings", 0.0, 500.0),
        ("inventory_availability", "available_quantity", "Snapshot remaining available inventory", 0.0, 500.0),
        ("customer_search_events", "search_price", "Observed quote price during customer search", 500.0, 100000.0),
        ("customer_search_events", "travellers_count", "Customer group party size", 1.0, 20.0),
        ("market_seasonal_signals", "demand_index", "Composite macroeconomic seasonal demand scale", 0.0, 1.0),
        ("market_seasonal_signals", "rainfall_mm", "Monthly historical precipitation index", 0.0, 1000.0),
        ("market_seasonal_signals", "temperature", "Regional climate mean temperature in Celsius", -40.0, 55.0),
    ]

    for ds_name, col, explanation, d_min, d_max in targets:
        if ds_name not in datasets or col not in datasets[ds_name].columns:
            continue

        s = datasets[ds_name][col]
        total_valid = int(s.notnull().sum())
        out_cnt, q25, q75, iqr, lb, ub = detect_outliers_iqr(s)
        pct = round((out_cnt / total_valid * 100), 2) if total_valid > 0 else 0.0

        min_val = float(s.min()) if total_valid > 0 else 0.0
        max_val = float(s.max()) if total_valid > 0 else 0.0

        # Domain boundary check
        domain_violations = int(((s < d_min) | (s > d_max)).sum())

        records.append({
            "dataset_name": ds_name,
            "column_name": col,
            "total_records": total_valid,
            "min_value": round(min_val, 2),
            "max_value": round(max_val, 2),
            "q25": round(q25, 2),
            "q75": round(q75, 2),
            "iqr": round(iqr, 2),
            "iqr_lower_bound": round(lb, 2),
            "iqr_upper_bound": round(ub, 2),
            "iqr_outlier_count": out_cnt,
            "iqr_outlier_pct": pct,
            "domain_min_threshold": d_min,
            "domain_max_threshold": d_max,
            "domain_breach_count": domain_violations,
            "business_classification": "Legitimate High-Value Commercial Variation" if domain_violations == 0 else "Contains Potential Data Error",
            "context_explanation": explanation,
        })

    return pd.DataFrame(records)
