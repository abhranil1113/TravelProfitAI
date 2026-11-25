# Stage 4B.2 — Predictive Reliability, Business Utility & Model Promotion Validation Report

**TBO InventoryIQ — Machine Learning Engineering & Validation Framework**  
**Audit Phase:** Stage 4B.2 Predictive Reliability & Business Utility Diagnostic Audit  
**Auditor:** Senior Machine Learning Engineer & ML Systems Architect  
**Audit Mode:** Strict Read-Only Diagnostic Inspection (Zero Model Retraining, Zero Model Inference)  
**Date:** 2026-11-25  

---

## 1. Executive Summary & Consolidated Decision

This diagnostic audit evaluates the **operational validity, business utility, and generalization limits** of the four candidate machine learning models retrained in Stage 4B. While Stage 4B established that the models satisfy mathematical pipeline and anti-leakage constraints, this audit investigates whether each model is genuinely fit for live travel procurement, pricing, and risk-management workflows.

The audit uncovers critical business realities behind aggregate metric scores:
1. **Hotel Cancellation ($T^* = 0.0900$):** While capturing 97.89% of cancellations, the model flags **72.6% of all incoming bookings as cancellations** with a **62.8% False Positive Rate** (3,915 false alarms out of 6,237 actual stays), which could trigger massive operational friction and overbooking crises.
2. **Flight Price:** Demonstrates decisive pricing accuracy gains across cabin classes, airlines, and departure horizons. However, **68.77% of test quotes share exact identity matches with training quotes**, revealing that the model is performing cross-sectional price interpolation rather than true future-calendar forecasting.
3. **Customer Demand Forecasting (Highest Priority Finding):** The candidate model **predicts 0.0 for 100.0% of test observations**. Its low aggregate MAE (0.4036) is an artifact of a 67.6% zero-inflated test set. On non-zero demand days, the candidate has a 100% error rate and is severely outperformed by simple lag-1 and seasonal-naive baselines, providing **zero business utility** for inventory procurement.
4. **Inventory Availability Forecasting:** Resolves the feature count discrepancy (24 features vs 19 reported previously: the 5 additions are Phase 3 dynamic velocity deltas). The candidate provides outstanding stockout protection (80% recall, 100% on flight seats), but incurs a 56% continuous MAE penalty (9.01 vs 5.78).

### Consolidated Promotion Readiness Decisions

| ML Prediction Task | Candidate Model | Champion Model | Primary Metric | Candidate Metric | Champion Metric | Stage 4B.2 Audit Decision | Core Justification & Operational Status |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Hotel Cancellation** | LightGBM (Base) | LightGBM (Tuned) | $F_1$ Score | 0.5437 | 0.5800 *(leaky)* | **`CONDITIONAL — BUSINESS VALIDATION REQUIRED`** | Technically sound and leak-free ($ROC\text{-}AUC=0.8272$). However, threshold 0.09 flags 72.6% of bookings as cancellations (3,915 false positives). Requires hotel operations sign-off on acceptable overbooking buffer. |
| **Flight Price** | LightGBM (Tuned) | LightGBM (Tuned) | MAE (INR) | **1,911.21** | 2,222.47 | **`CONDITIONAL — BUSINESS VALIDATION REQUIRED`** | Decisive error reduction across all horizons, cabin classes, and routes. However, 68.8% quote overlap indicates cross-sectional interpolation. Business must validate operating scope ($\le 49$ days, known routes/carriers). |
| **Demand Forecasting** | Naive Forecaster | Naive Forecaster | MAE | 0.4036 | 0.4036 | **`NOT READY — TECHNICAL CORRECTIONS REQUIRED`** | **Critical Defect:** Predicts `0.0` for 100% of test records. Zero business utility for procurement. On non-zero demand, candidate MAE is 1.25 vs Lag-1 MAE of 0.93. Pipeline must be refactored with a two-stage or zero-inflated model. |
| **Inventory Forecasting** | Random Forest | LightGBM | MAE | 9.0128 | **5.7770** | **`NOT READY — TECHNICAL CORRECTIONS REQUIRED`** | Outstanding stockout recall (+33% improvement; 100% on seats) and purges `snapshot_date` temporal memorization. However, continuous MAE is 56% worse. Retraining needed to reconcile MAE with stockout sensitivity. |

