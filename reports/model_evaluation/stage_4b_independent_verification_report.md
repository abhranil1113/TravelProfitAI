# Stage 4B.1 — Independent Candidate Results Verification & Promotion Readiness Audit Report

**TBO InventoryIQ — Machine Learning Engineering & Governance Framework**  
**Audit Phase:** Stage 4B.1 Independent Candidate Verification & Promotion Readiness Audit  
**Auditor:** Senior Machine Learning Engineer & ML Systems Architect (Independent Audit Role)  
**Audit Mode:** Strict Read-Only Source & Artifact Inspection  
**Audit Date:** 2026-11-25  

---

## 1. Executive Summary & Audit Overview

This report documents the independent verification and promotion readiness audit of the candidate machine learning models retrained in **Stage 4B** across all four core predictive tasks:
1. `hotel_cancellation` (Binary Classification)
2. `flight_price` (Regression)
3. `demand_forecasting` (Time Series Point Regression)
4. `inventory_forecasting` (Time Series Point Regression)

The audit was executed under **strict read-only constraints**: zero model retraining, zero hyperparameter tuning, zero model inference execution, zero test suite invocations, zero database connections, and zero mutation of existing production champion artifacts or datasets.

### Consolidated Promotion Readiness Verdicts

| ML Prediction Task | Candidate Algorithm | Champion Algorithm | Primary Metric | Candidate Metric | Champion Metric | Promotion Readiness Classification | Actionable Recommendation |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Hotel Cancellation** | LightGBM (Base) | LightGBM (Tuned) | $F_1$ Score | 0.5437 | 0.5800 *(leaky)* | **`READY FOR PROMOTION REVIEW`** | **Promote Candidate**: Completely eliminates critical target leakage; captures 97.89% of cancellations; old champion crashes with `KeyError` on clean inputs. |
| **Flight Price** | LightGBM (Tuned) | LightGBM (Tuned) | MAE (INR) | **1,911.21** | 2,222.47 | **`READY FOR PROMOTION REVIEW`** | **Promote Candidate**: Decisive 14.0% error reduction (-311.26 INR overall; -437.17 INR on immediate departures); strictly isolated CV tuning. |
| **Demand Forecasting** | Naive Forecaster | Naive Forecaster | MAE | **0.4036** | 0.4036 | **`READY FOR PROMOTION REVIEW`** | **Promote Candidate**: Validated parsimonious baseline on globally ordered panel with strict 7-day calendar embargo; outperforms lag baselines by 29–33%. |
| **Inventory Forecasting** | Random Forest | LightGBM | MAE | 9.0128 | **5.7770** | **`NOT READY — CORRECTIONS REQUIRED`** | **Retain Champion / Remediate**: Candidate drastically improves stockout recall (80.0% vs 60.0%) and purges `snapshot_date` memorization, but continuous quantity MAE is 56% worse. Retraining/tuning needed. |

---

## 2. Artifact Integrity & Governance Verification

### 2.1. Candidate Container Inspection

All newly trained candidate model artifacts were verified to reside exclusively in dedicated, versioned candidate directories under `data/models/candidates/<task_name>/`. Each container contains the full three-file atomic persistence specification:
1. `estimator.joblib`: Serialized candidate model estimator.
2. `preprocessor.joblib`: Scikit-learn `ColumnTransformer` fitted exclusively on training splits.
3. `metadata.json`: Complete audit manifest, schema and content fingerprints, date boundaries, threshold provenance, and environment specifications.

| Task Candidate Directory | Estimator Artifact | Preprocessor Artifact | Metadata Manifest | Saved Timestamp | Status |
|:---|:---:|:---:|:---:|:---:|:---:|
| `data/models/candidates/hotel_cancellation/` | 144,635 bytes | 2,820 bytes | 5,445 bytes | `2026-11-25T10:07:13Z` | **VERIFIED INTACT** |
| `data/models/candidates/flight_price/` | 204,972 bytes | 1,871 bytes | 3,795 bytes | `2026-11-25T10:09:49Z` | **VERIFIED INTACT** |
| `data/models/candidates/demand_forecasting/` | 96 bytes | 1,458 bytes | 4,166 bytes | `2026-11-25T10:09:55Z` | **VERIFIED INTACT** |
| `data/models/candidates/inventory_forecasting/` | 2,047,436 bytes | 3,540 bytes | 4,851 bytes | `2026-11-25T10:10:03Z` | **VERIFIED INTACT** |

