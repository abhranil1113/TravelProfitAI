# TBO InventoryIQ — Phase 3 Final Technical Audit & Verification Report
**AI-Powered Travel Inventory & Profit Optimization Platform**  
**Team:** Team Sabuj Sangha  
**Authors:** Abhranil Pal & Arka Dyuti Bose  
**Date:** November 23, 2026  
**Phase:** Phase 3 — Feature Engineering & Dataset Transformation (Final Technical Audit)  
**Status:** COMPLETE & AUDITED — 100% Passing Tests (101/101 Unified Test Suite)

---

## Executive Summary

This document presents the final technical audit, mathematical reconciliation, temporal validation, and architectural review for **Phase 3: Feature Engineering & Dataset Transformation** of the **TBO InventoryIQ** platform.

Phase 3 engineered 234 domain variables across 7 primary domain feature matrices and 1 cross-domain procurement decision matrix. The audit rigorously inspected all data schemas, mathematical formulations, unit segregations, temporal split mechanics, and target leakage boundaries. 

**Strict Operational Boundary:**  
In accordance with phase guidelines, **zero machine learning models were trained, no optimization solvers were executed, and all raw source data and Phase 1 processed data remained completely immutable.**

---

## 1. Flight Operations Record Count & Prototype Sampling Audit

### 1.1 Findings & Source Inspection
- **Raw Dataset:** `data/raw/flights/flights.csv` contains **5,819,079 flight records** (564.96 MB on disk).
- **Cleaned Dataset:** `data/processed/flights/cleaned_flights.parquet` contains **1,000 records** (39.5 KB on disk).
- **Feature Dataset:** `data/features/flights/flight_operations_features.parquet` contains **1,000 records** (22 engineered columns, 41.2 KB on disk).

### 1.2 Root Cause & Architectural Scope
The 1,000 records in `cleaned_flights.parquet` are an **intentional, deterministic chronological head prototype sample** starting from `2015-01-01` created during Phase 1 Data Cleaning. 

| Dimension | Raw Flights Source | Prototype Development Sample |
| :--- | :--- | :--- |
| **Row Count** | 5,819,079 | 1,000 |
| **Disk Size (CSV)** | 564.96 MB | 92.4 KB |
| **In-Memory RAM** | ~1.20 GB | ~0.85 MB |
| **Pipeline Processing Time** | ~12.5 minutes | ~0.05 seconds (52 ms) |
| **Temporal Coverage** | Full Calendar Year 2015 | January 1, 2015 (Chronological Slice) |
| **Carrier Coverage** | All 14 major US carriers | 14 carriers represented |
| **Route Diversity** | 4,693 airport pairs | 312 airport pairs |

### 1.3 Production Scaling & Pipeline Toggle
The transformation logic in `FlightOperationsFeatureTransformer` is vectorized with zero row-count dependencies. To transition from development mode to full-scale training in Phase 4:
```python
# Prototype Development Mode (Default)
df_features, _ = build_all_feature_datasets(flight_sample_rows=None)  # Uses 1,000-row parquet

# Full Production Mode (High-Memory Environment)
raw_full_flights = pd.read_csv("data/raw/flights/flights.csv", low_memory=False)
full_features = FlightOperationsFeatureTransformer().transform(raw_full_flights)
```
The prototype sample fulfills its analytical purpose of validating delay modeling, route congestion indicators, and cyclic departure features without memory exhaustion on local developer environments.

---

## 2. Flight Price Split Methodology Audit (Horizon vs. Chronological)

### 2.1 Inspection of Dataset & Manifest
The source flight price dataset (`cleaned_flight_prices.parquet`, 300,153 records) is derived from the Kaggle flight price prediction dataset. 
- **Calendar Timestamps:** The dataset contains **no transaction dates, no search timestamps, and no departure calendar dates**.
- **Temporal Dimensions:** The only temporal variable is `days_left` (integer values from 1 to 49 representing the advance booking horizon).

### 2.2 Relabeling to Scenario-Based Horizon Split
Previously, this split was loosely categorized under chronological time-series splitting. Following this audit, it has been formally relabeled in `dataset_split_manifest.json` as:
**`Scenario-Based Horizon Split (Advance Booking vs. Immediate Departure)`**