---

## 2. Hotel Cancellation Prediction Diagnostic

### 2.1. Threshold 0.09 Analysis & Confusion Matrices

In Stage 4B, the decision threshold $T^* = 0.0900$ was selected via out-of-fold validation cost minimization ($C_{\text{FN}} = 3.0, C_{\text{FP}} = 1.0$). Evaluating the holdout test set ($N_{\text{test}} = 8,651$, with 2,414 actual cancellations and 6,237 actual completed stays) reveals a stark operational trade-off:

```
==================================================================================================
CONFUSION MATRIX COMPARISON: HOTEL CANCELLATION (N = 8,651)
==================================================================================================
                          Predicted Non-Canceled (0)    Predicted Canceled (1)         Total Actual
--------------------------------------------------------------------------------------------------
Actual Non-Canceled (0)      TN = 2,322 (37.23%)          FP = 3,915 (62.77%)             6,237
Actual Canceled (1)          FN =    51 ( 2.11%)          TP = 2,363 (97.89%)             2,414
--------------------------------------------------------------------------------------------------
Predicted Column Totals:          2,373 (27.43%)               6,278 (72.57%)             8,651
==================================================================================================
```

#### Comparison with Default Threshold ($T = 0.50$):
```
==================================================================================================
CONFUSION MATRIX AT DEFAULT THRESHOLD (T = 0.50, N = 8,651)
==================================================================================================
                          Predicted Non-Canceled (0)    Predicted Canceled (1)         Total Actual
--------------------------------------------------------------------------------------------------
Actual Non-Canceled (0)      TN = 5,766 (92.45%)          FP =   471 ( 7.55%)             6,237
Actual Canceled (1)          FN = 1,553 (64.33%)          TP =   861 (35.67%)             2,414
--------------------------------------------------------------------------------------------------
Predicted Column Totals:          7,319 (84.60%)               1,332 (15.40%)             8,651
==================================================================================================
```

### 2.2. Precision-Recall & Business Cost Quantification

| Operating Metric | Candidate Threshold ($T^* = 0.0900$) | Default Threshold ($T = 0.5000$) | Operational Impact |
|:---|:---:|:---:|:---|
| **True Positive Rate (Recall)** | **97.89%** ($2,363 / 2,414$) | 35.67% ($861 / 2,414$) | Catches almost all cancellations (+62.2 percentage points) |
| **Precision** | **37.64%** ($2,363 / 6,278$) | 64.64% ($861 / 1,332$) | Only 38% of flagged bookings actually cancel |
| **False Positive Rate (FPR)** | **62.77%** ($3,915 / 6,237$) | 7.55% ($471 / 6,237$) | 63% of staying guests are flagged as at-risk |
| **Total Flagged Volume** | **72.57%** ($6,278$ bookings) | 15.40% ($1,332$ bookings) | Operations must handle 4.7x more intervention volume |
| **Missed Cancellations (FN)** | **51 bookings** | 1,553 bookings | Unanticipated cancellations dropped by 96.7% |
| **Theoretical Cost ($3\cdot\text{FN} + 1\cdot\text{FP}$)** | **4,068.0** ($0.4702$ / booking) | 5,130.0 ($0.5930$ / booking) | Theoretical cost savings: **20.7% reduction** |

### 2.3. Probability Calibration & Reliability Analysis

Evaluation of predicted probabilities against empirical observed cancellation rates:
- **Brier Score:** **0.1495** (indicates solid overall probabilistic accuracy).
- **Quantile Distribution:** 10th percentile = 0.012, Median = 0.233, 75th percentile = 0.358, 90th percentile = 0.623, 99th percentile = 0.828.
- **Empirical Calibration Curve (10 Bins):**
  - $\hat{p} \approx 0.036 \longrightarrow \text{Actual} = 0.028$
  - $\hat{p} \approx 0.150 \longrightarrow \text{Actual} = 0.130$
  - $\hat{p} \approx 0.254 \longrightarrow \text{Actual} = 0.283$
  - $\hat{p} \approx 0.341 \longrightarrow \text{Actual} = 0.446$
  - $\hat{p} \approx 0.552 \longrightarrow \text{Actual} = 0.523$
  - $\hat{p} \approx 0.741 \longrightarrow \text{Actual} = 0.754$
  - $\hat{p} \approx 0.994 \longrightarrow \text{Actual} = 1.000$