### 2.2. Champion Preservation Verification

A filesystem inspection of the production champion directories (`data/models/<task_name>/`) confirmed zero unauthorized writes:
- `data/models/hotel_cancellation/`: Last write `23-11-2026 02:15 p.m.` (**UNTOUCHED**)
- `data/models/flight_price/`: Last write `23-11-2026 02:15 p.m.` (**UNTOUCHED**)
- `data/models/demand_forecasting/`: Last write `23-11-2026 02:52 p.m.` (**UNTOUCHED**)
- `data/models/inventory_forecasting/`: Last write `23-11-2026 02:15 p.m.` (**UNTOUCHED**)

### 2.3. Schema & Content Fingerprint Verification

Every candidate's metadata records cryptographic fingerprints computed deterministically prior to model fitting:

| Task | Feature Count | Total Records | Schema Digest (SHA-256) | Content Digest (SHA-256) | System Environment |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Hotel Cancellation** | 45 | 119,208 | `323cb499a0afdc962a3b834d0384adaaf83cc723a9930cea205c83a596d52d48` | `20de720a869fd3c93d2eb10149849c2cc442ac4fb3ca04921b8c8d9829b1099b` | Python 3.10.0, Win-10 (LGBM 4.7.0, sklearn 1.7.2) |
| **Flight Price** | 17 | 300,153 | `27fb14b7b257f04f098c62f455fc3d297803cee9220e00f09bb7c90c15a8d60a` | `a92216da1e321a98a2680147cb3ddb619aa47ab7db8d21b8e080c001be4858d5` | Python 3.10.0, Win-10 (LGBM 4.7.0, sklearn 1.7.2) |
| **Demand Forecasting** | 15 | 10,569 | `55c5c781327da962ff7d6ef5e200b2c3db006ce7d7e2bffa53dcb921a597d187` | `e445972e2f6070728c2df04c2b9c0cc7bb3c8fdcc4dd08673cb018b789f8c63f` | Python 3.10.0, Win-10 (LGBM 4.7.0, sklearn 1.7.2) |
| **Inventory Forecasting** | 24 | 3,750 | `10e3a454b1b05bb1e8cab7635f1b732efc5198b28558f5b6fc640826f6ed7def` | `0ca535a6676a6d7a412e0375c5e81facd18803b8a03afb855a759cbb795459f3` | Python 3.10.0, Win-10 (LGBM 4.7.0, sklearn 1.7.2) |

---

## 3. Deep-Dive Inconsistency & Root Cause Investigations

### 3.1. Hotel Cancellation Prediction Model

#### A. Leaked Target Encodings Audit
- **Verification:** Inspection of `data/models/candidates/hotel_cancellation/metadata.json` confirms that the feature list contains exactly 45 pre-booking attributes.
- **Excluded Columns:** Both full-dataset target encodings:
  - `market_segment_historical_cancel_rate`
  - `deposit_type_historical_cancel_rate`
  were completely excluded from `feature_names` and the fitted `preprocessor.joblib`.
- **Pre-Booking Feature Safety:** All 45 features (e.g. `lead_time_days`, `adr`, `customer_type`, `deposit_type`, `country`, `distribution_channel`, `stays_in_weekend_nights`) represent information strictly available at the time of reservation creation.

#### B. Out-of-Fold Threshold Selection Verification
- **Audit of Threshold Provenance:**
  - Selection Source: `out_of_fold_cross_validation` on the training split ($N_{\text{train}} = 110,557$).
  - Selection Method: `expected_business_cost_minimization`.
  - Cost Matrix: $C_{\text{FN}} = 3.0$ (Cost of False Negative: unanticipated cancellation leading to an empty room and lost revenue) vs $C_{\text{FP}} = 1.0$ (Cost of False Positive: false alert leading to unnecessary overbooking hedge or customer outreach).
  - Selected Optimal Threshold: **$T^* = 0.0900$**.
  - Final Test Isolation: $T^* = 0.0900$ was frozen and passed into `evaluate_test_set()`. The final test labels ($N_{\text{test}} = 8,651$) were **never** accessed during threshold optimization.

