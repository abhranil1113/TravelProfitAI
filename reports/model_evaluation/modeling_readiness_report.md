# TBO InventoryIQ — Modeling Readiness & Dataset Eligibility Assessment
**AI-Powered Travel Inventory & Profit Optimization Platform**  
**Phase:** Phase 4 — Machine Learning Development, Cross-Validation, Benchmarking & Model Selection  
**Date:** November 23, 2026  
**Authors:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)  
**Status:** COMPLETE AUDIT

---

## Executive Summary

Before implementing model architectures or training algorithms, a comprehensive modeling-readiness audit was conducted across all eight feature datasets generated in Phase 3. 

Each dataset was evaluated against mathematical validity, target availability, temporal horizon, feature observability at prediction cutoff, potential target leakage, and business utility.

| Dataset Name | Primary Purpose / Proposed Task | Target Variable | Proposed Split | Eligibility Status |
| :--- | :--- | :--- | :--- | :--- |
| `hotel_cancellation_features` | Pre-arrival booking cancellation risk | `is_canceled` | Stratified 5-Fold + Booking Date Stream | **ELIGIBLE** |
| `flight_price_features` | Dynamic quote price regression | `price` | 5-Fold CV + Advance Booking Horizon | **ELIGIBLE** |
| `customer_demand_features` | Multi-horizon search demand forecasting | `future_search_volume_7d` | TimeSeriesSplit (5 folds, 7d embargo) | **ELIGIBLE (with Panel Aggregation)** |
| `inventory_features` | Available capacity & stockout forecasting | `future_available_quantity` | TimeSeriesSplit (5 folds on snapshot stream) | **ELIGIBLE (with Target Construction)** |
| `flight_operations_features` | Delay & cancellation operational modeling | `arrival_delay_minutes` | Chronological Flight Time | **CONDITIONALLY ELIGIBLE (Prototype Only)** |
| `supplier_profitability_features` | Procurement margin & terms analytics | N/A (Circular target) | N/A | **NOT ELIGIBLE FOR DIRECT ML (Decision Support)** |
| `market_demand_features` | Macro seasonal index & weather signals | N/A (Synthetic score) | N/A | **NOT ELIGIBLE AS STANDALONE TARGET (Feature Store)** |
| `destination_demand_supply_features`| Cross-domain inventory pressure index | N/A (Analytical ratio) | N/A | **NOT ELIGIBLE FOR ML (Phase 5 Solver Input)** |

---

## 1. Hotel Cancellation Features (`hotel_cancellation_features.parquet`)

### 1.1 Dataset Diagnostics
- **File Path:** `data/features/hotel/hotel_cancellation_features.parquet`
- **Format:** Apache Parquet (with CSV companion)
- **Shape:** 119,208 records $\times$ 54 features (2.12 MB Parquet, 29.65 MB CSV)
- **Missing Values:** 0 null cells (100% complete)
- **Infinite Values:** 0 infinite cells
- **Target Variable:** `is_canceled` (Binary: 0 = not canceled, 1 = canceled)
- **Target Distribution:**
  - Class 0 (Completed / Checked Out): 75,166 records (63.05%)
  - Class 1 (Canceled / No-Show): 44,042 records (36.95%)
  - Imbalance Ratio: 1.71 : 1 (Moderate class balance; stratification required)

### 1.2 Target Leakage & Pre-Booking Cutoff Enforcement
Prediction cutoff is defined as **Booking Creation Time ($t_{\text{booking}}$)**.

- **Pre-Booking Predictors (APPROVED):**
  - Customer lead time: `lead_time_days`, `lead_time_bucket`, `lead_time_log`
  - Planned stay duration: `total_stay_nights`, `stays_in_weekend_nights`, `stays_in_week_nights`, `weekend_nights_ratio`
  - Party composition: `total_guests`, `adults`, `children`, `babies`, `is_solo_traveller`, `is_family_booking`
  - Historical loyalty: `is_repeated_guest`, `previous_cancellations`, `previous_bookings_not_canceled`, `has_cancellation_history`
  - Special requirements: `special_requests_count`, `has_special_requests`, `required_car_parking_spaces`
  - Customer attributes: `customer_type`, `deposit_type`, `market_segment`, `distribution_channel`, `country`, `hotel`
  - Contracted pricing: `adr`, `adr_log`, `adr_per_guest`
  - Historical benchmarks: `market_segment_historical_cancel_rate`, `deposit_type_historical_cancel_rate`
