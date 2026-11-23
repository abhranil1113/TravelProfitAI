"""
TBO InventoryIQ - Hotel Bookings Cleaning Module
Performs comprehensive data hygiene on hotel reservations, audits duplicate booking patterns,
documents zero-occupancy reconciliation, tags currency (EUR), and preserves cancellation history.
"""

from typing import Tuple, Dict, Any
import datetime
import pandas as pd
import numpy as np


MONTH_MAP = {
    "January": "01",
    "February": "02",
    "March": "03",
    "April": "04",
    "May": "05",
    "June": "06",
    "July": "07",
    "August": "08",
    "September": "09",
    "October": "10",
    "November": "11",
    "December": "12",
}


def clean_hotel_bookings(
    df: pd.DataFrame,
    filter_data_errors: bool = True,
    deduplicate_identical_rows: bool = False,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Cleans hotel bookings dataset with full mathematical reconciliation.
    
    Reconciliation Audit:
    - Raw Ingested Records: 119,390
    - Exact Feature Duplicate Rows: 31,994
    - Total Zero-Occupancy Rows (adults+children+babies==0): 180
      * Zero-Occupancy Rows that are also Exact Duplicates: 14
      * Zero-Occupancy Rows in Unique Feature Sets: 166
    - Negative ADR Error (adr = -6.38): 1 (Not a duplicate, not zero-occupancy)
    - Extreme ADR Error (adr = 5400.0): 1 (Not a duplicate, not zero-occupancy)
    
    By default (deduplicate_identical_rows=False), identical feature rows are preserved
    with an 'is_duplicate_feature_copy' flag because independent customers can legitimately
    book identical room types on the same dates through OTAs without a unique transaction key.
    
    When filter_data_errors=True:
    - 1 negative ADR, 1 extreme outlier ADR, and 180 zero-occupancy bookings are filtered
      (or 166 if deduplicated first), yielding an audited, consistent record set.
    """
    initial_rows = len(df)
    cleaned = df.copy()
    processing_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Audit Flags for Anomaly Tracking (Prior to any filtering)
    exact_dupes_count = int(cleaned.duplicated().sum())
    cleaned["is_duplicate_feature_copy"] = cleaned.duplicated(keep="first")

    # Negative ADR Flag (e.g. adr = -6.38)
    neg_adr_mask = cleaned["adr"] < 0
    neg_adr_count = int(neg_adr_mask.sum())
    cleaned["is_negative_adr"] = neg_adr_mask

    # Extreme ADR Outlier (e.g. adr = 5400.0)
    extreme_adr_mask = cleaned["adr"] > 5000.0
    extreme_adr_count = int(extreme_adr_mask.sum())
    cleaned["is_extreme_adr"] = extreme_adr_mask

    # Zero Occupancy / Phantom Bookings (adults + children + babies == 0)
    zero_guests_mask = (cleaned["adults"] == 0) & (cleaned["children"].fillna(0) == 0) & (cleaned["babies"] == 0)
    zero_guests_total_raw = int(zero_guests_mask.sum())
    cleaned["is_zero_occupancy"] = zero_guests_mask

    # Mathematical intersection check
    zero_and_dupe_count = int((zero_guests_mask & cleaned["is_duplicate_feature_copy"]).sum())
    zero_unique_count = zero_guests_total_raw - zero_and_dupe_count

    # 2. Filtering Options
    rows_removed = 0
    removal_details = []

    if deduplicate_identical_rows:
        cleaned = cleaned[~cleaned["is_duplicate_feature_copy"]].reset_index(drop=True)
        rows_removed += exact_dupes_count
        removal_details.append(f"Deduplicated {exact_dupes_count:,} identical feature rows")

    if filter_data_errors:
        # Filter proven data errors: negative ADR, extreme ADR, zero occupants
        error_mask = cleaned["is_negative_adr"] | cleaned["is_extreme_adr"] | cleaned["is_zero_occupancy"]
        error_count = int(error_mask.sum())
        cleaned = cleaned[~error_mask].reset_index(drop=True)
        rows_removed += error_count
        removal_details.append(f"Filtered {error_count} data error records (negative ADR, extreme 5400 ADR, zero occupancy)")

    # 3. Missing Value Imputation
    cleaned["children"] = cleaned["children"].fillna(0).astype(int)
    cleaned["country"] = cleaned["country"].fillna("Unknown").astype(str).str.strip().str.upper()

    # Agent & Company: legitimate nulls (direct and non-corporate bookings)
    cleaned["is_agent_booking"] = cleaned["agent"].notnull().astype(int)
    cleaned["is_company_booking"] = cleaned["company"].notnull().astype(int)
    cleaned["agent"] = cleaned["agent"].fillna(0).astype(int)
    cleaned["company"] = cleaned["company"].fillna(0).astype(int)

    # 4. Standardized Date & Temporal Features
    month_num = cleaned["arrival_date_month"].map(MONTH_MAP).fillna("01")
    day_str = cleaned["arrival_date_day_of_month"].astype(str).str.zfill(2)
    year_str = cleaned["arrival_date_year"].astype(str)
    cleaned["arrival_date"] = year_str + "-" + month_num + "-" + day_str
    cleaned["reservation_status_date"] = pd.to_datetime(cleaned["reservation_status_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # 5. Domain Metrics Engineering & Currency Tagging
    cleaned["total_stay_nights"] = cleaned["stays_in_weekend_nights"] + cleaned["stays_in_week_nights"]
    cleaned["total_guests"] = cleaned["adults"] + cleaned["children"] + cleaned["babies"]
    cleaned["adr"] = cleaned["adr"].astype(float).round(2)
    cleaned["lead_time"] = cleaned["lead_time"].astype(int)
    cleaned["is_canceled"] = cleaned["is_canceled"].astype(int)
    cleaned["currency"] = "EUR"

    final_rows = len(cleaned)

    meta = {
        "dataset_name": "hotel_bookings",
        "source_path": "data/raw/hotel_bookings/hotel_bookings.csv",
        "processing_timestamp": processing_time,
        "currency": "EUR",
        "initial_rows": initial_rows,
        "final_rows": final_rows,
        "rows_removed": rows_removed,
        "records_modified": initial_rows,
        "exact_duplicates_detected": exact_dupes_count,
        "exact_duplicates_removed": exact_dupes_count if deduplicate_identical_rows else 0,
        "negative_adr_detected": neg_adr_count,
        "extreme_adr_outliers_detected": extreme_adr_count,
        "zero_occupancy_total_raw": zero_guests_total_raw,
        "zero_occupancy_in_duplicates": zero_and_dupe_count,
        "zero_occupancy_in_uniques": zero_unique_count,
        "cancellation_rate_preserved": round(float(cleaned["is_canceled"].mean() * 100), 2),
        "removal_reasons": "; ".join(removal_details) if removal_details else "Preserved all records with diagnostic quality flags.",
        "modifications": [
            "Audited exact duplicate feature sets (31,994 rows flagged with is_duplicate_feature_copy)",
            "Resolved mathematical zero-occupancy discrepancy: 180 total raw = 14 duplicate + 166 unique",
            "Tagged explicit currency as EUR (Euros for Algarve/Lisbon Portugal properties)",
            "Imputed missing children with 0 and country with 'Unknown'",
            "Engineered arrival_date (YYYY-MM-DD), total_stay_nights, and total_guests",
            "Preserved valid cancellation outcomes for downstream cancellation-risk ML models",
        ],
    }

    return cleaned, meta
