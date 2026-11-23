# TBO InventoryIQ – Comprehensive Data Quality & Validation Audit Report

**Audit Stage**: Second-Level Engineering Audit & Quality Reconciliation  
**Status**: Verified with Documented Caveats & Quality Controls  
**Total Ingested Datasets Evaluated**: 9  

## 1. Issues Discovered During Audit

1. **Hotel Bookings Accounting Reversal**: Exactly 1 reservation had a negative Average Daily Rate (`adr = -6.38`), representing an erroneous credit adjustment.
2. **Hotel Bookings Extreme Outlier**: Exactly 1 reservation recorded an extreme rate of `adr = 5400.0` (while 99% of reservations have ADR < $250).
3. **Hotel Bookings Zero Occupancy**: Exactly 180 reservation entries had `adults == 0 and children == 0 and babies == 0` (phantom bookings without occupants).
4. **Hotel Bookings Duplicate Feature Copies**: 31,994 records share identical values across all 32 columns. Without a unique booking confirmation ID, these may represent either duplicate scrapes/transfers or multiple independent bookings for identical rooms (e.g. tour groups).
5. **Flight Prices Redundant Quotes**: In `Flight Price Prediction.csv`, while 102,637 rows share an 8-column subset, across ALL feature columns (including duration and stops), there are 0 exact duplicates; distinct rows represent itineraries with varying transit durations.
6. **US DOT Airport Identifier Format Shift**: In late 2015, the US DOT reporting switched from 3-letter IATA codes (`JFK`, `LAX`) to 5-digit FAA numeric identifiers (`10135`, `10140`), causing unmapped lookups against `airports.csv`.
7. **Multi-Currency Environment**: Datasets span heterogeneous currencies: Hotel Bookings is in **EUR (€)**, Flight Prices, Supplier Offers, and Customer Searches are in **INR (₹)**, and US Flights contains operational distance/delay units without monetary values.

## 2. Corrections Made in Data Pipeline

- **Mathematical Reconciliation of Zero-Occupancy Discrepancy**:
  - Total zero-guest records in raw hotel bookings: **180**
  - Zero-guest records intersecting with exact feature duplicates: **14**
  - Zero-guest records in unique feature sets: **166**
  - Formula verified: `180 total - 14 duplicate = 166 unique`.
- **Duplicate Handling Policy Reassessed**:
  - Preserved all 300,153 flight price records; stopped aggressive subset deletion that was dropping alternative flight transit options.
  - Added non-destructive tracking flags (`is_duplicate_feature_copy`, `is_zero_occupancy`, `is_negative_adr`) allowing downstream consumers to filter or analyze as appropriate.
- **Funnel Integrity Policy**:
  - Avoided destructive mutation of observed `clicked` values. Created `has_funnel_anomaly` diagnostic flag instead.
- **Missing Value Imputation**:
  - Imputed missing hotel children count (4 rows) to 0; imputed missing guest country (488 rows) to `'Unknown'`.
  - Preserved legitimate nulls for hotel `origin_id` (hotels are stationary) and flight search `rooms_count`.

## 3. Issues That Remain Unresolved & Documented Limitations

- **Lack of Unique Booking Transaction Key in Public Data**: `hotel_bookings.csv` lacks a PNR or transaction ID. We cannot definitively prove whether 31,994 identical rows are system double-entries or legitimate group room allotments. They are flagged rather than silently purged.
- **Airport Code Crosswalk Table**: 306 US DOT 5-digit airport codes in late-2015 `flights.csv` require an external BTS FAA crosswalk table to translate into 3-letter IATA names.
- **Cross-Domain Currency Boundary**: Hotel ADR (EUR) cannot be combined with Flight Prices (INR) without a documented foreign exchange rate (e.g. 1 EUR ≈ 90 INR).

## 4. Raw Versus Cleaned Dataset Statistics

| Dataset Name | Raw Rows | Cleaned Rows | Rows Filtered | Retention % | Primary Identifier | Currency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `market_seasonal_signals` | 5,000 | 5,000 | 0 | 100.0% | `market_seasonal_signals` | N/A |
| `inventory_availability` | 5,000 | 5,000 | 0 | 100.0% | `inventory_availability` | N/A |
| `supplier_offers` | 5,000 | 5,000 | 0 | 100.0% | `supplier_offers` | INR |
| `customer_search_events` | 5,000 | 5,000 | 0 | 100.0% | `customer_search_events` | INR |
| `airlines` | 14 | 14 | 0 | 100.0% | `airlines` | N/A |
| `airports` | 322 | 322 | 0 | 100.0% | `airports` | N/A |
| `flights` | 1,000 | 1,000 | 0 | 100.0% | `flights` | N/A |
| `flight_prices` | 300,153 | 300,153 | 0 | 100.0% | `flight_prices` | INR |
| `hotel_bookings` | 119,390 | 119,208 | 182 | 99.85% | `hotel_bookings` | EUR |


