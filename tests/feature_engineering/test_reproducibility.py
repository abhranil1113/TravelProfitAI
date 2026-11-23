"""
Tests for Feature Generation Idempotency & Reproducibility Module
"""

import pytest
import pandas as pd
from feature_engineering.hotel_features import HotelFeatureTransformer
from feature_engineering.supplier_features import SupplierFeatureTransformer


def test_transformer_reproducibility():
    sample_supplier = pd.DataFrame({
        "offer_id": ["O1", "O2"],
        "supplier_id": ["S1", "S2"],
        "inventory_id": ["INV_1", "INV_2"],
        "inventory_type": ["hotel", "flight"],
        "origin_id": ["DEL", "BOM"],
        "destination_id": ["GOA", "BLR"],
        "travel_date": ["2026-06-01", "2026-06-15"],
        "purchase_cost": [3000.0, 4500.0],
        "selling_price": [3600.0, 5000.0],
        "available_quantity": [10, 20],
        "minimum_purchase_qty": [2, 5],
        "refundable": [True, False],
        "offer_valid_until": ["2026-05-20", "2026-06-01"],
    })

    transformer = SupplierFeatureTransformer()
    res1 = transformer.transform(sample_supplier)
    res2 = transformer.transform(sample_supplier)

    pd.testing.assert_frame_equal(res1, res2)
