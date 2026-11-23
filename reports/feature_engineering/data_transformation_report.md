# TBO InventoryIQ – Data Transformation & Feature Generation Report
**Phase:** Phase 3 – Feature Engineering & Dataset Transformation  
**Status:** COMPLETE & VERIFIED  
**Author:** Team Sabuj Sangha

---

## 1. Executive Summary

The feature engineering pipeline transformed nine cleaned and validated input datasets into **seven domain-specific feature datasets** plus a unified cross-domain destination procurement indicator table.

All transformations are deterministic, vectorized, and persisted in both high-performance **Apache Parquet** and standard **CSV** formats under `data/features/`.

---

## 2. Generated Feature Datasets & Storage Register

| Dataset Canonical Name | Row Count | Feature Count | Parquet Size (MB) | CSV Size (MB) | Primary Target / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hotel_cancellation_features` | 119,208 | 54 | 2.12 MB | 29.65 MB | Operational & Modeling Feature Set |
| `flight_price_features` | 300,153 | 21 | 3.23 MB | 44.77 MB | Operational & Modeling Feature Set |
| `flight_operations_features` | 1,000 | 22 | 0.04 MB | 0.09 MB | Operational & Modeling Feature Set |
| `customer_demand_features` | 5,000 | 39 | 0.22 MB | 0.93 MB | Operational & Modeling Feature Set |
| `inventory_features` | 5,000 | 27 | 0.19 MB | 0.8 MB | Operational & Modeling Feature Set |
| `supplier_profitability_features` | 5,000 | 28 | 0.45 MB | 0.96 MB | Operational & Modeling Feature Set |
| `market_demand_features` | 5,000 | 26 | 0.08 MB | 0.67 MB | Operational & Modeling Feature Set |
| `destination_demand_supply_features` | 20 | 17 | 0.01 MB | 0.0 MB | Operational & Modeling Feature Set |


---

## 3. Key Mathematical Formulas & Definitions

### Hospitality Domain (`hotel_cancellation_features`)
- **Booking Lead Time:** `lead_time_days = arrival_date - booking_date`
- **Total Stay Nights:** `total_stay_nights = stays_in_weekend_nights + stays_in_week_nights`
- **Weekend / Weekday Ratio:** `stays_in_weekend_nights / total_stay_nights` (safe div, default 0.0)
- **ADR per Guest:** `adr / total_guests` (safe div, default 0.0)
- **Bayesian Smoothed Prior:** `(count * mean + 50 * global_mean) / (count + 50)`

### Dynamic Aviation Pricing (`flight_price_features`)
- **Advance Booking Window:** `days_left` (1 to 49 days)
- **Haul Duration:** `duration_hours` and `duration_minutes = duration_hours * 60`
- **Cabin Multiplier:** Business vs Economy binary indicator

### Inventory Availability & Depletion (`inventory_features`)
- **Occupancy Rate:** `booked_quantity / total_capacity`
- **Inventory Utilization Rate:** Synonymous with occupancy_rate under platform model.
- **Availability Rate:** `available_quantity / total_capacity`
- **Booking Velocity:** `(booked_t - booked_{t-1}) / (date_t - date_{t-1})`
- **Depletion Velocity:** `-(avail_t - avail_{t-1}) / (date_t - date_{t-1})`

### Supplier Procurement Economics (`supplier_profitability_features`)
- **Gross Margin (₹):** `selling_price - purchase_cost`
- **Gross Margin Percentage:** `((selling_price - purchase_cost) / selling_price) * 100`
- **Markup Percentage:** `((selling_price - purchase_cost) / purchase_cost) * 100`
- **Minimum Purchase Outlay:** `minimum_purchase_qty * purchase_cost`

### Cross-Domain Procurement Indicators (`destination_demand_supply_features`)
- **Demand-to-Supply Ratio:** `search_volume / (available_units + 1)`
- **Inventory Pressure Category:** Classifies destinations into Supply Constrained, High Velocity, Over-Supplied, or Balanced.
- **Procurement Candidate Score:** `0.60 * normalized_demand + 0.40 * margin_score` (0–100 scale).

---

## 4. Source Dataset Immutability Verification
All original files under `data/raw/` and `data/synthetic/` and cleaned datasets under `data/processed/` remain **100% untouched and byte-preserved**.