- **Quarantined Operational Features (EXCLUDED from pre-booking predictors):**
  - `reservation_status` & `reservation_status_date`: Direct target outcome leakage (checkout/cancellation dates).
  - `assigned_room_type` & `room_type_changed`: Assigned by hotel front desk at check-in or day-of-arrival room allocation. Unavailable at reservation time.
  - `booking_changes`: Post-booking modifications between booking and arrival. Excluded from Day-0 initial reservation models.
- **Synthesized Booking Timestamp:**
  - $\text{booking\_date} = \text{arrival\_date} - \text{lead\_time\_days}$ (reconstructed from arrival date and lead time, documented as an assumption, spanning 2013-06-24 to 2017-08-31).

### 1.3 Eligibility Verdict
**STATUS: ELIGIBLE**  
Supports supervised binary classification using `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` alongside chronological holdout validation.

---

## 2. Flight Price Features (`flight_price_features.parquet`)

### 2.1 Dataset Diagnostics
- **File Path:** `data/features/flight_prices/flight_price_features.parquet`
- **Shape:** 300,153 records $\times$ 21 features (3.23 MB Parquet, 44.77 MB CSV)
- **Missing Values:** 0 null cells
- **Infinite Values:** 0 infinite cells
- **Target Variable:** `price` (Continuous positive INR ₹)
- **Target Distribution:**
  - Minimum: ₹1,105.00
  - 25th Percentile: ₹4,783.00
  - Median: ₹7,425.00
  - Mean: ₹20,889.66
  - 75th Percentile: ₹42,521.00
  - Maximum: ₹123,071.00
  - Skewness: Bimodal distribution reflecting Economy Class (mean ~₹6,572) vs Business Class (mean ~₹52,540).

### 2.2 Leakage & Predictor Integrity
- **Prediction Cutoff:** Flight Search / Quote Time ($t_{\text{quote}}$).
- **Approved Predictors:** `days_left`, `duration_hours`, `class`, `is_business_class`, `stops_count`, `is_direct_flight`, `airline`, `source_city`, `destination_city`, `route`, `departure_time`, `arrival_time`.
- **Excluded Features:**
  - `price_log`: Strictly excluded from predictor matrix (mathematical transformation of target).
  - `price_record_id`: Row identifier (memorization risk).
  - `currency`: Constant column (`"INR"`).
- **Temporal Nature:** No calendar observation timestamps exist in the Kaggle dataset. Formally modeled as a **Scenario-Based Horizon Split** (`days_left >= 15` advance booking vs `8-14` intermediate vs `1-7` immediate departure).

### 2.3 Eligibility Verdict
**STATUS: ELIGIBLE**  
Supports supervised regression using `KFold(n_splits=5, shuffle=True, random_state=42)` and horizon-stratified validation.

---

## 3. Customer Demand Features (`customer_demand_features.parquet`)

### 3.1 Dataset Diagnostics & Grain
- **File Path:** `data/features/customer_demand/customer_demand_features.parquet`
- **Shape:** 5,000 search event records $\times$ 39 features (0.22 MB Parquet, 0.93 MB CSV)
- **Current Grain:** Individual search event (`search_id`, `user_id`, `destination_id`, `inventory_type`, `search_date`).
- **Date Range:** `search_date` from `2025-09-12` to `2027-05-11` (607 days).
- **Current Target State:** `search_volume` does not exist at individual row level (every row is 1 event).

### 3.2 Required Transformation: Time-Series Panel Aggregation
To support genuine time-series demand forecasting:
1. Aggregate search events into a regular panel:
   $$\text{Grain} = \big[\text{destination\_id},\, \text{inventory\_type},\, \text{date}\big]$$
