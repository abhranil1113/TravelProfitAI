"""
Tests for Supplier Profitability Feature Engineering Module
Validates canonical monetary metrics, currency aliases, and profitability bounds.
"""

import pytest
import pandas as pd
from feature_engineering.supplier_features import SupplierFeatureTransformer


def test_supplier_feature_transformer():
    test_supplier = pd.DataFrame({
        "offer_id": ["O1", "O2"],
        "supplier_id": ["S10", "S20"],
        "inventory_id": ["INV_A", "INV_B"],
        "inventory_type": ["hotel", "flight"],
        "origin_id": ["DEL", "BOM"],
        "destination_id": ["GOA", "BLR"],
        "travel_date": ["2026-06-01", "2026-06-15"],
        "purchase_cost": [4000.0, 5000.0],
        "selling_price": [5000.0, 4800.0],  # O1 is profitable (1000 margin), O2 is negative margin (-200)
        "available_quantity": [50, 20],
        "minimum_purchase_qty": [5, 2],
        "refundable": [True, False],
        "offer_valid_until": ["2026-05-25", "2026-06-10"],
    })

    transformer = SupplierFeatureTransformer()
    feats = transformer.transform(test_supplier)

    assert len(feats) == 2

    # Canonical monetary columns
    assert "purchase_cost" in feats.columns
    assert "selling_price" in feats.columns
    assert "gross_margin" in feats.columns
    assert "min_purchase_commitment_cost" in feats.columns

    # Currency aliases for prototype consistency
    assert "purchase_cost_inr" in feats.columns
    assert "selling_price_inr" in feats.columns
    assert "gross_margin_inr" in feats.columns
    assert "min_purchase_commitment_cost_inr" in feats.columns

    # Margin percentages
    assert "gross_margin_percentage" in feats.columns
    assert "markup_percentage" in feats.columns
    assert "is_negative_margin" in feats.columns
    assert "profitability_category" in feats.columns

    # O1 checks: margin = 1000, margin_pct = 1000 / 5000 * 100 = 20.0%, markup = 1000 / 4000 * 100 = 25.0%
    assert feats.loc[0, "purchase_cost"] == 4000.0
    assert feats.loc[0, "selling_price"] == 5000.0
    assert feats.loc[0, "gross_margin"] == 1000.0
    assert feats.loc[0, "gross_margin_inr"] == 1000.0
    assert feats.loc[0, "gross_margin_percentage"] == 20.0
    assert feats.loc[0, "markup_percentage"] == 25.0
    assert feats.loc[0, "is_negative_margin"] == False
    assert feats.loc[0, "min_purchase_commitment_cost"] == 20000.0
    assert feats.loc[0, "min_purchase_commitment_cost_inr"] == 20000.0

    # O2 checks: negative margin
    assert feats.loc[1, "gross_margin"] == -200.0
    assert feats.loc[1, "gross_margin_inr"] == -200.0
    assert feats.loc[1, "is_negative_margin"] == True