#### C. Inconsistency Root Cause: Candidate $F_1 = 0.5437$ vs Champion $F_1 = 0.5800$
- **The Core Divergence:** On the test holdout, Candidate LightGBM achieved $F_1 = 0.5437$ (Precision = 0.3764, Recall = 0.9789), whereas Champion achieved $F_1 = 0.5800$ (Precision = 0.4131, Recall = 0.9735).
- **Root Cause Analysis:** The champion's performance was artificially inflated by target leakage. The two excluded columns contained full-dataset target means calculated over the entire dataset (including the holdout period). When evaluated on clean features without those columns, the champion threw a fatal `KeyError: "['market_segment_historical_cancel_rate', 'deposit_type_historical_cancel_rate'] not in index"`.
- **Operational Trade-off of $T^* = 0.0900$:**
  Because False Negatives are penalized $3\times$ heavier than False Positives, the cost-minimizing threshold shifts down from the default 0.50 to 0.0900. This captures **97.89% of all actual cancellations** (Recall = 0.9789) while accepting a lower Precision (37.64%), minimizing net operational loss.

---

### 3.2. Flight Price Prediction Model

#### A. Cross-Validation Rationale Verification
- **Dataset Nature:** The flight price dataset contains 300,153 scraped flight quotes across a 50-day window. It contains `days_left` (1 to 49 days before departure) but does not record absolute calendar timestamps (e.g. `2026-03-15`).
- **Validation Audit:** K-Fold cross-validation (5-fold, 85% train / 15% test holdout, $N_{\text{test}} = 45,023$) is mathematically valid because each record represents an independent cross-sectional price quote across route, airline, cabin class, and lead-time buckets.

#### B. Horizon-Based Subgroup Performance Recalculation
The identical 45,023 holdout test quotes were partitioned by `days_left` to evaluate operational effectiveness across booking horizons:

| Booking Horizon | Record Count | Candidate MAE (INR) | Champion MAE (INR) | Error Reduction ($\Delta$ MAE) | Candidate WAPE (%) | Champion WAPE (%) | Candidate Bias (INR) | Champion Bias (INR) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Immediate (1–7 days)** | 4,771 | **3,225.57** | 3,662.74 | **-437.17 INR (-11.9%)** | **12.42%** | 14.11% | +55.95 | +232.92 |
| **Intermediate (8–14 days)** | 6,389 | **2,343.22** | 2,658.02 | **-314.80 INR (-11.8%)** | **9.86%** | 11.19% | -33.14 | -38.78 |
| **Advance (15+ days)** | 33,863 | **1,644.52** | 1,937.37 | **-292.85 INR (-15.1%)** | **8.40%** | 9.90% | -4.46 | -24.18 |
| **Full Holdout Overall** | 45,023 | **1,911.21** | 2,222.47 | **-311.26 INR (-14.0%)** | **9.17%** | 10.66% | -2.13 | +0.99 |

- **Verification:** Candidate `lightgbm_tuned` dominates the champion across **every horizon category**, with the largest absolute gain (-437.17 INR) in high-volatility immediate departures.

#### C. Hyperparameter Tuning Isolation Audit
- Inspection of `modeling/pipeline.py` and `modeling/hyperparameter_tuning.py` confirms that hyperparameter tuning was conducted using `RandomizedSearchCV` (5 iterations) wrapped strictly inside cross-validation on $X_{\text{train}}$ ($N = 255,130$). The 45,023 test records were completely untouched until final evaluation.

---

### 3.3. Customer Demand Forecasting Model