```json
{
  "split_type": "Scenario-Based Horizon Split (Advance Booking vs. Immediate Departure)",
  "split_key": "days_left",
  "calendar_timestamps_present": false,
  "rationale": "Kaggle source dataset lacks calendar collection timestamps. Split evaluates model generalization across booking horizons: advance booking (>=15 days) to near-departure (1-7 days).",
  "total_records": 300153,
  "train": {
    "records": 196887,
    "pct": 65.59,
    "days_left_range": [15, 49],
    "avg_price_inr": 19448.87
  },
  "validation": {
    "records": 58315,
    "pct": 19.43,
    "days_left_range": [8, 14],
    "avg_price_inr": 22485.12
  },
  "test": {
    "records": 44951,
    "pct": 14.98,
    "days_left_range": [1, 7],
    "avg_price_inr": 25776.43
  }
}
```

### 2.3 Scientific Integrity & Generalization Target
We deliberately avoided generating synthetic calendar dates. Instead, the split tests how an ML model trained on advance booking patterns (`days_left >= 15`) generalizes to the high-volatility, dynamic-pricing environment of near-departure procurement (`days_left < 8`), where average prices surge by 32.5% (from ₹19,449 to ₹25,776).

---

## 3. Hotel Cancellation Features & Leakage Quarantine Audit

### 3.1 Pre-Booking vs. Post-Booking Operational Features
In hotel cancellation prediction, features must be strictly separated based on when they are observed:

| Feature Name | Observation Point | Classification | Pre-Booking Model Status |
| :--- | :--- | :--- | :--- |
| `lead_time_days` | Booking Creation | Transaction Attribute | **APPROVED (Input)** |
| `reserved_room_type` | Booking Creation | Customer Selection | **APPROVED (Input)** |
| `deposit_type` | Booking Creation | Payment Terms | **APPROVED (Input)** |
| `customer_type` | Booking Creation | Account Profile | **APPROVED (Input)** |
| `booking_changes` | Post-Booking Horizon | Customer Modification | **QUARANTINED for Day-0 Models** |
| `assigned_room_type` | Check-in / Night Audit | Front Desk Operation | **STRICTLY QUARANTINED (Leakage)** |
| `room_type_changed` | Check-in / Night Audit | Operational Discrepancy | **STRICTLY QUARANTINED (Leakage)** |
| `reservation_status` | Post-Departure / Checkout | Final Outcome | **STRICTLY EXCLUDED (Target)** |

`assigned_room_type` is determined when the hotel allocates a physical room (typically on the day of arrival or the preceding night audit). Using `room_type_changed` to predict cancellation at transaction time would introduce operational leakage. Therefore, `assigned_room_type` and `room_type_changed` are quarantined in `LEAKAGE_EXCLUSIONS`.

### 3.2 True Transaction Booking Date Synthesis
Because hotel cancellations occur relative to when the reservation was created, we synthesized the true booking creation date:
$$\text{booking\_date} = \text{arrival\_date} - \text{lead\_time\_days}$$

Across the 119,208 records:
- $\text{arrival\_date}$ spans `2015-07-01` to `2017-08-31` (792 days).
- $\text{booking\_date}$ spans `2013-06-24` to `2017-08-31` (1,529 days).

### 3.3 Dual Split Manifest for Hotel Models
To support both revenue management cohort evaluation and real-time transaction scoring, `dataset_split_manifest.json` now provides two distinct split strategies:

1. **Arrival Date Seasonal Cohort Split (`arrival_date`):**
   - **Train (<= 2016-12-31):** 77,597 records (65.09%), Cancel Rate: 38.64%
   - **Validation (2017-01-01 to 2017-04-30):** 23,371 records (19.61%), Cancel Rate: 39.81%
   - **Test (>= 2017-05-01):** 18,240 records (15.30%), Cancel Rate: 31.42%
2. **Transaction Booking Date Stream Split (`booking_date`):**
   - **Train (<= 2016-11-06):** 83,445 records (70.00%), Cancel Rate: 37.89%
   - **Validation (2016-11-07 to 2017-02-03):** 17,881 records (15.00%), Cancel Rate: 38.12%
   - **Test (>= 2017-02-04):** 17,882 records (15.00%), Cancel Rate: 34.21%

---

## 4. Composite Demand Score Normalization & Configurable Weights

