"""
TBO InventoryIQ - Data Type Validation Module
Inspects actual vs expected data types, detects malformed values, and reports conversion issues.
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np


def validate_data_types(
    dataset_name: str,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Validates data types and checks for malformed dates, numericals, and IDs.
    Returns a DataFrame with column-level datatype evaluation.
    """
    records = []
    
    for col in df.columns:
        actual_dtype = str(df[col].dtype)
        col_lower = col.lower()
        issue_type = "None"
        issue_details = "Data type matches operational requirements"
        malformed_count = 0

        # 1. ID Columns (Should be string/object, never converted to float)
        if "id" in col_lower or "code" in col_lower:
            if actual_dtype in ["float64", "float32"]:
                issue_type = "FloatIdentifier"
                issue_details = "ID stored as float; risks loss of leading zeros or precision"
                malformed_count = df[col].notnull().sum()
            elif actual_dtype in ["int64", "int32"]:
                issue_type = "IntegerIdentifier"
                issue_details = "ID stored as integer; recommend string representation"
                malformed_count = df[col].notnull().sum()

        # 2. Date Columns (Should be valid parseable date strings or datetime)
        elif "date" in col_lower and not any(k in col_lower for k in ["year", "month", "week", "day"]):
            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                # Test date parseability
                parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
                invalid_dates = parsed.isnull() & df[col].notnull()
                malformed_count = int(invalid_dates.sum())
                if malformed_count > 0:
                    issue_type = "InvalidDateFormat"
                    issue_details = f"{malformed_count} rows have invalid date formatting"
                else:
                    issue_type = "StringDate"
                    issue_details = "Date stored as string; ready for datetime conversion"

        # 3. Financial / Price columns (Should be numeric, float/decimal)
        elif any(k in col_lower for k in ["price", "cost", "adr", "amount", "rainfall", "temperature", "demand_index"]):
            if not pd.api.types.is_numeric_dtype(df[col]):
                numeric_converted = pd.to_numeric(df[col], errors="coerce")
                malformed_count = int((numeric_converted.isnull() & df[col].notnull()).sum())
                issue_type = "NonNumericFinancial"
                issue_details = f"{malformed_count} rows contain non-numeric characters in financial field"

        # 4. Quantity / Count columns (Should be integers)
        elif any(k in col_lower for k in ["count", "quantity", "capacity", "adults", "children", "babies", "nights"]):
            if not pd.api.types.is_numeric_dtype(df[col]):
                numeric_converted = pd.to_numeric(df[col], errors="coerce")
                malformed_count = int((numeric_converted.isnull() & df[col].notnull()).sum())
                issue_type = "NonNumericQuantity"
                issue_details = f"{malformed_count} rows contain non-numeric characters in count field"

        # 5. Boolean Indicators
        elif "indicator" in col_lower or col_lower in ["sold_out", "refundable", "clicked", "booking_completed", "is_canceled", "is_repeated_guest"]:
            unique_vals = set(df[col].dropna().unique())
            valid_bools = {True, False, 1, 0, "True", "False", "true", "false", 1.0, 0.0}
            invalid_bools = unique_vals - valid_bools
            if invalid_bools:
                issue_type = "InvalidBooleanValues"
                issue_details = f"Unexpected boolean representations: {invalid_bools}"
                malformed_count = len(invalid_bools)

        records.append({
            "dataset_name": dataset_name,
            "column_name": col,
            "actual_dtype": actual_dtype,
            "issue_type": issue_type,
            "malformed_count": malformed_count,
            "details": issue_details,
        })

    return pd.DataFrame(records)


def validate_all_data_types(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Run data type validation across all datasets.
    """
    all_records = []
    for name, df in datasets.items():
        res = validate_data_types(name, df)
        all_records.append(res)
    if all_records:
        return pd.concat(all_records, ignore_index=True)
    return pd.DataFrame()