2. Compute `daily_search_volume` and fill zero-activity days.
3. Construct engineered lag features: `lag_1`, `lag_7`, `lag_14`, rolling means (`rolling_7d`, `rolling_14d`, `rolling_28d`).
4. Construct future demand target at a documented forecast horizon:
   $$\text{Target} = \text{future\_search\_volume\_7d} = \text{shift}(-7)$$
5. **Leakage Quarantine:** Exclude post-search funnel conversions (`clicked`, `booking_completed`, `has_funnel_anomaly`) from demand forecasting inputs.

### 3.3 Eligibility Verdict
**STATUS: ELIGIBLE (with Panel Aggregation)**  
Supports time-series supervised regression using `TimeSeriesSplit(n_splits=5)` with an embargo gap of 7 days to prevent target window overlap.

---

## 4. Inventory Availability Features (`inventory_features.parquet`)

### 4.1 Dataset Diagnostics & Snapshot Structure
- **File Path:** `data/features/inventory/inventory_features.parquet`
- **Shape:** 5,000 snapshot records $\times$ 27 features (0.19 MB Parquet, 0.80 MB CSV)
- **Grain:** Multi-temporal observation snapshots per `(inventory_id, travel_date)`.
- **Snapshot Counts:** 16 to 48 sequential observations per inventory item tracking depletion from 90 days out down to 1 day before departure.
- **Physical Units:** Hotel room nights (`ROOM_NIGHT`) and flight seats (`SEAT`).

### 4.2 Target Construction & Stockout Definition
- **Forecast Target:** `future_available_quantity` (available units observed at next temporal snapshot $t+1$).
- **Prediction Cutoff:** Snapshot observation date ($t_{\text{snapshot}}$). Future snapshot rows are strictly masked.
- **Stockout Definition:** An inventory item is defined as entering a critical stockout state when bookable units drop to or below the safety threshold:
  $$\text{Stockout Threshold} = 5 \text{ units}$$
  $$\text{Actual Stockout} = \mathbb{I}(\text{future\_available\_quantity} \le 5)$$
  $$\text{Predicted Stockout} = \mathbb{I}(\widehat{\text{future\_available\_quantity}} \le 5)$$

### 4.3 Eligibility Verdict
**STATUS: ELIGIBLE (with Target Construction)**  
Supports time-series supervised regression and stockout detection recall evaluation using `TimeSeriesSplit(n_splits=5)` grouped by inventory item.

---

## 5. Flight Operations Features (`flight_operations_features.parquet`)

### 5.1 Dataset Diagnostics
- **File Path:** `data/features/flights/flight_operations_features.parquet`
- **Shape:** 1,000 development sample records $\times$ 22 features (0.04 MB Parquet, 0.09 MB CSV)
- **Scope:** Chronological head slice (January 1, 2015) from the 5,819,079-record US DOT dataset.
- **Target Variables Available:** `arrival_delay_minutes`, `is_ontime_arrival`, `is_cancelled`.

### 5.2 Modeling Assessment & Scope Limitations
- The 1,000 records represent only a 1-day slice of winter operations (Jan 1, 2015), introducing severe seasonal and weather bias.
- Post-departure telemetry (`DEPARTURE_TIME`, `WHEELS_OFF`, `AIR_TIME`, `TAXI_IN`, etc.) cannot be used to predict delays prior to takeoff.
- Running full-scale 5.8M training is constrained by local RAM (~1.2 GB raw, ~3 GB pipeline).

### 5.3 Eligibility Verdict
**STATUS: CONDITIONALLY ELIGIBLE (Prototype Benchmark Only)**  
Suitable as a prototype test fixture for flight delay regression, but marked as non-production until full 5.8M multi-season data is processed in a high-memory cluster.

---

## 6. Supplier Profitability Features (`supplier_profitability_features.parquet`)