### 4.1 Input Range & Formula Normalization
In `market_seasonal_signals.parquet`, `demand_index` is a continuous ratio bounded in `[0.0, 1.0]` (observed min = 0.06, max = 0.99, mean = 0.52). 

Previously, adding a flat event bonus of 15 to 20 points directly to a [0, 1] variable resulted in event indicators completely overpowering base demand.

### 4.2 Formula & Configurable Dataclass
We refactored `feature_engineering/demand_features.py` to implement `CompositeDemandScoreConfig`:

```python
@dataclass
class CompositeDemandScoreConfig:
    base_weight: float = 0.70              # Up to 70 points from scaled demand
    event_bonus: float = 20.0              # +20 points for holidays/festivals/events
    rain_penalty: float = 10.0             # -10 points for heavy rainfall
    heavy_rain_threshold_mm: float = 50.0  # Precipitation threshold
    demand_scale_factor: float = 100.0     # Normalizes [0, 1] to [0, 100]
```

$$\text{demand\_scaled} = \text{clip}(\text{demand\_index}, 0.0, 1.0) \times 100.0$$
$$\text{composite\_score} = \text{clip}\Big(0.70 \times \text{demand\_scaled} + 20.0 \times \mathbb{I}_{\text{event}} - 10.0 \times \mathbb{I}_{\text{rain} > 50\text{mm}},\, 0.0,\, 100.0\Big)$$

### 4.3 Boundary & Robustness Verification
Unit tests in `tests/feature_engineering/test_demand_features.py` verified:
- $\text{demand\_index} = 0.0 \implies \text{composite\_score} = 0.0$ (Low Tier)
- $\text{demand\_index} = 1.0 \implies \text{composite\_score} = 70.0$ (Extreme Peak Tier)
- Event uplift (+20.0 pts) and heavy rain penalty (-10.0 pts) calculate correctly.
- Missing inputs ($\text{NaN}$) impute safely to neutral demand (0.50 -> 35.0 score).
- Dual input scaling: accepts both raw $[0.0, 1.0]$ and pre-scaled $[0.0, 100.0]$ inputs seamlessly.

---

## 5. Demand-to-Supply Ratio & Strict Unit Segregation

### 5.1 The Unit Inconsistency Defect
The previous implementation grouped searches, inventory, and supplier offers purely by `destination_id`. This created a physical unit mismatch: hotel room nights (`ROOM_NIGHT`) and flight seats (`SEAT`) were summed together into an uninterpretable single quantity.

### 5.2 Resolution: Segregation by `(destination_id, inventory_type)`
In `feature_engineering/aggregation.py`, `build_destination_demand_supply_indicators` was refactored to group strictly by:
$$\text{Grouping Grain} = \big[\text{destination\_id},\, \text{inventory\_type}\big]$$

Each row now explicitly declares its `unit_type`:
- `HOTEL` $\implies$ `ROOM_NIGHT`
- `FLIGHT` $\implies$ `SEAT`

```
Destination: GOA
├── Inventory Type: HOTEL  | Unit: ROOM_NIGHT | Demand: 120 searches | Avail: 350 rooms | Ratio: 0.34
└── Inventory Type: FLIGHT | Unit: SEAT       | Demand: 340 searches | Avail: 180 seats | Ratio: 1.88
```

### 5.3 Heuristic Pressure Index Definition
The `demand_to_supply_ratio` is defined as:
$$\text{demand\_to\_supply\_ratio} = \frac{\text{search\_volume}}{\text{available\_units} + 1.0}$$

**Operational Interpretation:**  
This metric represents consumer inquiry density per available physical unit. 
- A ratio $\ge 1.0$ indicates search demand exceeds available bookable inventory, triggering procurement recommendations (`"High Demand - Supply Constrained"`).
- A ratio $< 1.0$ with high availability indicates excess capacity (`"Low Demand - Over-Supplied"`), signaling a hold or markdown strategy.

---

## 6. Supplier Currency & Financial Field Audit

### 6.1 Raw Data Verification
Inspection of `data/synthetic/supplier_offers.csv` confirmed that the raw dataset contains no ISO currency column. 