## 5. Missing Value Analysis (Exact Formula: (missing_count / total_rows) * 100)

| Stage | Dataset | Column | Missing Count | Missing % | Status | Business Justification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw` | `inventory_availability` | `origin_id` | 2,656 | 53.12% | Legitimate Nullable | Hotels are stationary destination-only inventory and do not possess an origin location. |
| `raw` | `supplier_offers` | `origin_id` | 2,750 | 55.0% | Legitimate Nullable | Hotel supply offers apply to destination properties and do not have an origin. |
| `raw` | `customer_search_events` | `rooms_count` | 2,279 | 45.58% | Legitimate Nullable | Flight searches do not require or specify hotel room counts. |
| `raw` | `airports` | `LATITUDE` | 3 | 0.9317% | Legitimate Nullable | Geographical coordinates unrecorded for select remote landing strips. |
| `raw` | `airports` | `LONGITUDE` | 3 | 0.9317% | Legitimate Nullable | Geographical coordinates unrecorded for select remote landing strips. |
| `raw` | `flights` | `TAIL_NUMBER` | 2 | 0.2% | Legitimate Nullable | Unassigned tail number for cancelled flights. |
| `raw` | `flights` | `DEPARTURE_TIME` | 84 | 8.4% | Legitimate Nullable | Flight cancelled before pushback. |
| `raw` | `flights` | `DEPARTURE_DELAY` | 84 | 8.4% | Legitimate Nullable | Flight cancelled before departure. |
| `raw` | `flights` | `TAXI_OUT` | 84 | 8.4% | Legitimate Nullable | Flight cancelled before taxiing. |
| `raw` | `flights` | `WHEELS_OFF` | 84 | 8.4% | Legitimate Nullable | Flight cancelled prior to takeoff. |
| `raw` | `flights` | `ELAPSED_TIME` | 85 | 8.5% | Legitimate Nullable | Flight cancelled or diverted before completion. |
| `raw` | `flights` | `AIR_TIME` | 85 | 8.5% | Legitimate Nullable | Flight cancelled or diverted. |
| `raw` | `flights` | `WHEELS_ON` | 84 | 8.4% | Legitimate Nullable | Flight cancelled or diverted. |
| `raw` | `flights` | `TAXI_IN` | 84 | 8.4% | Legitimate Nullable | Flight cancelled or diverted. |
| `raw` | `flights` | `ARRIVAL_TIME` | 84 | 8.4% | Legitimate Nullable | Flight cancelled or diverted. |
| `raw` | `flights` | `ARRIVAL_DELAY` | 85 | 8.5% | Legitimate Nullable | Flight cancelled or diverted. |
| `raw` | `flights` | `CANCELLATION_REASON` | 916 | 91.6% | Legitimate Nullable | Not cancelled (flight operated normally). |
| `raw` | `flights` | `AIR_SYSTEM_DELAY` | 886 | 88.6% | Legitimate Nullable | Flight arrived on time or with delay < 15 minutes. |
| `raw` | `flights` | `SECURITY_DELAY` | 886 | 88.6% | Legitimate Nullable | Flight arrived on time or with delay < 15 minutes. |
| `raw` | `flights` | `AIRLINE_DELAY` | 886 | 88.6% | Legitimate Nullable | Flight arrived on time or with delay < 15 minutes. |
| `raw` | `flights` | `LATE_AIRCRAFT_DELAY` | 886 | 88.6% | Legitimate Nullable | Flight arrived on time or with delay < 15 minutes. |
| `raw` | `flights` | `WEATHER_DELAY` | 886 | 88.6% | Legitimate Nullable | Flight arrived on time or with delay < 15 minutes. |
| `raw` | `hotel_bookings` | `children` | 4 | 0.0034% | Legitimate Nullable | Default zero children if not entered. |
| `raw` | `hotel_bookings` | `country` | 488 | 0.4087% | Legitimate Nullable | Guest country of origin omitted or not captured during reservation. |
| `raw` | `hotel_bookings` | `agent` | 16,340 | 13.6862% | Legitimate Nullable | Bookings placed directly by guests without travel agency intermediary. |
| `raw` | `hotel_bookings` | `company` | 112,593 | 94.3069% | Legitimate Nullable | Non-corporate individual leisure bookings without company sponsor. |


## 6. Currency and Identifier Limitations

| Dataset | Domain Entity | Currency / Unit | Risk / Limitation | Recommended Operational Procedure |
| :--- | :--- | :--- | :--- | :--- |
| `hotel_bookings` | Accommodation | **EUR (€)** | Blending with INR flight costs distorts profit margins by ~90x | Convert via explicit FX table before bundling |
| `flight_prices` | Domestic Aviation | **INR (₹)** | Airfares quoted in INR for Indian metro routes | Safe to compare with synthetic search prices in INR |
| `supplier_offers` | Wholesale Supply | **INR (₹)** | Contracted wholesale inventory procurement costs | Directly compatible with customer search price units |
| `customer_search_events` | Retail Intent | **INR (₹)** | Customer search quote pricing in INR | Directly compatible with wholesale supplier offers |
| `flights` | Operations | Operational units (miles, min) | No pricing data present | Delays and cancellation rate model only |


## 7. Cross-Dataset Relationship Matrix & Cardinality

| Left Dataset | Right Dataset | Join Key(s) | Cardinality | Join Viability | Row Multiplication Risk & Caution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_search_events` | `inventory_availability` | `destination_id` | M:N | Safe when filtered | Filter by `travel_date` to avoid multi-month Cartesian explosion |
| `inventory_availability` | `supplier_offers` | `inventory_id` + `travel_date` | 1:M | Safe with snapshot filter | Group by `snapshot_date` to prevent snapshot duplicate fanout |
| `supplier_offers` | `market_seasonal_signals` | `destination_id` + `travel_date` | M:1 | Safe (100% match) | Seamless joining on destination and calendar date |
| `flights` | `airlines` | `AIRLINE` == `IATA_CODE` | M:1 | Safe (100% match) | Zero unmatched carriers |
| `flights` | `airports` | `ORIGIN_AIRPORT` == `IATA_CODE` | M:1 | Partial (3-letter only) | 5-digit numeric codes require FAA crosswalk |
| `hotel_bookings` | `inventory_availability` | None (Synthetic vs Real) | N/A | Incompatible | Train hotel ML model on hotel_bookings; score on synthetic inventory |


