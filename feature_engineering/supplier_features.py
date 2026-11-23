"""
TBO InventoryIQ - Supplier Profitability Feature Engineering (Phase 3)
Builds supplier gross margin, markup percentage, contractual commitment,
and offer competitiveness features.

CURRENCY & METRIC AUDIT NOTE:
The raw synthetic dataset (`data/synthetic/supplier_offers.csv`) does not declare an official
ISO 4217 currency code. The numeric values are preserved exactly and modeled as INR (₹)
for consistency with customer search prices and domestic flight price quotes across the platform.
Both canonical names (`purchase_cost`, `selling_price`) and currency-aliased names
(`purchase_cost_inr`, `selling_price_inr`) are provided.
"""

import pandas as pd
import numpy as np

from feature_engineering.base_transformer import (
    BaseFeatureTransformer,
    safe_divide,
    safe_log1p,
    safe_date_diff_days,
    bin_series,
)
from feature_engineering.config import BIN_CONFIGS


class SupplierFeatureTransformer(BaseFeatureTransformer):
    """
    Transforms supplier offer records into procurement economics & margin features.
    Preserves exact numeric values while exposing canonical and currency-tagged columns.
    """
    def __init__(self):
        super().__init__(name="supplier_profitability_features")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # 1. Identifiers & Entity Attributes
        out["offer_id"] = df["offer_id"].astype(str)
        out["supplier_id"] = df["supplier_id"].astype(str)
        out["inventory_id"] = df["inventory_id"].astype(str)
        out["inventory_type"] = df["inventory_type"].astype(str)
        out["origin_id"] = df["origin_id"].astype(str)
        out["destination_id"] = df["destination_id"].astype(str)
        out["travel_date"] = df["travel_date"].astype(str)

        # 2. Financial Pricing & Margins
        cost = df["purchase_cost"].clip(lower=0.0).astype(float)
        selling = df["selling_price"].clip(lower=0.0).astype(float)

        # Canonical monetary columns
        out["purchase_cost"] = cost.round(2)
        out["selling_price"] = selling.round(2)

        # Currency-tagged aliases for prototype consistency
        out["purchase_cost_inr"] = cost.round(2)
        out["selling_price_inr"] = selling.round(2)
        out["purchase_cost_log"] = safe_log1p(cost).round(4)
        out["selling_price_log"] = safe_log1p(selling).round(4)

        # Gross margin = selling - cost
        margin = selling - cost
        out["gross_margin"] = margin.round(2)
        out["gross_margin_inr"] = margin.round(2)

        # Gross Margin Percentage = (selling - cost) / selling * 100
        out["gross_margin_percentage"] = (
            safe_divide(margin, selling, default=0.0) * 100
        ).round(2)

        # Markup Percentage = (selling - cost) / cost * 100
        out["markup_percentage"] = (
            safe_divide(margin, cost, default=0.0) * 100
        ).round(2)

        out["is_negative_margin"] = out["gross_margin"] < 0
        out["profitability_category"] = bin_series(
            out["gross_margin_percentage"],
            bins=BIN_CONFIGS["supplier_margin_pct"]["bins"],
            labels=BIN_CONFIGS["supplier_margin_pct"]["labels"],
        )

        # 3. Contractual Volume & Minimum Commitment Terms
        avail = df["available_quantity"].clip(lower=0).astype(int)
        min_qty = df["minimum_purchase_qty"].clip(lower=1).astype(int)

        out["available_quantity"] = avail
        out["minimum_purchase_qty"] = min_qty
        out["min_purchase_commitment_cost"] = (min_qty * cost).round(2)
        out["min_purchase_commitment_cost_inr"] = (min_qty * cost).round(2)
        out["requires_bulk_commitment"] = min_qty > 10

        # 4. Refundability & Validity
        out["is_refundable"] = df["refundable"].astype(bool)
        if "offer_valid_until" in df.columns:
            out["offer_valid_until"] = df["offer_valid_until"].astype(str)
            validity_days = safe_date_diff_days(df["travel_date"], df["offer_valid_until"]).fillna(0)
            out["advance_validity_days_before_travel"] = validity_days.clip(lower=0).astype(int)

        # Prototype currency metadata (noting synthetic lack of explicit ISO symbol)
        out["currency"] = "INR"
        return out
