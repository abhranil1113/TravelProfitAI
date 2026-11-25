"""
TBO InventoryIQ - Feature Metadata & Dictionary Generator (Phase 3)
Builds feature_dictionary.csv, feature_metadata.json, and generation summary metadata.
"""

from pathlib import Path
from typing import Dict, List, Any
import json
import pandas as pd

from feature_engineering.config import REPORTS_DIR, LEAKAGE_EXCLUSIONS


def generate_feature_dictionary_records(
    feature_datasets: Dict[str, pd.DataFrame]
) -> List[Dict[str, Any]]:
    """
    Generates structured dictionary records for every engineered feature across all datasets,
    rigorously distinguishing predictive inputs, target variables, quarantined leakage,
    analytical metrics, and optimization parameters.
    """
    records = []

    # Domain Knowledge & Descriptions Registry
    # Format: col: (description, formula_or_logic, business_purpose, unit, leakage_status, ml_readiness_status)
    descriptions_registry = {
        # Hotel Cancellation Features
        "is_canceled": (
            "Binary target variable indicating if the hotel booking was canceled (1) or honored (0)",
            "hotel_bookings['is_canceled']",
            "target_variable",
            "FLAG",
            "None",
            "TARGET_VARIABLE",
        ),
        "lead_time_days": (
            "Number of days elapsed between booking entry and arrival date",
            "lead_time.clip(lower=0)",
            "predictive_lead_time",
            "DAYS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "lead_time_bucket": (
            "Categorical binning of lead time into operational windows (0-7d to 365d+)",
            "bin_series(lead_time_days)",
            "predictive_risk_tiering",
            "CATEGORICAL",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "lead_time_log": (
            "Log1p transformed lead time to normalize extreme advance bookings",
            "safe_log1p(lead_time_days)",
            "predictive_scale_normalization",
            "LOG_DAYS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "total_stay_nights": (
            "Sum of weekend nights and weekday nights duration",
            "stays_in_weekend_nights + stays_in_week_nights",
            "predictive_length_of_stay",
            "NIGHTS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "weekend_nights_ratio": (
            "Proportion of stay spent on weekend nights",
            "safe_divide(stays_in_weekend_nights, total_stay_nights)",
            "predictive_leisure_profile",
            "RATIO",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "weekday_nights_ratio": (
            "Proportion of stay spent on weekday nights",
            "safe_divide(stays_in_week_nights, total_stay_nights)",
            "predictive_corporate_profile",
            "RATIO",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "total_guests": (
            "Total headcount: adults + children + babies",
            "adults + children + babies",
            "predictive_party_size",
            "PERSONS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "is_solo_traveller": (
            "Indicator flag if reservation is for exactly 1 guest",
            "total_guests == 1",
            "predictive_occupancy_profile",
            "BOOLEAN",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "is_family_booking": (
            "Indicator flag if reservation includes children or babies",
            "children + babies > 0",
            "predictive_family_profile",
            "BOOLEAN",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "adr": (
            "Average Daily Rate per room night agreed at booking time in Euros (€)",
            "adr.clip(lower=0.0)",
            "predictive_pricing_yield",
            "EUR",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "adr_log": (
            "Log1p transformed Average Daily Rate",
            "safe_log1p(adr)",
            "predictive_scale_normalization",
            "LOG_EUR",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "adr_per_guest": (
            "Average Daily Rate normalized per individual guest headcount",
            "safe_divide(adr, total_guests)",
            "predictive_per_person_cost",
            "EUR",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "reservation_status": (
            "Operational reservation checkout/cancellation status recorded post-departure",
            "reservation_status",
            "operational_outcome",
            "CATEGORICAL",
            "Critical (Direct Target Leakage)",
            "EXCLUDED_LEAKAGE",
        ),
        "reservation_status_date": (
            "Date when checkout or cancellation action was logged in PMS",
            "reservation_status_date",
            "operational_outcome",
            "DATE",
            "Critical (Direct Target Leakage)",
            "EXCLUDED_LEAKAGE",
        ),
        "assigned_room_type": (
            "Room type physically assigned at check-in / night audit",
            "assigned_room_type",
            "operational_outcome",
            "CATEGORICAL",
            "Critical (Post-Booking Check-in Outcome)",
            "EXCLUDED_LEAKAGE",
        ),
        "room_type_changed": (
            "Indicator if assigned room type differs from originally reserved type",
            "reserved_room_type != assigned_room_type",
            "operational_outcome",
            "BOOLEAN",
            "Critical (Post-Booking Check-in Outcome)",
            "EXCLUDED_LEAKAGE",
        ),
        "booking_changes": (
            "Number of reservation modifications made between booking and arrival",
            "booking_changes",
            "post_booking_monitoring",
            "COUNT",
            "Medium (Post-Booking Modification)",
            "EXCLUDED_LEAKAGE",
        ),
        "market_segment_historical_cancel_rate": (
            "Global Bayesian smoothed prior cancellation rate for market segment across full dataset",
            "df.groupby('market_segment')['is_canceled'].agg(['count', 'mean'])",
            "analytical_reference_metric",
            "PROBABILITY",
            "High (Global Full-Dataset Target Leakage)",
            "EXCLUDED_LEAKAGE",
        ),
        "deposit_type_historical_cancel_rate": (
            "Global Bayesian smoothed prior cancellation rate for deposit type across full dataset",
            "df.groupby('deposit_type')['is_canceled'].agg(['count', 'mean'])",
            "analytical_reference_metric",
            "PROBABILITY",
            "High (Global Full-Dataset Target Leakage)",
            "EXCLUDED_LEAKAGE",
        ),
        # Flight Dynamic Pricing Features
        "price": (
            "Flight ticket commercial price quote in Indian Rupees (₹)",
            "price.astype(float)",
            "target_variable",
            "INR",
            "None",
            "TARGET_VARIABLE",
        ),
        "price_log": (
            "Log1p transformed flight ticket price for variance stabilization",
            "safe_log1p(price)",
            "target_transform",
            "LOG_INR",
            "None",
            "TARGET_VARIABLE",
        ),
        "days_left": (
            "Days remaining between quote observation and flight departure",
            "days_left.clip(lower=1)",
            "predictive_advance_window",
            "DAYS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "days_left_bucket": (
            "Categorical binning capturing departure surge curve",
            "bin_series(days_left)",
            "predictive_surge_window",
            "CATEGORICAL",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "duration_hours": (
            "Flight duration elapsed time in decimal hours",
            "duration.astype(float)",
            "predictive_haul_proxy",
            "HOURS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "duration_bucket": (
            "Categorical haul classification (Short, Medium, Long, Ultra-Long)",
            "bin_series(duration_hours)",
            "predictive_haul_category",
            "CATEGORICAL",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "is_business_class": (
            "Indicator if fare quote is for Business cabin class",
            "class.str.lower() == 'business'",
            "predictive_cabin_premium",
            "BOOLEAN",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "is_direct_flight": (
            "Indicator if flight is non-stop direct service",
            "stops_count == 0",
            "predictive_service_level",
            "BOOLEAN",
            "None",
            "PREDICTIVE_INPUT",
        ),
        # Customer Search Demand Features
        "search_lead_days": (
            "Days elapsed between search submission and intended travel date",
            "travel_date - search_date",
            "predictive_search_lead",
            "DAYS",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "search_price_inr": (
            "Searched travel package price displayed to consumer (₹)",
            "search_price.clip(lower=0.0)",
            "predictive_consumer_budget",
            "INR",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "search_price_per_traveller_inr": (
            "Search price quote normalized per searched passenger",
            "safe_divide(search_price_inr, travellers_count)",
            "predictive_budget_density",
            "INR",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "clicked": (
            "Post-search user interaction indicator flag",
            "clicked.astype(bool)",
            "funnel_conversion_metric",
            "BOOLEAN",
            "Critical (Post-Search Outcome)",
            "EXCLUDED_LEAKAGE",
        ),
        "booking_completed": (
            "Post-search downstream transaction checkout completion flag",
            "booking_completed.astype(bool)",
            "funnel_conversion_metric",
            "BOOLEAN",
            "Critical (Post-Search Outcome)",
            "EXCLUDED_LEAKAGE",
        ),
        "has_funnel_anomaly": (
            "Data consistency check flagging bookings with no preceding click",
            "booking_completed & ~clicked",
            "data_quality_anomaly",
            "BOOLEAN",
            "Critical (Post-Search Outcome)",
            "EXCLUDED_LEAKAGE",
        ),
        # Inventory Features
        "occupancy_rate": (
            "Ratio of booked quantity over total physical capacity (0.0 to 1.0)",
            "safe_divide(booked_quantity, total_capacity)",
            "predictive_utilization",
            "RATIO",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "inventory_utilization_rate": (
            "Capacity utilization rate (synonymous with occupancy_rate)",
            "safe_divide(booked_quantity, total_capacity)",
            "predictive_utilization",
            "RATIO",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "availability_rate": (
            "Fraction of capacity remaining available to book (0.0 to 1.0)",
            "safe_divide(available_quantity, total_capacity)",
            "predictive_availability",
            "RATIO",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "inventory_sold_out_indicator": (
            "Flag indicating zero remaining bookable units",
            "available_quantity == 0",
            "predictive_stockout_flag",
            "BOOLEAN",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "booking_velocity_units_per_day": (
            "Incremental units booked per day between consecutive snapshot observations",
            "safe_divide(delta_booked, delta_days)",
            "predictive_booking_pace",
            "UNITS_PER_DAY",
            "None (Strict Past Lag)",
            "PREDICTIVE_INPUT",
        ),
        "inventory_depletion_velocity": (
            "Rate of inventory reduction per day between snapshots",
            "safe_divide(-delta_available, delta_days)",
            "predictive_depletion_speed",
            "UNITS_PER_DAY",
            "None (Strict Past Lag)",
            "PREDICTIVE_INPUT",
        ),
        # Supplier Profitability & Procurement Economics Features
        "purchase_cost_inr": (
            "Wholesale B2B procurement cost per unit contracted with supplier (₹)",
            "purchase_cost.clip(lower=0.0)",
            "optimization_cost_coefficient",
            "INR",
            "None",
            "OPTIMIZATION_INPUT",
        ),
        "selling_price_inr": (
            "Retail commercial selling price quote to traveler (₹)",
            "selling_price.clip(lower=0.0)",
            "optimization_revenue_coefficient",
            "INR",
            "None",
            "OPTIMIZATION_INPUT",
        ),
        "gross_margin_inr": (
            "Monetary gross margin per unit: selling_price - purchase_cost (₹)",
            "selling_price - purchase_cost",
            "optimization_objective_coefficient",
            "INR",
            "Deterministic Financial Metric",
            "OPTIMIZATION_INPUT",
        ),
        "gross_margin_percentage": (
            "Gross profit margin percentage: (selling - cost) / selling * 100",
            "safe_divide(selling - cost, selling) * 100",
            "optimization_profit_rate",
            "PERCENT",
            "Deterministic Financial Metric",
            "OPTIMIZATION_INPUT",
        ),
        "markup_percentage": (
            "Wholesale markup percentage over supplier purchase cost",
            "safe_divide(selling - cost, cost) * 100",
            "optimization_markup_rate",
            "PERCENT",
            "Deterministic Financial Metric",
            "OPTIMIZATION_INPUT",
        ),
        "is_negative_margin": (
            "Alert flag identifying loss-making supplier inventory contracts",
            "selling_price < purchase_cost",
            "optimization_infeasible_filter",
            "BOOLEAN",
            "Deterministic Financial Metric",
            "OPTIMIZATION_INPUT",
        ),
        "minimum_purchase_qty": (
            "Minimum batch purchase commitment required by supplier contract",
            "minimum_purchase_qty.clip(lower=1)",
            "optimization_allocation_bound",
            "UNITS",
            "None",
            "OPTIMIZATION_INPUT",
        ),
        "min_purchase_commitment_cost_inr": (
            "Minimum cash outlay required to contract supplier batch",
            "minimum_purchase_qty * purchase_cost",
            "optimization_cashflow_bound",
            "INR",
            "None",
            "OPTIMIZATION_INPUT",
        ),
        # Macro Market Features
        "demand_index": (
            "Normalized destination market demand intensity baseline [0.0, 1.0]",
            "demand_index.clip(0.0, 1.0)",
            "exogenous_demand_baseline",
            "INDEX",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "has_special_event": (
            "Indicator if travel date coincides with holiday, festival, or event",
            "holiday | festival | event",
            "exogenous_demand_catalyst",
            "BOOLEAN",
            "None",
            "PREDICTIVE_INPUT",
        ),
        "composite_seasonal_demand_score": (
            "Configurable composite score combining demand index, events, and weather",
            "clip(0.70*demand + 20*event - 10*rain, 0, 100)",
            "procurement_priority_score",
            "SCORE_0_TO_100",
            "None",
            "PREDICTIVE_INPUT",
        ),
        # Cross-Domain Synthesis
        "demand_to_supply_ratio": (
            "Synthesized cross-domain ratio of destination search demand to available physical capacity",
            "safe_divide(search_volume, physical_capacity)",
            "optimization_candidate_pressure",
            "RATIO",
            "None",
            "OPTIMIZATION_INPUT",
        ),
    }

    for ds_name, df in feature_datasets.items():
        quarantined = LEAKAGE_EXCLUSIONS.get(ds_name, [])
        for col in df.columns:
            dtype_str = str(df[col].dtype)
            if col in descriptions_registry:
                desc, src, purpose, unit, leak_status, ml_status = descriptions_registry[col]
            else:
                # Default heuristic classification
                if col in quarantined:
                    desc = f"Quarantined feature '{col}' in {ds_name} (excluded from model training)"
                    src = col
                    purpose = "operational_outcome_or_target_leakage"
                    unit = "CATEGORICAL" if "category" in dtype_str or "object" in dtype_str else "NUMERIC"
                    leak_status = "Quarantined / Excluded"
                    ml_status = "EXCLUDED_LEAKAGE"
                elif col in ["price", "is_canceled"]:
                    desc = f"Supervised target variable '{col}' in {ds_name}"
                    src = col
                    purpose = "target_variable"
                    unit = "FLAG" if "int" in dtype_str else "CURRENCY"
                    leak_status = "Target Variable"
                    ml_status = "TARGET_VARIABLE"
                elif ds_name in ["supplier_profitability_features", "destination_demand_supply_features"]:
                    desc = f"Procurement optimization input '{col}' in {ds_name}"
                    src = col
                    purpose = "optimization_parameter"
                    unit = "STANDARD"
                    leak_status = "None"
                    ml_status = "OPTIMIZATION_INPUT"
                elif (
                    col.endswith("_id")
                    or col in ["currency", "booking_date", "arrival_date", "travel_date", "snapshot_date", "search_date", "unit"]
                ):
                    desc = f"Entity identifier or partition timestamp '{col}' in {ds_name}"
                    src = col
                    purpose = "metadata_identifier"
                    unit = "IDENTIFIER"
                    leak_status = "None"
                    ml_status = "METADATA_ID"
                else:
                    desc = f"Predictive feature '{col}' in {ds_name}"
                    src = col
                    purpose = "predictive_feature"
                    unit = "STANDARD"
                    leak_status = "None"
                    ml_status = "PREDICTIVE_INPUT"

            records.append({
                "feature_name": col,
                "dataset_name": ds_name,
                "data_type": dtype_str,
                "formula_or_logic": src,
                "business_purpose": purpose,
                "ml_readiness_status": ml_status,
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