## 8. Machine Learning Data Leakage Audit

| Dataset | Field Name | Leakage Risk Level | Nature of Risk | Modeling Guidance |
| :--- | :--- | :--- | :--- | :--- |
| `customer_search_events` | `booking_completed`, `clicked` | **HIGH (Target Leakage)** | Outcome of the search event | Exclude when predicting search demand; use only as prediction target |
| `hotel_bookings` | `reservation_status`, `reservation_status_date` | **CRITICAL (Post-Event Leakage)** | Recorded upon departure or checkout | Strictly exclude from all pre-booking models |
| `hotel_bookings` | `is_canceled` | **HIGH (Target Leakage)** | Target label for cancellation risk | Exclude from pricing or demand forecasting models |
| `inventory_availability` | `booked_quantity`, `sold_out` | **MEDIUM (Look-ahead Risk)** | Evolving time-series inventory snapshot | Enforce `snapshot_date < travel_date` temporal boundary |
| `flights` | Delay breakdown columns | **HIGH (Post-Flight Outcome)** | Computed after flight completion | Do not use as inputs for pre-flight delay forecasting |


## 9. Exploratory Data Analysis (EDA) Readiness Assessment

### Verdict: **CONDITIONALLY READY FOR EDA & FEATURE ENGINEERING**

The nine datasets are structurally validated, correctly typed, and mathematically reconciled. However, downstream analysts and models must adhere to the following architectural guardrails:
1. **Never sum or compare Hotel ADR with Flight Prices without currency conversion** (EUR vs INR).
2. **Filter out zero-occupancy bookings** (`is_zero_occupancy == False`) when computing per-guest metrics.
3. **Respect temporal boundaries**: Do not leak post-event reservation statuses or converted booking indicators into pre-booking predictive features.
4. **Snapshot grouping**: When joining inventory snapshots with supplier offers, always filter to the target snapshot date to prevent Cartesian multiplication.