### 6.2 Standardization & Dual Column Support
To maintain mathematical integrity across the platform:
1. Exact numeric values were preserved without arbitrary currency exchange conversions.
2. The values are treated as INR (₹) for prototype consistency with domestic flight prices and search prices.
3. In `feature_engineering/supplier_features.py`, both canonical names and currency-tagged aliases are exposed:
   - Canonical: `purchase_cost`, `selling_price`, `gross_margin`, `min_purchase_commitment_cost`
   - Aliased: `purchase_cost_inr`, `selling_price_inr`, `gross_margin_inr`, `min_purchase_commitment_cost_inr`
4. This currency assumption is formally cataloged as a prototype limitation in `feature_metadata.json`.

---

## 7. Snapshot & Temporal Integrity Audit

### 7.1 Point-in-Time Snapshot Deduplication
In `inventory_availability`, suppliers report multiple observation snapshots over time for the same `(inventory_id, travel_date)`. Joining across snapshots without deduplication would cause Cartesian row multiplication.

In `feature_engineering/aggregation.py`, `deduplicate_latest_inventory_snapshots` extracts strictly the single most recent temporal observation per inventory unit before joining:
```python
sorted_df = inventory_df.sort_values(by=["inventory_id", "travel_date", "snapshot_date"])
latest_df = sorted_df.groupby(["inventory_id", "travel_date"], as_index=False).last()
```

### 7.2 Verification of Join Cardinality
- `customer_search_events`: 5,000 rows
- `inventory_availability`: 5,000 rows (deduplicated to 5,000 unique inventory-date items)
- `supplier_offers`: 5,000 rows
- Resulting `destination_demand_supply_features`: Exactly **20 rows** (10 destinations $\times$ 2 inventory types: `HOTEL` and `FLIGHT`). Zero row multiplication occurred.

---

## 8. Target Leakage Audit Summary

A systematic prediction cutoff audit was performed across all 8 feature datasets.

| Feature Dataset | Target Variable | Prediction Cutoff | Quarantined Features | Status |
| :--- | :--- | :--- | :--- | :--- |
| `hotel_cancellation_features` | `is_canceled` | Booking Creation Time | `reservation_status`, `reservation_status_date`, `assigned_room_type`, `room_type_changed` | **PASS** |
| `flight_price_features` | `price` | Quote / Search Time | `price` (target label excluded from input matrix) | **PASS** |
| `flight_operations_features` | `ARRIVAL_DELAY` | Scheduled Departure | 18 post-departure telemetry variables (`DEPARTURE_TIME`, `WHEELS_OFF`, `AIR_TIME`, etc.) | **PASS** |
| `customer_demand_features` | `search_volume` | Window Start Time | `clicked`, `booking_completed` (funnel outcomes) | **PASS** |
| `inventory_features` | `available_quantity` | Snapshot Date | Future snapshot observations masked via strict temporal lags | **PASS** |
| `supplier_profitability_features` | `gross_margin_pct` | Procurement Quote | `gross_margin_percentage`, `markup_percentage` (analytical metrics only) | **PASS** |
| `market_demand_features` | `demand_index` | Pre-Travel Horizon | Zero post-travel indicators | **PASS** |

Full audit details are documented in [leakage_audit.md](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/reports/feature_engineering/leakage_audit.md).

---

## 9. Re-run Validation & Test Suite Reconciliation

### 9.1 Unified Test Suite Execution
The complete project test suite was executed via `pytest tests/ -v`. **All 101 tests passed with zero failures.**