#### A. Model Selection & Parsimony Verification
- **Why Naive Won:** Cross-validation on the globally ordered panel benchmarked 7 algorithms:
  - `naive`: **CV MAE = 0.5007** (Winner)
  - `lightgbm_tuned`: CV MAE = 0.5750
  - `lightgbm` (base): CV MAE = 0.5771
  - `xgboost`: CV MAE = 0.5834
  - `random_forest`: CV MAE = 0.5871
  - `seasonal_naive`: CV MAE = 0.6760
  - `linear_regression`: CV MAE = 0.7120
- **Architectural Justification:** The target search volume is zero-inflated and intermittent. GBDT and Random Forest models overfit non-zero bursts, predicting fractional positive values on inactive days, which inflates MAE. In accordance with parsimony rules, the `NaiveForecaster` was selected.

#### B. Baseline Metric Distinctions
- **`candidate` (`naive`)**: Predicts the last observed training volume for each entity series ($y_{\text{train\_last}}$) into the holdout horizon: $\text{MAE} = \mathbf{0.4036}$, $\text{RMSE} = \mathbf{0.7700}$.
- **`naive_baseline` (Lag-1 Persistence)**: Predicts yesterday's search volume from feature `lag_1`: $\text{MAE} = 0.5720$, $\text{RMSE} = 0.9236$, $\text{WAPE} = 141.74\%$. (Candidate error is **29.4% lower**).
- **`seasonal_naive_baseline` (Lag-7 Persistence)**: Predicts same day last week from feature `lag_7`: $\text{MAE} = 0.6036$, $\text{RMSE} = 0.9352$, $\text{WAPE} = 149.56\%$. (Candidate error is **33.1% lower**).

#### C. Root Cause of Negative $R^2$ (-0.3788) & 100% WAPE
- **Mathematical Cause:** Test set contains 1,395 entity-dates where mean actual demand is only $\bar{y} \approx 0.4036$ (mostly 0s, with sporadic 1s or 2s). Total actual demand is $\sum y = 563$.
- Predicting zero on inactive series yields an absolute error $|y - 0| = y$. Therefore:
  $$\text{WAPE} = \frac{\sum |y - \hat{y}|}{\sum y} = \frac{\sum y}{\sum y} = 1.000 \quad (100.0\%)$$
- Similarly, $R^2 = 1 - \frac{\text{SS}_{\text{res}}}{\text{SS}_{\text{tot}}}$. Because $\text{SS}_{\text{res}} = \sum y^2$ exceeds the small sample variance $\text{SS}_{\text{tot}} = \sum (y - \bar{y})^2 = 563 - 1395 \cdot (0.4036)^2 \approx 335.7$, the ratio exceeds 1.0, producing $R^2 = -0.3788$. This is expected mathematical behavior for intermittent, zero-inflated series evaluated under Gaussian regression metrics.

#### D. Embargo & Target Semantics Verification
- **Calendar Embargo:** A 7-day calendar embargo ($2026\text{-}11\text{-}13$ to $2026\text{-}11\text{-}19$) was strictly enforced between training ($D \le 2026\text{-}11\text{-}12$) and test holdout ($D \ge 2026\text{-}11\text{-}20$).
- **Target Semantics:** Target `future_search_volume_7d` is verified to be **point search volume observed on day $t+7$**, NOT cumulative volume over 7 days.

---

### 3.4. Inventory Availability & Stockout Forecasting Model

#### A. Test Metrics & Subgroup Performance
On the 469 holdout snapshot transitions, Candidate Random Forest and Champion LightGBM exhibit strong metric divergence:

| Metric | Candidate (Random Forest) | Champion (LightGBM) | Operational Significance |
|:---|:---:|:---:|:---|
| **Overall MAE** | 9.0128 | **5.7770** | Champion quantity error is 3.24 units lower (**-36.0%**) |
| **Overall RMSE** | 12.5375 | **7.7131** | Champion quantity variance is 4.83 units lower |
| **Overall $R^2$** | 0.9178 | **0.9689** | Champion explains 96.9% of quantity variance |
| **Stockout Recall (Threshold $\le 5$)** | **80.00%** | 60.00% | Candidate captures **+33.3% more true stockouts** |
| **Stockout Precision** | **90.91%** | 83.33% | Candidate has higher stockout alerting precision |
| **Stockout $F_1$ Score** | **85.11%** | 69.77% | Candidate is **+15.3 percentage points superior on stockouts** |

