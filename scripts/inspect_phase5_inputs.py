import json
import glob
import os
import pandas as pd

def main():
    print("=== CHAMPION MODEL METADATA ===")
    for m_path in sorted(glob.glob("data/models/*/metadata.json")):
        with open(m_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        task_name = meta.get("task", os.path.basename(os.path.dirname(m_path)))
        champ = meta.get("model_name", meta.get("champion_model", "unknown"))
        target = meta.get("target", "unknown")
        feats = meta.get("feature_names", [])
        print(f"Task: {task_name}")
        print(f"  Model Name: {champ}")
        print(f"  Target: {target}")
        print(f"  Features count: {len(feats)}")
        print(f"  Sample features: {feats[:5]}")
        print(f"  Metrics: {meta.get('metrics', meta.get('cv_metrics', {}))}")
        print()

    print("=== PROCESSED DATASETS SUMMARY ===")
    processed_paths = [
        "data/processed/supplier_offers/cleaned_supplier_offers.parquet",
        "data/processed/inventory/cleaned_inventory_availability.parquet",
        "data/processed/searches/cleaned_customer_search_events.parquet",
        "data/processed/market_signals/cleaned_market_seasonal_signals.parquet",
        "data/processed/hotel_bookings/cleaned_hotel_bookings.parquet",
        "data/processed/flight_prices/cleaned_flight_prices.parquet",
    ]
    for p in processed_paths:
        if os.path.exists(p):
            df = pd.read_parquet(p)
            print(f"File: {os.path.basename(p)}")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)}")
            print(f"  Dtypes: {dict(df.dtypes.iloc[:6])}")
            if "currency" in df.columns:
                print(f"  Currencies: {df['currency'].value_counts().to_dict()}")
            if "inventory_type" in df.columns:
                print(f"  Inventory Types: {df['inventory_type'].value_counts().to_dict()}")
            if "destination_id" in df.columns:
                print(f"  Unique Destinations: {df['destination_id'].nunique()}")
            print()

    print("=== FEATURE DATASETS SUMMARY ===")
    feature_paths = sorted(glob.glob("data/features/*/*.parquet"))
    for p in feature_paths:
        df = pd.read_parquet(p)
        print(f"Feature Table: {os.path.basename(p)}")
        print(f"  Shape: {df.shape}")
        print(f"  Columns ({len(df.columns)}): {list(df.columns)[:8]}...")
        print()

if __name__ == "__main__":
    main()