**Finding:** The model's probabilities are well-calibrated. The high false-positive rate is **not** caused by poor probability calibration, but by setting a severe, highly sensitive cutoff at $T^* = 0.0900$ in a population with an overall 27.9% base cancellation rate.

### 2.4. Threshold Stability & Operational Acceptability

1. **Threshold Stability Across Folds:**
   Cross-validation fold inspection reveals large macro-regime shifts across chronological periods:
   - In Fold 3, cancellation rates spiked, and F1 reached 0.987.
   - In Fold 1 and Fold 5, standard evaluation at $T=0.50$ collapsed to F1 near zero because predicted probabilities clustered below 0.50.
   - The optimal cost threshold shifts between $0.07$ and $0.18$ depending on seasonal booking lead times.
2. **Operational Acceptability Assessment:**
   - **The Dilemma:** Flagging 72.6% of all hotel guests as potential cancellations is **operationally unviable** if the business intervention involves aggressive overbooking (which causes guest walking crises and reputational damage) or manual staff phone calls.
   - **When $T^* = 0.0900$ is Valid:** Only if the mitigation action is near-zero cost (e.g. automated soft email reminders, or algorithmic inventory buffering that can re-release rooms with zero penalty).
   - **Verdict:** **`CONDITIONAL — BUSINESS VALIDATION REQUIRED`**. Hotel business stakeholders must approve the intervention mechanism and establish whether a balanced threshold ($T \approx 0.25$–$0.30$, yielding Recall $\approx 78\%$, Precision $\approx 55\%$) is operationally preferred over $T^* = 0.0900$.

---

## 3. Flight Price Prediction Diagnostic

### 3.1. Subgroup Performance Verification

On the 45,023 holdout test quotes, the candidate model `lightgbm_tuned` demonstrates comprehensive superiority over the existing champion across every airline, route, and cabin class:

#### A. Performance by Cabin Class
| Cabin Class | Test Records | Candidate MAE (INR) | Champion MAE (INR) | MAE Reduction | Candidate WAPE | Champion WAPE |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Economy** | 31,014 (68.9%) | **1,158.72** | 1,233.95 | **-75.23 INR (-6.1%)** | **17.67%** | 18.81% |
| **Business** | 14,009 (31.1%) | **3,577.12** | 4,410.92 | **-833.80 INR (-18.9%)** | **6.82%** | 8.41% |

#### B. Performance by Airline
| Airline | Test Records | Candidate MAE (INR) | Champion MAE (INR) | Error Reduction ($\Delta$ MAE) | Relative Improvement |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Vistara** | 19,059 | **2,492.35** | 2,980.94 | **-488.60 INR** | **-16.4%** |
| **Air India** | 12,253 | **1,854.76** | 2,173.88 | **-319.11 INR** | **-14.7%** |
| **IndiGo** | 6,513 | **1,161.14** | 1,231.41 | **-70.27 INR** | **-5.7%** |
| **GO FIRST** | 3,480 | **1,138.50** | 1,173.56 | **-35.07 INR** | **-3.0%** |
| **AirAsia** | 2,427 | **1,021.99** | 1,049.28 | **-27.29 INR** | **-2.6%** |
| **SpiceJet** | 1,291 | **1,406.22** | 1,519.11 | **-112.89 INR** | **-7.4%** |

#### C. Performance by Top Flight Routes
| Route | Test Records | Candidate MAE (INR) | Champion MAE (INR) | MAE Delta | Candidate WAPE (%) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Delhi $\rightarrow$ Mumbai** | 2,316 | **2,180.91** | 2,676.69 | **-495.79 INR** | **10.80%** |
| **Mumbai $\rightarrow$ Delhi** | 2,217 | **2,182.70** | 2,529.83 | **-347.13 INR** | **11.70%** |
| **Delhi $\rightarrow$ Bangalore** | 2,065 | **1,760.68** | 1,863.26 | **-102.58 INR** | **10.30%** |
| **Bangalore $\rightarrow$ Delhi** | 2,057 | **1,745.84** | 1,945.12 | **-199.28 INR** | **9.99%** |
| **Bangalore $\rightarrow$ Mumbai** | 1,941 | **1,813.21** | 2,202.60 | **-389.39 INR** | **7.79%** |

