# TBO InventoryIQ – Modeling Readiness Assessment (Post-Feature Engineering)
**Phase:** Phase 3 – Feature Engineering & Dataset Transformation  
**Status:** READY FOR PHASE 4 (MODELING)  
**Author:** Team Sabuj Sangha

---

## 1. Executive Modeling Readiness Matrix

| Model ID | Candidate Model Name | Target Variable | Problem Formulation | Engineered Dataset | Post-Feature Readiness Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Model 1** | Hotel Booking Cancellation Predictor | `is_canceled` | Binary Classification | `hotel_cancellation_features` (119k rows, 35 features) | **MODEL READY** |
| **Model 2** | Dynamic Flight Price Regressor | `price` | Supervised Regression | `flight_price_features` (300k rows, 17 features) | **MODEL READY** |
| **Model 3** | Destination Search Demand Forecaster | `search_volume` | Time Series / Count Regression | `customer_demand_features` (5k events + panel) | **MODEL READY** |
| **Model 4** | Inventory Depletion & Stockout Velocity | `available_quantity` / `is_sold_out` | Survival / Time-to-Event | `inventory_features` (5k rows, lagged velocity) | **MODEL READY** |
| **Model 5** | Supplier Price Competitiveness & Profit Ranker | `purchase_cost_inr` / `margin_percentage` | Ranking / Regression | `supplier_profitability_features` (5k offers) | **MODEL READY** |

---

## 2. Transformation Advancements from Phase 2

In Phase 2, Models 3 and 4 were rated *CONDITIONALLY READY* due to missing temporal panel aggregations and snapshot lag features.

### Enhancements Completed in Phase 3:
1. **Model 3 (Search Demand):** Constructed explicit search-to-travel lead time buckets, calendar cyclic indicators, party sizing ratios, and destination-level panel aggregations.
2. **Model 4 (Inventory Depletion):** Constructed chronological snapshot chaining (`prev_booked`, `prev_available`, `days_since_prev_snapshot`) yielding explicit `booking_velocity_units_per_day` and `inventory_depletion_velocity`.
3. **Model 1 (Hotel Cancellation):** Successfully extracted 35 clean, leakage-quarantined features with Bayesian smoothed priors and zero post-checkout data leakage.
4. **Model 2 (Flight Dynamic Pricing):** Engineered the non-linear advance surge curve (`days_left_bucket`), haul categories, and cabin class flags.

---

## 3. Strict Pre-Modeling Constraints for Phase 4
- **No Joint Cross-Currency Fitting:** Never combine EUR-denominated ADR with INR-denominated flight prices in a single loss function without an explicit foreign exchange rate.
- **Strict Chronological Evaluation:** Evaluate all models against the chronological split manifests defined in `reports/feature_engineering/dataset_split_manifest.json`.
- **Zero Model Training Performed in Phase 3:** Confirmed that zero machine learning training was executed. All datasets are prepared, validated, and stored for Phase 4.