### 6.1 Dataset Diagnostics & Formula Audit
- **File Path:** `data/features/supplier/supplier_profitability_features.parquet`
- **Shape:** 5,000 records $\times$ 28 features (0.45 MB Parquet, 0.96 MB CSV)
- **Columns:** `purchase_cost`, `selling_price`, `gross_margin`, `gross_margin_percentage`, `markup_percentage`, `available_quantity`, `minimum_purchase_qty`.

### 6.2 Target Circularity Defect
- In this dataset, `gross_margin` is deterministically computed as:
  $$\text{gross\_margin} = \text{selling\_price} - \text{purchase\_cost}$$
  $$\text{gross\_margin\_percentage} = \frac{\text{selling\_price} - \text{purchase\_cost}}{\text{selling\_price}} \times 100$$
- Training a machine learning model to predict `gross_margin` or `gross_margin_percentage` when `purchase_cost` and `selling_price` are known inputs is a circular identity ($R^2 = 1.0$), not predictive modeling.
- Real-world supplier prediction requires future realized outcomes (e.g., supplier fulfillment rate, dispute rate, refund frequency, or realized commission settlement). These future outcomes do not exist in the static contract table.

### 6.3 Eligibility Verdict
**STATUS: NOT ELIGIBLE FOR DIRECT SUPERVISED ML**  
Classified as **Business Intelligence & Procurement Decision Support**. Utilized in Phase 5 Optimization as contractual cost inputs, not as a supervised ML target.

---

## 7. Market Demand Signals (`market_demand_features.parquet`)

### 7.1 Dataset Diagnostics
- **File Path:** `data/features/market/market_demand_features.parquet`
- **Shape:** 5,000 records $\times$ 26 features (0.08 MB Parquet, 0.67 MB CSV)
- **Columns:** `demand_index`, `demand_index_scaled_100`, `composite_seasonal_demand_score`, `holiday_indicator`, `temperature_celsius`, `rainfall_mm`.

### 7.2 Modeling Assessment
- The composite demand score is a heuristic formula constructed in Phase 3. Training an ML model to predict this score is predicting a synthetic formula.
- Its genuine value is as an **enrichment feature store** (weather and holiday indicators) for customer demand and flight price models, not as an independent supervised target.

### 7.3 Eligibility Verdict
**STATUS: NOT ELIGIBLE AS STANDALONE TARGET (Feature Store Enrichment Only)**

---

## 8. Destination Demand & Supply Indicators (`destination_demand_supply_features.parquet`)

### 8.1 Dataset Diagnostics
- **File Path:** `data/features/market/destination_demand_supply_features.parquet`
- **Shape:** 20 records $\times$ 17 features (10 destinations $\times$ 2 inventory types: `HOTEL` and `FLIGHT`).
- **Columns:** `search_volume`, `available_units`, `demand_to_supply_ratio`, `procurement_candidate_score`.

### 8.2 Modeling Assessment
- A 20-row summary table lacks the statistical sample size ($N=20$) for cross-validation or ML training.
- The `demand_to_supply_ratio` is an analytical pressure index designed specifically as constraint inputs for Phase 5 knapsack optimization.

### 8.3 Eligibility Verdict
**STATUS: NOT ELIGIBLE FOR ML (Phase 5 Mathematical Optimization Input)**

---

## 9. Final Phase 4 Modeling Scope

Based on rigorous data readiness analysis, Phase 4 will develop, benchmark, cross-validate, and persist models for the **four genuinely eligible travel prediction tasks**:

1. **Hotel Booking Cancellation Prediction** (`hotel_cancellation_features`) — Binary Classification
2. **Flight Quote Price Prediction** (`flight_price_features`) — Supervised Regression
3. **Customer Search Demand Forecasting** (`customer_demand_features` panel) — Time-Series Panel Regression
4. **Inventory Availability & Stockout Forecasting** (`inventory_features` stream) — Multi-Horizon Time-Series Regression

All four tasks will run through the extensible ML registry and framework, utilizing **Baselines (Dummy/Linear/Naive)**, **Random Forest**, **XGBoost**, and **LightGBM**, evaluated under task-specific cross-validation protocols.
