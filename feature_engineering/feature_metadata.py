"""
TBO InventoryIQ - Feature Metadata & Dictionary Generator (Phase 3)
Builds feature_dictionary.csv, feature_metadata.json, and generation summary metadata.
"""

from pathlib import Path
from typing import Dict, List, Any
import json
import pandas as pd

from feature_engineering.config import REPORTS_DIR


def generate_feature_dictionary_records(
    feature_datasets: Dict[str, pd.DataFrame]
) -> List[Dict[str, Any]]:
    """
    Generates structured dictionary records for every engineered feature across all datasets.
    """
    records = []

    # Domain Knowledge & Descriptions Registry
    descriptions_registry = {
        # Hotel
        "is_canceled": ("Binary target variable indicating if the hotel booking was canceled (1) or honored (0)", "hotel_bookings", "target", "FLAG", "None"),
        "lead_time_days": ("Number of days elapsed between booking entry and arrival date", "lead_time", "Booking Lead Time Window", "DAYS", "None"),
        "lead_time_bucket": ("Categorical binning of lead time into operational windows (0-7d to 365d+)", "lead_time_days", "Risk Tiering", "CATEGORICAL", "None"),
        "lead_time_log": ("Log1p transformed lead time to normalize extreme advance bookings", "lead_time_days", "Scale Normalization", "LOG_DAYS", "None"),
        "total_stay_nights": ("Sum of weekend nights and weekday nights duration", "stays_in_weekend_nights + stays_in_week_nights", "Length of Stay", "NIGHTS", "None"),
        "weekend_nights_ratio": ("Proportion of stay spent on weekend nights", "stays_in_weekend_nights / total_stay_nights", "Leisure Trip Indicator", "RATIO", "None"),
        "weekday_nights_ratio": ("Proportion of stay spent on weekday nights", "stays_in_week_nights / total_stay_nights", "Corporate Trip Indicator", "RATIO", "None"),
        "total_guests": ("Total headcount: adults + children + babies", "adults + children + babies", "Party Size", "PERSONS", "None"),
        "is_solo_traveller": ("Indicator flag if reservation is for exactly 1 guest", "total_guests == 1", "Single Occupancy", "BOOLEAN", "None"),
        "is_family_booking": ("Indicator flag if reservation includes children or babies", "children + babies > 0", "Family Travel Profile", "BOOLEAN", "None"),
        "adr": ("Average Daily Rate per room night in Euros (€)", "adr", "Hospitality Pricing Yield", "EUR", "None"),
        "adr_per_guest": ("Average Daily Rate normalized per individual guest headcount", "adr / total_guests", "Per-Person Cost", "EUR", "None"),
        "room_type_changed": ("Indicator if assigned room type differs from originally reserved type", "reserved != assigned", "Operational Upgrades / Overbooking", "BOOLEAN", "None"),
        "market_segment_historical_cancel_rate": ("Bayesian smoothed prior cancellation rate for the customer's market segment", "historical aggregations", "Segment Risk Benchmark", "PROBABILITY", "Historical Prior"),
        # Flight Prices
        "price": ("Flight ticket commercial price in Indian Rupees (₹)", "price", "Target Pricing Variable", "INR", "None"),
        "price_log": ("Log1p transformed flight ticket price for variance stabilization", "log1p(price)", "Transformed Target", "LOG_INR", "None"),
        "days_left": ("Days remaining between price observation and scheduled flight departure", "days_left", "Dynamic Advance Booking Window", "DAYS", "None"),
        "days_left_bucket": ("Categorical binning capturing the exponential departure surge curve", "days_left", "Pricing Window Tier", "CATEGORICAL", "None"),
        "duration_hours": ("Flight duration elapsed time in decimal hours", "duration", "Flight Haul Distance Proxy", "HOURS", "None"),
        "duration_bucket": ("Categorical haul classification (Short, Medium, Long, Ultra-Long)", "duration_hours", "Route Fleet Category", "CATEGORICAL", "None"),
        "is_business_class": ("Indicator if fare quote is for Business cabin class", "class == Business", "Cabin Premium", "BOOLEAN", "None"),
        "is_direct_flight": ("Indicator if flight is non-stop direct service", "stops_count == 0", "Service Quality", "BOOLEAN", "None"),
        # Customer Search
        "search_lead_days": ("Days elapsed between search submission and intended travel date", "travel_date - search_date", "Advance Planning Window", "DAYS", "None"),
        "search_price_inr": ("Searched travel package price quote displayed to consumer (₹)", "search_price", "Consumer Budget Consideration", "INR", "None"),
        "search_price_per_traveller_inr": ("Search price point normalized per searched passenger", "search_price / travellers_count", "Individual Budget Threshold", "INR", "None"),
        "travellers_per_room": ("Headcount density per requested hotel room", "travellers_count / rooms_count", "Room Sharing Density", "RATIO", "None"),
        "clicked": ("Analytical flag indicating whether user clicked search offer", "clicked", "Funnel Click Engagement", "BOOLEAN", "Post-Search Outcome"),
        "booking_completed": ("Analytical flag indicating whether search converted into paid booking", "booking_completed", "End-to-End Conversion", "BOOLEAN", "Post-Search Outcome"),
        # Inventory
        "occupancy_rate": ("Ratio of booked quantity over total physical capacity (0.0 to 1.0)", "booked_quantity / total_capacity", "Capacity Utilization", "RATIO", "None"),
        "inventory_utilization_rate": ("Synonymous with occupancy_rate under platform operational definition", "booked_quantity / total_capacity", "Capacity Utilization", "RATIO", "None"),
        "availability_rate": ("Fraction of inventory capacity remaining available to book (0.0 to 1.0)", "available_quantity / total_capacity", "Remaining Availability", "RATIO", "None"),
        "inventory_sold_out_indicator": ("Flag indicating zero remaining bookable units", "available_quantity == 0", "Stockout Risk", "BOOLEAN", "None"),
        "booking_velocity_units_per_day": ("Incremental units booked per day between consecutive snapshot observations", "delta_booked / delta_days", "Sales Velocity", "UNITS_PER_DAY", "Lagged Historical"),
        "inventory_depletion_velocity": ("Rate of inventory reduction per day between snapshots", "-delta_available / delta_days", "Depletion Speed", "UNITS_PER_DAY", "Lagged Historical"),
        # Supplier
        "purchase_cost_inr": ("Wholesale B2B procurement cost per unit paid to supplier (₹)", "purchase_cost", "Procurement Cost", "INR", "None"),
        "selling_price_inr": ("Retail commercial selling price to traveler (₹)", "selling_price", "Retail Revenue", "INR", "None"),
        "gross_margin_inr": ("Monetary gross margin per unit: selling_price - purchase_cost (₹)", "selling - cost", "Unit Margin", "INR", "None"),
        "gross_margin_percentage": ("Gross profit margin as percentage of retail selling price", "(selling - cost) / selling * 100", "Gross Profit Margin", "PERCENT", "Deterministic Metric"),
        "markup_percentage": ("Wholesale markup percentage over supplier purchase cost", "(selling - cost) / cost * 100", "Cost Markup Rate", "PERCENT", "Deterministic Metric"),
        "is_negative_margin": ("Flag identifying loss-making supplier inventory contracts", "selling < cost", "Margin Deficit Alert", "BOOLEAN", "None"),
        "min_purchase_commitment_cost_inr": ("Minimum cash outlay required to contract supplier batch", "minimum_purchase_qty * cost", "Cash Outlay Commitment", "INR", "None"),
        # Market Demand
        "demand_index": ("Normalized market demand intensity index across calendar year", "demand_index", "Market Demand Baseline", "INDEX", "None"),
        "has_special_event": ("Indicator if travel date coincides with holiday, festival, or event", "holiday | festival | event", "Event Surge Catalyst", "BOOLEAN", "None"),
        "composite_seasonal_demand_score": ("Configurable composite score combining demand index, events, and weather", "0.65*demand + 15*event - 10*rain", "Procurement Demand Priority", "SCORE_0_TO_100", "None"),
    }

    for ds_name, df in feature_datasets.items():
        for col in df.columns:
            dtype_str = str(df[col].dtype)
            desc, src, purpose, unit, leak_status = descriptions_registry.get(
                col,
                (f"Engineered feature '{col}' in {ds_name}", col, "Analytical Dimension", "STANDARD", "None")
            )
            records.append({
                "feature_name": col,
                "dataset_name": ds_name,
                "data_type": dtype_str,
                "formula_or_logic": src,
                "business_purpose": purpose,
                "description": desc,
                "unit": unit,
                "missing_value_treatment": "Zero-imputed / Flagged / Categorical Unknown",
                "leakage_status": leak_status,
            })

    return records