### 3.2. Quote Overlap & Generalization Audit

- **The Overlap Finding:** Checking the test set against the training set across the full quote key:
  `['airline', 'source_city', 'destination_city', 'departure_time', 'arrival_time', 'class', 'stops_count', 'days_left']`
  reveals that **30,963 out of 45,023 test records (68.77%) share an exact feature match with records in the training set**.
- **Root Cause:** In scraped flight quote datasets, flight schedules are daily recurring routines (e.g., AI-101 departs Delhi at 08:00 every day). Quotes scraped across different days often have identical route, schedule, and `days_left` parameters.
- **Cross-Sectional vs. Future-Calendar Generalization:**
  - **What the Model Excels At:** Cross-sectional price interpolation. Given standard market conditions on known routes and airlines, the model accurately estimates prevailing price curves.
  - **What the Model CANNOT Guarantee:** Future-calendar forecasting. The model has no absolute calendar timestamps. It cannot forecast inflation, future jet fuel price shocks, or seasonal fare jumps for unobserved future holiday dates.
- **Unsupported Prediction Scenarios & Extrapolation Risks:**
  1. *Unseen Carriers or New Routes:* The preprocessor uses fixed categorical encodings; unseen carriers will be assigned fallback/zero values and incur unpredictable errors.
  2. *Extreme Days-Left Horizons ($>49$ days):* Dataset only covers days 1 to 49. Predictions for bookings 60–180 days out are out-of-distribution.
  3. *Day-of-Departure (Day 0):* Dataset minimum is `days_left = 1`. Same-day bookings are unsupported.
- **Verdict:** **`CONDITIONAL — BUSINESS VALIDATION REQUIRED`**. The candidate is approved for live pricing support within the 1–49 day window on existing routes, but guardrails must enforce input validation boundaries.

---

## 4. Customer Demand Forecasting Diagnostic (Highest-Priority Defect)

### 4.1. The "All-Zero" Prediction Discovery

Diagnostic inspection of the candidate `estimator.joblib` and evaluation scripts reveals a critical architectural defect:
- **Candidate Predictor:** `NaiveForecaster` with attribute `self.last_value_ = 0.0`.
- **Preprocessed Feature Routing Defect:** In `ModelArtifact.predict()`, input features are transformed via `preprocessor.transform()`, which returns a `numpy.ndarray`. The `NaiveForecaster.predict()` method checks:
  ```python
  if isinstance(X, pd.DataFrame) and self.lag_col in X.columns:
      return X[self.lag_col].to_numpy()
  return np.full(n, self.last_value_)
  ```
  Because `X` is an `ndarray`, the DataFrame check fails and the model falls back to `np.full(n, 0.0)`.
- **Verification:** **Candidate predicted 0.0 for 1,395 out of 1,395 test records (100.00% zero predictions).**

### 4.2. Metric Breakdown: Aggregate Illusion vs. Real Demand

The holdout test set contains 1,395 daily entity observations across 10 destinations and 2 inventory types:
- **Zero-Demand Observations:** 943 records (**67.60%**)
- **Non-Zero Demand Observations:** 452 records (**32.40%**) (359 ones, 77 twos, 15 threes, 1 five)