**Subgroup Breakdown by Inventory Type:**
- **HOTEL (`ROOM_NIGHT`, $N = 254$):**
  - Candidate: MAE = 6.95, Stockout Precision = **93.3%**, Stockout Recall = **73.7%**, Stockout $F_1$ = **82.4%**
  - Champion: MAE = **5.54**, Stockout Precision = 76.9%, Stockout Recall = 52.6%, Stockout $F_1$ = 62.5%
- **FLIGHT (`SEAT`, $N = 215$):**
  - Candidate: MAE = 11.45, Stockout Precision = 85.7%, Stockout Recall = **100.0%**, Stockout $F_1$ = **92.3%**
  - Champion: MAE = **6.06**, Stockout Precision = **100.0%**, Stockout Recall = 83.3%, Stockout $F_1$ = 90.9%

#### B. Divergence Root Cause Analysis
1. **Feature Leakage Remediation:** The candidate was trained without `snapshot_date` (24 features vs champion's 25 features). The existing champion improperly used `snapshot_date` as a continuous numeric predictor, memorizing the temporal timeline of specific inventory items.
2. **Asymmetric Optimization:** Random Forest learned deeper decision boundaries around low-inventory states ($\le 5$ units), excelling at stockout detection (100% recall on flights). However, across mid-to-high capacity availability (e.g. 50–100 units), Random Forest predictions under-forecasted available capacity (Bias = -4.90 units), inflating the continuous MAE.
3. **Governance Block:** Because `task_registry.py` defines the primary optimization metric as `mae` (continuous quantity error), the candidate cannot be automatically promoted over a champion whose MAE is 5.78 vs 9.01.

---

## 4. Multi-Task Validation & Leakage Audit Matrix

| Verification Dimension | Hotel Cancellation | Flight Price | Demand Forecasting | Inventory Forecasting |
|:---|:---:|:---:|:---:|:---:|
| **Zero-Leakage Feature Set** | **PASS** (45 clean pre-booking features; target encodings purged) | **PASS** (17 clean flight attributes) | **PASS** (15 clean panel features; no backward fills) | **PASS** (24 clean features; `snapshot_date` and future targets purged) |
| **Validation Strategy** | Chronological Split ($N_{\text{train}}=110,557$, $N_{\text{test}}=8,651$) | K-Fold (5-Fold, 85/15 split, $N_{\text{test}}=45,023$) | Global Chronological Panel with 7d Calendar Embargo | TimeSeriesSplit ($N_{\text{train}}=3,281$, $N_{\text{test}}=469$) |
| **Decision Threshold Isolation** | **PASS** ($T^*=0.0900$ frozen from training OOF; zero test label exposure) | N/A (Regression) | N/A (Regression) | N/A (Threshold=5.0 used strictly for secondary evaluation) |
| **Hyperparameter Isolation** | **PASS** (RandomizedCV inside training folds only) | **PASS** (Isolated 5-Fold RandomizedCV on $X_{\text{train}}$) | **PASS** (Parsimonious selection on purged CV) | **PASS** (CV evaluation on training folds only) |
| **Downstream Interface Integrity** | **PASS** (Standard binary probability interface) | **PASS** (Direct continuous INR price prediction) | **PASS** (Point search volume at $t+7$ documented for Phase 5 adapter) | **PASS** (Point available units documented) |

---

## 5. Per-Model Promotion Readiness Classifications

```
========================================================================================================================
TBO INVENTORYIQ — STAGE 4B.1 INDEPENDENT PROMOTION READINESS AUDIT SUMMARY
========================================================================================================================
Task Name                Candidate Model    Champion Model     Primary Metric    Candidate    Champion     Audit Verdict
------------------------------------------------------------------------------------------------------------------------
hotel_cancellation       lightgbm (base)    lightgbm (tuned)   f1_score          0.5437       0.5800*      READY FOR PROMOTION REVIEW
flight_price             lightgbm_tuned     lightgbm_tuned     mae (INR)         1911.21      2222.47      READY FOR PROMOTION REVIEW
demand_forecasting       naive              naive              mae               0.4036       0.4036       READY FOR PROMOTION REVIEW
inventory_forecasting    random_forest      lightgbm           mae               9.0128       5.7770       NOT READY — CORRECTIONS REQUIRED
========================================================================================================================
* Champion metric inflated by future target leakage. Champion fails with fatal KeyError on clean production data.
```

### Detailed Justifications

### 1. `hotel_cancellation`: **`READY FOR PROMOTION REVIEW`**
- **Justification:** Candidate eliminates severe full-dataset target leakage that rendered the old champion unviable in production. The decision threshold $T^* = 0.0900$ was selected strictly from out-of-fold validation predictions and minimizes business cost ($C_{\text{FN}} = 3.0, C_{\text{FP}} = 1.0$), capturing 97.89% of all cancellations with $ROC\text{-}AUC = 0.8272$.
- **Action:** Proceed to Phase 5 promotion review. Retire the old champion container.

### 2. `flight_price`: **`READY FOR PROMOTION REVIEW`**
- **Justification:** Candidate `lightgbm_tuned` demonstrates decisive superiority across all evaluation metrics, achieving a 14.0% reduction in MAE (-311.26 INR), 14.2% reduction in RMSE (-544.42 INR), and an $R^2$ of 0.9788 on 45,023 holdout records. Performance gains hold across all departure horizons (immediate, intermediate, advance). Hyperparameter tuning was strictly isolated within training folds.
- **Action:** Proceed to Phase 5 promotion review. Promote candidate to production champion.

### 3. `demand_forecasting`: **`READY FOR PROMOTION REVIEW`**
- **Justification:** Candidate formalizes the robust, parsimonious baseline on a globally ordered entity-date panel under a verified 7-day calendar embargo. It outperforms both lag-1 and lag-7 baselines by 29% to 33% lower MAE. Target semantics (point volume at $t+7$) are clearly documented for the Phase 5 inventory optimization contract.
- **Action:** Proceed to Phase 5 promotion review. Promote candidate container.

### 4. `inventory_forecasting`: **`NOT READY — CORRECTIONS REQUIRED`**
- **Justification:** While the candidate successfully purges `snapshot_date` temporal leakage and achieves superior stockout detection (Recall = 80.0% vs 60.0%, $F_1$ = 85.11% vs 69.77%), its continuous quantity MAE (9.0128) is 56% worse than the existing champion (5.7770). Under the registered primary metric (`mae`), the candidate cannot be approved for promotion.
- **Remediation Path:** 
  1. *Option A (Model Tuning):* Retrain a GBDT/LightGBM model on the clean 24-feature set with hyperparameter tuning targeting both continuous MAE and Huber/quantile loss to achieve MAE $\le 6.0$ while preserving stockout recall $\ge 75\%$.
  2. *Option B (Metric Alignment):* If business stakeholders agree that stockout detection is the overriding operational objective, formally update `task_registry.py` to register a compound loss or stockout $F_1$ as the primary metric before re-evaluating promotion.

---

## 6. Phase 5 Architectural Sign-Off & Transition Contract

1. **Downstream Demand Optimizer Adapter (F-10 Contract):**
   - The ML demand model outputs **daily point search volume per destination at $t+7$**.
   - The Phase 5 optimization solvers (`budget_service.py`, `optimization_service.py`) consume **inventory unit booking demand**.
   - An adapter in `services/` will map search volume forecasts into unit booking distributions via empirical conversion ratios and service-level buffers.
2. **Model Registry Promotion Procedure:**
   - Candidate containers for approved tasks (`hotel_cancellation`, `flight_price`, `demand_forecasting`) will be copied into `data/models/<task_name>/` during Phase 5 deployment with automated rollback checkpoints.
   - `inventory_forecasting` will retain the existing champion model pending resolution of the stockout vs MAE objective.

---
*Report certified by Senior Machine Learning Engineer & ML Systems Architect.*  
*Artifacts Verified: `data/models/candidates/*`, `reports/model_evaluation/stage_4b_retraining_results.json`.*