def export_feature_metadata_and_dictionary(
    feature_datasets: Dict[str, pd.DataFrame],
    generation_summaries: List[Dict[str, Any]],
) -> Dict[str, Path]:
    """
    Saves feature_dictionary.csv, feature_metadata.json, and feature_generation_summary.json.
    """
    # 1. Feature Dictionary CSV
    records = generate_feature_dictionary_records(feature_datasets)
    dict_df = pd.DataFrame(records)
    dict_csv_path = REPORTS_DIR / "feature_dictionary.csv"
    dict_df.to_csv(dict_csv_path, index=False)

    # 2. Feature Metadata JSON
    meta_json_path = REPORTS_DIR / "feature_metadata.json"
    metadata_bundle = {
        "project": "TBO InventoryIQ",
        "phase": "Phase 3 - Feature Engineering & Dataset Transformation",
        "total_datasets": len(feature_datasets),
        "total_features": len(records),
        "features": records,
    }
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata_bundle, f, indent=2)

    # 3. Feature Generation Summary JSON
    summary_json_path = REPORTS_DIR / "feature_generation_summary.json"
    summary_bundle = {
        "status": "COMPLETED",
        "timestamp": pd.Timestamp.now().isoformat(),
        "datasets": generation_summaries,
    }
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_bundle, f, indent=2)

    return {
        "dictionary_csv": dict_csv_path,
        "metadata_json": meta_json_path,
        "summary_json": summary_json_path,
    }