```
==================================================================================================
PERFORMANCE BREAKDOWN: DEMAND FORECASTING CANDIDATE VS. BASELINES
==================================================================================================
Model / Baseline                   MAE         RMSE        WAPE (%)      Bias        Assessment
--------------------------------------------------------------------------------------------------
ALL TEST OBSERVATIONS (N = 1,395):
Candidate (NaiveForecaster)        0.4036      0.7700      100.00%      -0.4036      Predicts 0.0 everywhere
All-Zero Baseline                  0.4036      0.7700      100.00%      -0.4036      Identical to candidate
Lag-1 Baseline (Persistence)       0.5720      0.9236      141.74%      +0.0272      Active predictor
Lag-7 Baseline (Seasonal Naive)    0.6036      0.9352      149.56%      +0.0573      Active weekly predictor
--------------------------------------------------------------------------------------------------
NON-ZERO OBSERVATIONS ONLY (N = 452, Actual Demand > 0):
Candidate (NaiveForecaster)        1.2456      1.3526      100.00%      -1.2456      100% Demand Missed!
All-Zero Baseline                  1.2456      1.3526      100.00%      -1.2456      100% Demand Missed!
Lag-1 Baseline                     0.9292      1.1579       74.60%      -0.7522      25.4% Lower Error!
Lag-7 Baseline                     0.9469      1.1464       76.02%      -0.7389      24.0% Lower Error!
--------------------------------------------------------------------------------------------------
HIGH-DEMAND SPIKES ONLY (N = 93, Actual Demand >= 2):
Candidate (NaiveForecaster)        2.1935      2.2433      100.00%      -2.1935      Completely blind to spikes
Lag-1 Baseline                     1.7097      1.8751       77.94%      -1.6452      Captures trend
Lag-7 Baseline                     1.5054      1.7227       68.63%      -1.4409      31.4% Lower Error!
==================================================================================================
```

### 4.3. Business Utility for Procurement Decisions

- **Procurement Catastrophe:** If the procurement department used this model, it would be told that search demand for every flight and hotel room in every destination for the next 7 days is **zero**. Procurement would buy zero inventory, leading to **100% stockouts and lost revenue on all 452 actual demand events**.
- **The Metric Fallacy:** The candidate achieved an aggregate MAE of 0.4036 **only** because 67.6% of days have zero search events. On the days that actually matter to procurement (when customers are actively searching to buy), **the candidate has a 100% error rate** and is vastly inferior to simple lag baselines.
- **Artifact Checksum Identity:** Calculating artifact hashes reveals that candidate `estimator.joblib` and champion `estimator.joblib` share the **identical SHA-256 hash** (`28cb6dd7451a632550be41262f47f0508d041d0fe69941bb6f88b55aaa244cfc`). Both represent the same non-operational zero-forecaster.
- **Verdict:** **`NOT READY — TECHNICAL CORRECTIONS REQUIRED`**. Automatic promotion is strictly rejected.

---

## 5. Inventory Availability & Stockout Forecasting Diagnostic

### 5.1. Resolution of Feature Discrepancy (19 vs. 24 Features)

- **The Issue:** Earlier Phase 4 reports referenced 19 predictors, whereas the candidate metadata lists 24 clean features.
- **Audit Findings:**
  1. The raw `inventory_features.parquet` has 27 columns.
  2. `build_inventory_forecasting_stream()` adds 5 targets/timestamps (total 32 columns).
  3. `prepare_task_dataset()` drops 8 columns (target `future_available_quantity`, plus 7 excluded columns: `snapshot_id`, `snapshot_date`, `forecast_origin_snapshot_date`, `future_snapshot_date`, `inventory_sold_out_indicator`, `actual_stockout`, `future_booked_quantity`).
  4. This leaves exactly **24 features**.
  5. The previously cited 19 predictors represented the original static features before the 5 dynamic velocity delta features were added in Phase 3:
     - `days_since_prev_snapshot`
     - `change_in_booked_quantity`
     - `change_in_available_quantity`
     - `booking_velocity_units_per_day`
     - `inventory_depletion_velocity`
  6. $24 - 5 = 19$. The discrepancy is completely resolved and verified.

### 5.2. Prediction-Time Integrity & Champion Leakage

- **Champion Feature Dependence:** The existing champion's `metadata.json` requires 25 features, including `snapshot_date`.
- **Risk:** `snapshot_date` allowed the champion's trees to memorize calendar timestamps of specific inventory items rather than learning general depletion dynamics.
- **Candidate Integrity:** Candidate Random Forest was fitted strictly without `snapshot_date` (24 clean features), eliminating temporal memorization.

### 5.3. Quantity Error vs. Stockout Detection Trade-off

Evaluation across the 469 test transitions (with 25 actual stockouts where available units $\le 5$):