```
============================= test session starts =============================
platform win32 -- Python 3.10.0, pytest-8.3.4, pluggy-1.7.0
collected 101 items

tests\data_quality\test_audit_reconciliation.py (7 passed)
tests\data_quality\test_cleaning_pipeline.py (6 passed)
tests\data_quality\test_dataset_loading.py (7 passed)
tests\data_quality\test_validation_rules.py (7 passed)
tests\eda\test_eda_currency_safety.py (4 passed)
tests\eda\test_eda_data_loading.py (5 passed)
tests\eda\test_eda_kpis.py (6 passed)
tests\eda\test_eda_leakage_safety.py (4 passed)
tests\eda\test_eda_profiling.py (5 passed)
tests\eda\test_eda_relationships.py (3 passed)
tests\eda\test_eda_report_generation.py (2 passed)
tests\eda\test_eda_snapshot_handling.py (4 passed)
tests\eda\test_eda_source_preservation.py (2 passed)
tests\eda\test_eda_statistics.py (6 passed)
tests\feature_engineering\test_aggregation.py (3 passed)
tests\feature_engineering\test_dataset_builder.py (1 passed)
tests\feature_engineering\test_date_features.py (2 passed)
tests\feature_engineering\test_demand_features.py (5 passed)
tests\feature_engineering\test_feature_metadata.py (2 passed)
tests\feature_engineering\test_feature_pipeline.py (1 passed)
tests\feature_engineering\test_feature_validation.py (2 passed)
tests\feature_engineering\test_flight_features.py (2 passed)
tests\feature_engineering\test_hotel_features.py (2 passed)
tests\feature_engineering\test_inventory_features.py (1 passed)
tests\feature_engineering\test_leakage_detection.py (4 passed)
tests\feature_engineering\test_reproducibility.py (1 passed)
tests\feature_engineering\test_search_features.py (2 passed)
tests\feature_engineering\test_source_preservation.py (2 passed)
tests\feature_engineering\test_supplier_features.py (1 passed)
tests\feature_engineering\test_temporal_consistency.py (2 passed)

================= 101 passed, 7 warnings in 142.84s (0:02:22) =================
```

### 9.2 Generated Feature File Manifest & Byte Integrity
All datasets were successfully generated and validated in both dual formats (Parquet for ML performance and CSV for tabular verification):

| Feature Dataset Name | Rows | Columns | Parquet Path | Parquet Size | CSV Path | CSV Size |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `hotel_cancellation_features` | 119,208 | 54 | `data/features/hotel/` | 2.12 MB | `data/features/hotel/` | 29.65 MB |
| `flight_price_features` | 300,153 | 21 | `data/features/flight_prices/` | 3.23 MB | `data/features/flight_prices/` | 44.77 MB |
| `flight_operations_features` | 1,000 | 22 | `data/features/flights/` | 0.04 MB | `data/features/flights/` | 0.09 MB |
| `customer_demand_features` | 5,000 | 39 | `data/features/customer_demand/` | 0.22 MB | `data/features/customer_demand/` | 0.93 MB |
| `inventory_features` | 5,000 | 27 | `data/features/inventory/` | 0.19 MB | `data/features/inventory/` | 0.80 MB |
| `supplier_profitability_features` | 5,000 | 28 | `data/features/supplier/` | 0.45 MB | `data/features/supplier/` | 0.96 MB |
| `market_demand_features` | 5,000 | 26 | `data/features/market/` | 0.08 MB | `data/features/market/` | 0.67 MB |
| `destination_demand_supply_features` | 20 | 17 | `data/features/market/` | 0.01 MB | `data/features/market/` | 0.01 MB |

---

## 10. Final Sign-off & Phase 4 Readiness

### 10.1 Audit Sign-Off Checklist
- [x] **Flight operations sample size verified & documented (1,000 prototype sample vs 5.8M raw rows).**
- [x] **Flight price split methodology accurately relabeled as Scenario-Based Horizon Split.**
- [x] **Hotel cancellation features audited: operational check-in features quarantined; true `booking_date` synthesized.**
- [x] **Composite demand score normalized to 100-pt scale with configurable `CompositeDemandScoreConfig`.**
- [x] **Demand-to-supply ratio grouped by `(destination_id, inventory_type)` with strict `ROOM_NIGHT` vs `SEAT` segregation.**
- [x] **Supplier currency verified; canonical and aliased fields documented.**
- [x] **Temporal snapshot deduplication enforced (zero Cartesian row inflation).**
- [x] **Full target leakage audit conducted with explicit quarantine boundaries.**
- [x] **Parquet and CSV dual serialization verified across all 8 datasets.**
- [x] **100% test passing rate achieved across 101 tests spanning Phase 1, Phase 2, and Phase 3.**

### 10.2 Phase 4 Handoff Prerequisites
Phase 3 Feature Engineering & Dataset Transformation is formally **CLOSED**. The data assets, split manifests, and feature dictionaries are 100% verified, reproducible, and ready for:
1. **Phase 4: Machine Learning Model Development & Benchmarking** (Flight price regression, hotel cancellation classification, demand forecasting).
2. **Phase 5: Procurement & Profit Optimization Engine** (Constrained knapsack and mixed-integer linear programming under budget and risk constraints).
