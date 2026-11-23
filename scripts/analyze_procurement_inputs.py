import pandas as pd
import numpy as np

def analyze_procurement_inputs():
    offers = pd.read_parquet("data/processed/supplier_offers/cleaned_supplier_offers.parquet")
    inv = pd.read_parquet("data/processed/inventory/cleaned_inventory_availability.parquet")
    searches = pd.read_parquet("data/processed/searches/cleaned_customer_search_events.parquet")
    market = pd.read_parquet("data/processed/market_signals/cleaned_market_seasonal_signals.parquet")

    print("=== SUPPLIER OFFERS STATS ===")
    print(f"Total offers: {len(offers)}")
    print(f"Inventory types:\n{offers['inventory_type'].value_counts()}")
    print(f"Suppliers count: {offers['supplier_id'].nunique()}")
    print(f"Unique inventory items: {offers['inventory_id'].nunique()}")
    print(f"Date range travel_date: {offers['travel_date'].min()} to {offers['travel_date'].max()}")
    print(f"Date range offer_valid_until: {offers['offer_valid_until'].min()} to {offers['offer_valid_until'].max()}")
    print(f"Purchase cost range: min={offers['purchase_cost'].min()}, median={offers['purchase_cost'].median()}, max={offers['purchase_cost'].max()}")
    print(f"Selling price range: min={offers['selling_price'].min()}, median={offers['selling_price'].median()}, max={offers['selling_price'].max()}")
    print(f"Available qty range: min={offers['available_quantity'].min()}, max={offers['available_quantity'].max()}")
    print(f"Min purchase qty range: min={offers['minimum_purchase_qty'].min()}, max={offers['minimum_purchase_qty'].max()}")
    print(f"Negative margin count: {offers['is_negative_margin'].sum()} / {len(offers)}")
    print(f"Refundable counts:\n{offers['refundable'].value_counts()}")

    print("\n=== INVENTORY SNAPSHOTS STATS ===")
    print(f"Total inventory records: {len(inv)}")
    print(f"Unique inventory_id in availability: {inv['inventory_id'].nunique()}")
    print(f"Unique snapshots: {inv['snapshot_id'].nunique()}")
    print(f"Date range snapshot_date: {inv['snapshot_date'].min()} to {inv['snapshot_date'].max()}")
    print(f"Snapshots per (inventory_id, travel_date): min={inv.groupby(['inventory_id', 'travel_date']).size().min()}, max={inv.groupby(['inventory_id', 'travel_date']).size().max()}")

    print("\n=== OFFERS & INVENTORY OVERLAP ===")
    overlap_inv = set(offers["inventory_id"]).intersection(set(inv["inventory_id"]))
    print(f"Offers inventory_ids in availability: {len(overlap_inv)} / {offers['inventory_id'].nunique()}")

if __name__ == "__main__":
    analyze_procurement_inputs()