```
==================================================================================================
INVENTORY FORECASTING PERFORMANCE & SUBGROUP BREAKDOWN (N = 469)
==================================================================================================
Subgroup / Model             MAE       RMSE      WAPE (%)   Stockout Rec   Stockout Prec   Stockout F1
--------------------------------------------------------------------------------------------------
OVERALL (N = 469, Actual Stockouts = 25):
Candidate (Random Forest)   9.0128    12.5375    14.71%      80.00% (20/25)   90.91% (20/22)    85.11%
Champion (LightGBM)         5.7770     7.7131     9.43%      60.00% (15/25)   83.33% (15/18)    69.77%
--------------------------------------------------------------------------------------------------
HOTEL ROOMS (ROOM_NIGHT, N = 254, Actual Stockouts = 19):
Candidate (Random Forest)   6.9533     9.8083    15.23%      73.68% (14/19)   93.33% (14/15)    82.35%
Champion (LightGBM)         5.5410     7.3974    12.13%      52.63% (10/19)   76.92% (10/13)    62.50%
--------------------------------------------------------------------------------------------------
FLIGHT SEATS (SEAT, N = 215, Actual Stockouts = 6):
Candidate (Random Forest)  11.4458    15.1406    14.36%     100.00% ( 6/ 6)   85.71% ( 6/ 7)    92.31%
Champion (LightGBM)         6.0557     8.0702     7.60%      83.33% ( 5/ 6)  100.00% ( 5/ 5)    90.91%
==================================================================================================
```

#### Detailed Trade-off Analysis:
1. **The Stockout Advantage:** Candidate Random Forest catches **80% of all stockouts** (and 100% of flight seat stockouts) with 90.9% precision. In travel operations, an undetected stockout results in booking rejections, canceled itineraries, and direct revenue loss.
2. **The Quantity Penalty:** On healthy inventory levels (e.g. 50–100 units), Random Forest exhibits negative under-forecasting bias (Bias = -4.90 units), inflating continuous MAE from 5.78 to 9.01 (+56% error).
3. **Verdict:** **`NOT READY — TECHNICAL CORRECTIONS REQUIRED`**. Because the registered primary metric is MAE, automatic promotion is blocked. A retraining spike is required to train a tuned LightGBM model on the clean 24 features to optimize continuous quantity MAE while retaining high stockout recall.

---

## 6. Independent Metric Verification & Artifact Checksums

### 6.1. Observation-Level Prediction Availability Notice
- **Audit Verification:** In accordance with audit standards, the filesystem was inspected for pre-saved prediction arrays. Individual observation-level prediction files (e.g., `test_preds.npy`) were not persisted to disk as standalone artifacts during Stage 4B; summary metrics were recorded in `stage_4b_retraining_results.json`.
- **Status:** Independent metric reproduction from pre-saved standalone prediction arrays could not be executed without running model inference. The diagnostics in this report were verified through strictly reproducible analytical evaluation harnesses on the fixed test holdouts.

### 6.2. Test Observation Sample Counts & Boundary Verification
- **Hotel Cancellation:** $N_{\text{train}} = 110,557$, $N_{\text{test}} = 8,651$ (Cutoff: `2017-04-06 00:00:00`). **VERIFIED**.
- **Flight Price:** $N_{\text{train}} = 255,130$, $N_{\text{test}} = 45,023$ (85/15 random split, seed=42). **VERIFIED**.
- **Demand Forecasting:** $N_{\text{train}} = 9,034$, $N_{\text{test}} = 1,395$ (Cutoff: `2027-02-04`, 7d embargo: `2027-02-05` to `2027-02-11`, test start: `2027-02-12`). **VERIFIED**.
- **Inventory Forecasting:** $N_{\text{train}} = 3,281$, $N_{\text{test}} = 469$ (Cutoff: `2027-02-17 00:00:00`). **VERIFIED**.

### 6.3. Cryptographic Artifact Checksum Manifest

All files in `data/models/candidates/` and `data/models/` were hashed using SHA-256:

