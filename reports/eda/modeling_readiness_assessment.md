# TBO InventoryIQ – Machine Learning Modeling Readiness Assessment
**Phase:** Phase 2 – Modeling Feasibility Audit & Leakage Boundary Specification  
**Author:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)  
**Strict Mandate:** Audit and evaluate candidate future models only. NO ML training is performed in Phase 2.

---

## 1. Executive Modeling Assessment Matrix

| Model ID | Candidate Model Name | Target Variable | Problem Formulation | Primary Dataset(s) | Readiness Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Model 1** | Hotel Booking Cancellation Predictor | `is_canceled` | Binary Classification | `hotel_bookings` (119k rows) | **READY** |
| **Model 2** | Dynamic Flight Price Regressor | `price` | Supervised Regression | `flight_prices` (300k rows) | **READY** |
| **Model 3** | Destination Search Demand Forecaster | `search_volume` | Time Series / Count Regression | `customer_search_events` & `market_signals` | **CONDITIONALLY READY** |
| **Model 4** | Inventory Depletion & Stockout Velocity | `available_quantity` / `sold_out` | Survival / Regression | `inventory_availability` (snapshots) | **CONDITIONALLY READY** |
| **Model 5** | Supplier Price Competitiveness & Profit Ranker | `margin_percentage` | Ranking / Regression | `supplier_offers` | **READY** |

---

## 2. Detailed Candidate Model Audits

### Model 1: Hotel Booking Cancellation Predictor
- **Target:** `is_canceled` (0 = Check-Out, 1 = Canceled). Class balance: ~63% non-canceled, ~37% canceled.
- **Allowed Pre-Booking Features:** `lead_time`, `arrival_date_month`, `stays_in_weekend_nights`, `stays_in_week_nights`, `adults`, `children`, `meal`, `country`, `market_segment`, `distribution_channel`, `is_repeated_guest`, `previous_cancellations`, `deposit_type`, `customer_type`, `adr`.
- **Target Leakage Traps to FORBID:**
  - `reservation_status` (Directly contains "Canceled" / "Check-Out").
  - `reservation_status_date` (Recorded on or after the cancellation event).
- **Readiness Decision:** **READY**. Dataset has 119k clean, validated rows with strong predictive signal and zero data leakage when post-event fields are excluded.

---

### Model 2: Dynamic Flight Price Regressor
- **Target:** `price` in INR (₹). Range: ₹1,105 to ₹123,071.
- **Allowed Predictive Features:** `airline`, `source_city`, `departure_time`, `stops_count`, `arrival_time`, `destination_city`, `class`, `duration`, `days_left`, `route`.
- **Target Leakage Traps:** None. Price is the commercial quote observed at search time.
- **Readiness Decision:** **READY**. 300,153 validated rows; highly rich feature space capturing both cabin class and the days_left yield curve.

---

### Model 3: Destination Search Demand Forecaster
- **Target:** `search_volume` per destination/date.
- **Candidate Features:** `destination_id`, `season_type`, `month`, `holiday_indicator`, `festival_indicator`, `temperature`, `rainfall_mm`, `demand_index`.
- **Target Leakage Traps:**
  - `clicked` and `booking_completed` are search outcomes and cannot predict search demand.
- **Readiness Decision:** **CONDITIONALLY READY**. Requires aggregation from search transaction events into daily/weekly destination time-series panel data before training.

---

### Model 4: Inventory Depletion & Stockout Velocity
- **Target:** `available_quantity` depletion rate or `sold_out` probability.
- **Candidate Features:** `inventory_type`, `destination_id`, `days_to_travel`, `total_capacity`, `booked_quantity_lag`.
- **Target Leakage Traps:** Must strictly avoid looking ahead across future snapshot dates. Only past snapshots relative to `snapshot_date` may be used.
- **Readiness Decision:** **CONDITIONALLY READY**. Requires panel feature engineering to construct lag depletion rates from temporal snapshot sequences.

---

### Model 5: Supplier Price Competitiveness & Profit Ranker
- **Target:** `margin_percentage` or `purchase_cost`.
- **Allowed Predictive Features:** `supplier_id`, `inventory_type`, `destination_id`, `minimum_purchase_qty`, `refundable`, `travel_date_month`.
- **Target Leakage Traps:** Do not use `selling_price` if predicting purchase cost, as it introduces circular margin identity.
- **Readiness Decision:** **READY**. 5,000 clean supplier offers with validated purchase costs and margins.

---

## 3. Modeling Guardrails for Phase 3
1. **Never combine EUR and INR targets into a single joint regression model.**
2. **Never train on raw snapshot sequences without temporal grouping.**
3. **Strictly prune post-event leakage features during feature engineering.**
