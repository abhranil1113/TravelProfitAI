import json
import os
import joblib
import pandas as pd
import numpy as np

def run_empirical_audit():
    print("=" * 70)
    print("1. HOTEL CANCELLATION MODEL DEEP INSPECTION")
    print("=" * 70)
    model_dir = "data/models/hotel_cancellation"
    with open(os.path.join(model_dir, "metadata.json")) as f:
        meta = json.load(f)
    print("Task:", meta.get("task_name"))
    print("Model:", meta.get("model_name"))
    print("Features count:", len(meta.get("feature_names", [])))
    print("Feature list:\n", meta.get("feature_names", []))
    
    prep = joblib.load(os.path.join(model_dir, "preprocessor.joblib"))
    print("\nPreprocessor type:", type(prep))
    if hasattr(prep, "named_transformers_"):
        print("Transformers:", list(prep.named_transformers_.keys()))
        for t_name, trans in prep.named_transformers_.items():
            print(f"  Transformer '{t_name}': {type(trans)}")
            if hasattr(trans, "categories_"):
                print(f"    Categories for {t_name}: {[list(c)[:5] for c in trans.categories_]}")

    est = joblib.load(os.path.join(model_dir, "estimator.joblib"))
    print("\nEstimator type:", type(est))
    if hasattr(est, "classes_"):
        print("Classes:", est.classes_)

    print("\n" + "=" * 70)
    print("2. SEARCH EVENTS SCHEMA & CONVERSION FIELDS")
    print("=" * 70)
    searches = pd.read_parquet("data/processed/searches/cleaned_customer_search_events.parquet")
    print("Search events shape:", searches.shape)
    print("Columns:", list(searches.columns))
    print("\nSample values:")
    print(searches[["search_date", "travel_date", "destination_id", "inventory_type", "travellers_count", "rooms_count", "clicked", "booking_completed"]].head(5))
    print("\nConversion rate overall:")
    print(searches.groupby("inventory_type")["booking_completed"].agg(["count", "sum", "mean"]))
    print("\nIs stay duration or checkout date present in search events?")
    print("Columns with 'night' or 'stay' or 'checkout':", [c for c in searches.columns if any(w in c.lower() for w in ['night', 'stay', 'checkout', 'duration'])])

    print("\n" + "=" * 70)
    print("3. INVENTORY ID & SUPPLIER RELATIONSHIPS (SHARED STOCK POOLS)")
    print("=" * 70)
    offers = pd.read_parquet("data/processed/supplier_offers/cleaned_supplier_offers.parquet")
    inv = pd.read_parquet("data/processed/inventory/cleaned_inventory_availability.parquet")
    print("Offers shape:", offers.shape)
    print("Unique offers:", offers["offer_id"].nunique())
    print("Unique inventory_ids in offers:", offers["inventory_id"].nunique())
    print("Unique supplier_ids in offers:", offers["supplier_id"].nunique())
    print("Suppliers by inventory type:")
    for itype, grp in offers.groupby("inventory_type"):
        print(f"  {itype}: suppliers={sorted(grp['supplier_id'].unique())}, count={grp['supplier_id'].nunique()}")

    # Check if multiple suppliers offer the same inventory_id on the same travel_date
    supp_per_inv_date = offers.groupby(["inventory_id", "travel_date"])["supplier_id"].nunique()
    print("\nSuppliers per (inventory_id, travel_date):")
    print("  Min:", supp_per_inv_date.min(), "Max:", supp_per_inv_date.max(), "Mean:", supp_per_inv_date.mean())
    multi_supp_same_inv = supp_per_inv_date[supp_per_inv_date > 1]
    print(f"Number of (inventory_id, travel_date) pairs with >1 supplier: {len(multi_supp_same_inv)} / {len(supp_per_inv_date)}")

    # Check if multiple offers exist for the same (inventory_id, travel_date)
    offers_per_inv_date = offers.groupby(["inventory_id", "travel_date"]).size()
    print("Offers per (inventory_id, travel_date):")
    print("  Min:", offers_per_inv_date.min(), "Max:", offers_per_inv_date.max())
    print(f"Number of (inventory_id, travel_date) pairs with >1 offer: {(offers_per_inv_date > 1).sum()} / {len(offers_per_inv_date)}")

    # Check inventory_availability relationships
    print("\nInventory availability table:")
    print("Unique inventory_ids in inv_avail:", inv["inventory_id"].nunique())
    print("Unique supplier_ids in inv_avail:", inv["supplier_id"].nunique())
    # Does each inventory_id belong to a single supplier or multiple in inv_avail?
    supp_per_inv_in_avail = inv.groupby("inventory_id")["supplier_id"].nunique()
    print("Suppliers per inventory_id in inventory_availability:")
    print("  Min:", supp_per_inv_in_avail.min(), "Max:", supp_per_inv_in_avail.max())
    print(f"Inventory IDs with multiple suppliers in availability table: {(supp_per_inv_in_avail > 1).sum()} / {len(supp_per_inv_in_avail)}")

    # Check total capacity vs available quantity in inv_avail
    sample_item = inv.iloc[0]["inventory_id"]
    sample_date = inv.iloc[0]["travel_date"]
    print(f"\nSnapshots for sample item {sample_item} on travel_date {sample_date}:")
    print(inv[(inv["inventory_id"] == sample_item) & (inv["travel_date"] == sample_date)][["snapshot_id", "snapshot_date", "travel_date", "total_capacity", "booked_quantity", "available_quantity", "supplier_id"]])

if __name__ == "__main__":
    run_empirical_audit()