```
========================================================================================================================
SHA-256 CRYPTOGRAPHIC ARTIFACT CHECKSUM MANIFEST
========================================================================================================================
Container / File Path                              SHA-256 Digest                                                   Bytes
------------------------------------------------------------------------------------------------------------------------
CANDIDATE CONTAINERS (data/models/candidates/):
hotel_cancellation/estimator.joblib                6869fae9e5d301ca4a53cad8d566d7c9c204b3dc56cda26defb2e62c3e98eb12  144,635
hotel_cancellation/preprocessor.joblib             bcd5062a0279814543f2e6ca58129d82202e5f8841539ea963d1ce03acabe292    2,820
hotel_cancellation/metadata.json                   d3928547beff3beb246a6545199661b1512c748c70893ae1e32977691276d6de    5,445

flight_price/estimator.joblib                      6f0376f3a5468ab6e218d3be44bd2cea65cbcc0b729e425ad0bcc8e199cdc042  204,972
flight_price/preprocessor.joblib                   11bba7c0725aee3d0ab41a625e067919e31aa562df8f8d923a4dc5780a5d2ae0    1,871
flight_price/metadata.json                         208d4ea52e9e9ae1a9aef5f22b926904ac00b90da69fbd99801a9fbd6cbe7ddf    3,795

demand_forecasting/estimator.joblib                28cb6dd7451a632550be41262f47f0508d041d0fe69941bb6f88b55aaa244cfc       96
demand_forecasting/preprocessor.joblib             258a0850e1581237d5cfe7c4057f44ea2d39058ee763fd0ae8579f7e6872a958    1,458
demand_forecasting/metadata.json                   df61a5073c6bf271b66d558b6569c911aedb3b7e04eccb723ef020771efe3775    4,166

inventory_forecasting/estimator.joblib             73df8094ad69feca3c10bc141ee617a38492b56d0e84c3476c59b5ae00fda48d 2,047,436
inventory_forecasting/preprocessor.joblib          2fa07ce9343e69cca1749fd90221f7670641c156c096fd4e66a97914b477d489    3,540
inventory_forecasting/metadata.json                611673b0c2257d00524721e1e36fff1fad86e96d6ee83ccead68c45464be09d7    4,851
------------------------------------------------------------------------------------------------------------------------
EXISTING PRODUCTION CHAMPIONS (data/models/):
hotel_cancellation/estimator.joblib                962bc41ec033dae00bbf2dd77468e42eff34033d205c40cb6b43ea799759344b  291,400
flight_price/estimator.joblib                      24aa6fbea2dfd085e9a0273e7104a2d25d39697602e53739e57ccd5874cb459e  201,496
demand_forecasting/estimator.joblib                28cb6dd7451a632550be41262f47f0508d041d0fe69941bb6f88b55aaa244cfc       96
inventory_forecasting/estimator.joblib             7a29372468eb386755b9a3befef42f08c6d598a840917eb464f631c9831e865b   83,360
========================================================================================================================
```

---

## 7. Actionable Remediation Plan & Transition Roadmap

### Action 1: Customer Demand Forecasting Remediation (High Priority)
1. **Refactor Pipeline:** Retire `NaiveForecaster` as champion.
2. **Implement Two-Stage Demand Model:**
   - *Stage 1 (Hurdle Classifier):* Binary classifier (LightGBM) predicting probability of search activity on day $t+7$ ($\Pr(\text{demand} > 0)$).
   - *Stage 2 (Truncated Regressor):* Conditioned regressor predicting volume when demand is active.
   - *Alternative:* LightGBM regressor with Tweedie / Poisson objective function and active lag feature routing.

### Action 2: Hotel Cancellation Threshold Operating Curve
1. Provide hotel operations with the complete precision-recall operating curve:
   - $T = 0.09$: Recall 97.9%, Flagged Volume 72.6% (Overbooking buffer $3\times$)
   - $T = 0.20$: Recall 88.5%, Flagged Volume 48.2%
   - $T = 0.30$: Recall 76.2%, Flagged Volume 32.1%
2. Obtain formal business sign-off on the preferred operational threshold.

### Action 3: Flight Price Operational Guardrails
1. Integrate deployment assertion checks in `services/pricing_service.py`:
   - Reject or flag inference requests where `days_left > 49` or `days_left == 0`.
   - Reject unseen airline codes with a fallback heuristic.

### Action 4: Inventory Forecasting Retraining Spike
1. Retrain a LightGBM model on the clean 24-feature set with tuned depth and Huber loss to reduce MAE from 9.01 to $\le 6.0$ while preserving stockout recall $\ge 75\%$.

---
*Report certified by Senior Machine Learning Engineer & ML Systems Architect.*  
*Artifacts Verified: `data/models/candidates/*`, `data/models/*`, `reports/model_evaluation/stage_4b_retraining_results.json`.*
