# Stage 4A.1 — Independent ML Remediation Verification & Production Readiness Audit Report

**Author:** Principal ML Systems Auditor & Independent Quality Reviewer  
**Audit Scope:** Independent verification of all Stage 4A remediations across Hotel Cancellation, Flight Price, Demand Forecasting, Inventory Forecasting, Pipeline Quality Gates, and Model Persistence.  
**Audit Protocol:** Static source-code tracing, data structure inspection, and mathematical formula verification. Zero test execution, zero model training, zero dataset modification.

---

## 1. Domain 1: Hotel Cancellation Prediction

### 1.1 Full-Dataset Target Encodings Exclusion
- **Exact File & Line:** [feature_engineering/hotel_features.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/feature_engineering/hotel_features.py#L22-L44)
- **Observed Behavior:** 
  `market_segment_historical_cancel_rate` and `deposit_type_historical_cancel_rate` were removed from `PRE_BOOKING_FEATURE_COLUMNS` and placed into `ANALYTICAL_REFERENCE_COLUMNS`. In `transform()`, these columns are still computed on the full dataset using Bayesian smoothing priors over the entire target vector `df["is_canceled"]`.
  In [modeling/configs/hotel_cancellation.yaml](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/configs/hotel_cancellation.yaml#L21-L32) and [modeling/registry/task_registry.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/registry/task_registry.py#L121-L132), both columns are explicitly registered in `excluded_columns`.
  In [modeling/target_builder.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/target_builder.py#L180-L195), `prepare_task_dataset()` excludes all `excluded_columns` from `X`.
- **Status:** **VERIFIED** for `run_task_pipeline()`.
- **Remaining Risk & Bypass Vulnerability:** If a developer or script directly calls `train_single_model(estimator, preprocessor, X_train, y_train)` or `execute_cross_validation(task_config, model_name, X, y)` without first passing through `prepare_task_dataset()`, neither `train_single_model()` nor `execute_cross_validation()` invokes `audit_task_leakage()`.
- **Recommended Correction:** Add a mandatory call to `audit_task_leakage(task_config, X)` at the entry point of `execute_cross_validation()`.
- **Approval Required:** No (Internal ML hardening).

### 1.2 Chronological Validation Timestamp Analysis
- **Exact File & Line:** [feature_engineering/hotel_features.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/feature_engineering/hotel_features.py#L75-L80)
- **Observed Behavior:**
  ```python
  arrival_dt = pd.to_datetime(df["arrival_date"])
  booking_dt = arrival_dt - pd.to_timedelta(out["lead_time_days"], unit="D")
  out["booking_date"] = booking_dt.dt.strftime("%Y-%m-%d")
  ```
  The column `booking_date` is **synthesized** by subtracting `lead_time_days` from `arrival_date`.
- **Status:** **PARTIALLY VERIFIED WITH DOCUMENTED LIMITATION**.
- **Proof & Finding:**
  The raw hotel bookings dataset does **not** contain an actual transaction timestamp column (no `created_at`, no booking timestamp, no hour/minute/second of reservation).
  Therefore, claiming that the model undergoes "actual booking-time validation" is factually incorrect. The validation order is based on a **mathematically reconstructed reservation date**.
  *Specific Artifacts of Synthesis:*
  1. For bookings with `lead_time_days = 0`, `booking_date` exactly equals `arrival_date`.
  2. For extreme lead times (e.g. 700+ days), `booking_date` stretches back to 2013-06-24, whereas hotel operational stays run from July 2015 to August 2017.
  3. Cancellations that occurred after booking are recorded at `reservation_status_date`, which cannot be used for splitting without post-event target leakage.
- **Valid Alternative:**
  Acknowledge `booking_date` as a *Synthesized Transaction Proxy Date*. For true production deployment, point-in-time reservation transaction timestamps must be logged at ingestion.
- **Approval Required:** Yes (Clarification of architectural claims in documentation and audit reports).

### 1.3 Validation-Based Threshold Selection vs Test Data
- **Exact File & Line:** [modeling/evaluator.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/evaluator.py#L56-L74) and [modeling/pipeline.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/pipeline.py#L151)
- **Observed Behavior:**
  In `pipeline.py`:
  ```python
  test_evaluation = evaluate_test_set(task_cfg, champion_artifact, X_test, y_test)
  ```
  In `evaluator.py`:
  ```python
  def evaluate_test_set(task_config, artifact, X_test, y_test):
      ...
      if probs is not None:
          cost_opt = optimize_classification_threshold(y_test_arr, probs, cost_fn=cost_fn, cost_fp=cost_fp)
          evaluation_report["cost_optimal_threshold"] = {
              "optimal_threshold": cost_opt["optimal_threshold"],
              ...
          }
  ```
- **Status:** **NOT SATISFIED (CRITICAL DEFECT)**.
- **Finding:**
  `optimize_classification_threshold()` is invoked directly on `y_test_arr` (the untouched final holdout test set)!
  This violates holdout validation principles: the decision threshold is selected post-hoc on the test set, rather than being tuned strictly on out-of-fold validation predictions or an isolated validation partition and then applied out-of-sample to `X_test`.
- **Remaining Risk:** Severe data leakage in evaluation metrics. The reported threshold and minimal business cost reflect test-set overfitting.
- **Recommended Correction:**
  1. Execute `optimize_classification_threshold()` on the out-of-fold validation predictions from `execute_cross_validation()` (or a dedicated validation split `X_val`, `y_val`).
  2. Store the resulting threshold $T^*$ in `champ_summary`.
  3. In `evaluate_test_set()`, apply this fixed $T^*$ to `X_test` without re-optimizing.
- **Approval Required:** No (Bug fix for evaluation methodology).

---

## 2. Domain 2: Customer Demand Forecasting

### 2.1 Absence of Future-Looking Interpolation or Backward Fill
- **Exact File & Line:** [modeling/target_builder.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/target_builder.py#L60-L64)
- **Observed Behavior:**
  ```python
  reindexed["avg_search_price"] = reindexed["avg_search_price"].ffill().fillna(0.0)
  ```
  A global search across the entire `modeling/` directory confirmed 0 occurrences of `.bfill()`, `backfill`, or `interpolate()`.
- **Status:** **VERIFIED**.

### 2.2 PurgedGroupTimeSeriesSplit Boundary Calculations & Group Handling
- **Exact File & Line:** [modeling/splitters.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/splitters.py#L38-L82), [modeling/cross_validator.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/cross_validator.py#L110), and [modeling/pipeline.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/pipeline.py#L70-L75)
- **Observed Behavior:**
  In `target_builder.py`:
  `panel_records` are appended per group `(destination_id, inventory_type)` and concatenated via `pd.concat(panel_records, ignore_index=True)`.
  The resulting dataframe is **entity-major** (DEST001 records for all dates, then DEST002 for all dates, etc.). It is never sorted globally by `date`.
  In `cross_validator.py` line 110:
  ```python
  split_gen = splitter.split(X, y if is_classifier else None)
  ```
  Notice that `groups` is **never passed** to `splitter.split()`!
  In `PurgedGroupTimeSeriesSplit.split(X, y, groups=None)`:
  ```python
  if groups is not None:
      ...
  else:
      ts = TimeSeriesSplit(n_splits=self.n_splits, gap=self.embargo_gap)
      yield from ts.split(X, y)
  ```
  Because `groups is None`, it falls back to scikit-learn's row-based `TimeSeriesSplit(gap=7)`.
- **Status:** **NOT SATISFIED (CRITICAL DEFECT)**.
- **Proof & Finding:**
  1. Because `groups` is not passed, the custom `PurgedGroupTimeSeriesSplit` date logic is completely dead code during cross-validation.
  2. Scikit-learn's `TimeSeriesSplit(gap=7)` treats `gap=7` as **7 rows**, not 7 calendar days!
  3. Because `X` is entity-major, fold 1 trains on DEST001 (all dates) and validates on DEST002 (all dates). This creates an entity holdout with 100% calendar date overlap across folds!
  4. In `pipeline.py`, `split_idx = int(len(X) * 0.85)` puts DEST001–DEST009 in train and DEST009–DEST010 in test, causing total temporal contamination.
- **Recommended Correction:**
  1. In `prepare_task_dataset()`, sort the final panel globally by calendar date: `panel_clean = panel_df.sort_values("date").reset_index(drop=True)`.
  2. In `cross_validator.py`, pass `groups=df_full["date"]` into `splitter.split(X, y, groups=groups)`.
  3. In `pipeline.py`, partition train and test by unique calendar dates (e.g. `split_date = dates.quantile(0.85)`), enforce a 7-day embargo buffer, and assign train/test masks based on global date boundaries.
- **Approval Required:** No (Bug fix for cross-validation engine).

### 2.3 Embargo Gap Consistency Across Evaluation, CV, and Tuning
- **Exact File & Line:** [modeling/hyperparameter_tuning.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/hyperparameter_tuning.py#L69-L75)
- **Observed Behavior:**
  In `hyperparameter_tuning.py`:
  ```python
  splitter = get_cross_validation_splitter(
      task_config.validation_strategy,
      n_splits=cv_splits,
      shuffle=(not is_time_based),
      random_state=RANDOM_SEED,
  )
  ```
  Notice that `gap` is **not passed** to `get_cross_validation_splitter()` in `hyperparameter_tuning.py` (it defaults to `gap=0`)!
- **Status:** **NOT SATISFIED (CRITICAL DEFECT)**.
- **Finding:**
  While `cross_validator.py` retrieves `gap = task_config.business_params.get("embargo_gap_days", 0)`, `hyperparameter_tuning.py` does not retrieve `embargo_gap_days` and passes `gap=0`. Consequently, hyperparameter tuning uses zero embargo gap, while cross-validation attempts to use 7.
- **Recommended Correction:**
  Update `hyperparameter_tuning.py` to retrieve `gap = task_config.business_params.get("embargo_gap_days", 0)` and pass it into `get_cross_validation_splitter()`.
- **Approval Required:** No (Bug fix).

### 2.4 Traceability Metadata Exclusion from Predictors
- **Exact File & Line:** [modeling/target_builder.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/target_builder.py#L180-L195)
- **Observed Behavior:**
  `date`, `forecast_origin_date`, and `target_date` are added to `meta_cols_to_drop` and excluded from `X`.
  `audit_task_leakage()` validates that none of these columns exist in `X` and raises `ValueError` if detected.
- **Status:** **VERIFIED**.

### 2.5 Downstream Optimizer Target Semantics & Units
- **Exact File & Line:** [optimization/predictions/demand_forecasting.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/optimization/predictions/demand_forecasting.py#L40-L63)
- **Observed Behavior:**
  The ML model is trained on `future_search_volume_7d = vol.shift(-7)` (point volume on day $t + 7$).
  The downstream optimizer in `DemandForecastingService` computes a 30-day historical window average scaled to a 7-day rate:
  ```python
  horizon_rate = float(count) * (horizon_days / max(1.0, (opt_ts - recent_cutoff).days))
  ```
  Furthermore, `predict_future_search_volume()` pulls directly from `self._panel_cache` (computed from raw search events) and completely ignores the loaded ML estimator `self.estimator`!
- **Status:** **PARTIALLY VERIFIED WITH DOCUMENTED ARCHITECTURAL DISCONNECT**.
- **Finding:**
  1. Unit and semantics mismatch: ML predicts instantaneous daily searches at $t+7$, whereas Phase 5 optimization requires aggregate volume across the full 7-day procurement window.
  2. The trained ML model is completely bypassed by the downstream service at runtime.
- **Recommended Correction:**
  Formalize whether Phase 5 intends to consume:
  - Aggregate 7-day cumulative searches: $y = \sum_{k=1}^7 \text{vol}_{t+k}$, or
  - Point demand rate: $y = \text{vol}_{t+7}$.
  Update `DemandForecastingService` to invoke `self.estimator.predict()` once semantics are aligned.
- **Approval Required:** Yes (Business logic & Phase 5 contract decision).

---

## 3. Domain 3: Inventory Availability & Stockout Forecasting

### 3.1 Snapshot Sorting & Duplicate Timestamp Analysis
- **Exact File & Line:** [modeling/target_builder.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/target_builder.py#L115-L118)
- **Observed Behavior:**
  ```python
  sort_cols = ["inventory_id", "travel_date", "snapshot_date"]
  if "snapshot_id" in df_work.columns:
      sort_cols.append("snapshot_id")
  df_work = df_work.sort_values(sort_cols).reset_index(drop=True)
  ```
  Dataset inspection showed 0 duplicate `(inventory_id, travel_date, snapshot_date)` records in `inventory_features.parquet`.
- **Status:** **VERIFIED WITH ARCHITECTURAL CLARIFICATION**.
- **Finding:**
  `snapshot_id` provides **deterministic tie-breaking** (preventing non-deterministic row permutations across platforms), but it cannot guarantee true temporal sub-daily ordering unless `snapshot_id` is monotonically assigned at observation time.
- **Approval Required:** No.

### 3.2 Metadata Exclusion
- **Exact File & Line:** [modeling/target_builder.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/target_builder.py#L180-L195)
- **Observed Behavior:**
  `snapshot_date`, `forecast_origin_snapshot_date`, `future_snapshot_date`, `actual_stockout`, and `future_booked_quantity` are dropped from `X` and enforced via `audit_task_leakage()`.
- **Status:** **VERIFIED**.

### 3.3 Stockout Threshold Configuration Alignment
- **Exact File & Line:** [task_registry.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/registry/task_registry.py#L225), [inventory_forecasting.yaml](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/configs/inventory_forecasting.yaml#L25), [target_builder.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/target_builder.py#L162), [metrics.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/metrics.py#L325), [evaluator.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/evaluator.py#L115)
- **Observed Behavior:**
  All components now uniformly resolve `stockout_threshold_units` or fallback to `stockout_threshold` with default `5.0`.
- **Status:** **VERIFIED**.

### 3.4 ROOM_NIGHT and SEAT Subgroup Metrics
- **Exact File & Line:** [modeling/evaluator.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/evaluator.py#L125-L144)
- **Observed Behavior:**
  `evaluator.py` checks `if "unit_type" in X_test.columns` and computes separate regression and stockout metrics for `ROOM_NIGHT` ($N=1,992$) and `SEAT` ($N=1,758$).
- **Status:** **VERIFIED**.
- **Remaining Risk:** Both units currently use a flat threshold of 5.0 units. A 5-seat buffer represents ~2-3% of aircraft capacity, whereas 5 rooms can represent 25% of a boutique hotel. Unit-specific thresholds should be parameterized in Phase 5.
- **Approval Required:** No.

---

## 4. Domain 4: Pipeline and Validation Quality Gates

### 4.1 Training Entry Points and Fail-Closed Validation
- **Exact File & Line:** [modeling/pipeline.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/pipeline.py#L64-L66)
- **Observed Behavior:**
  `run_task_pipeline()` enforces:
  ```python
  val_report = validate_modeling_features(X, fail_closed=True)
  leakage_report = audit_task_leakage(task_cfg, X)
  ```
- **Status:** **PARTIALLY VERIFIED**.
- **Finding:**
  Mandatory fail-closed validation is enforced when executing via `run_task_pipeline()`.
  However, standalone scripts (e.g. `scripts/execute_phase4_final_validation.py`) and direct calls to `execute_cross_validation()` do not invoke these checks.
- **Recommended Correction:** Embed `audit_task_leakage()` directly inside `execute_cross_validation()`.
- **Approval Required:** No.

### 4.2 Error Gate Coverage (Infinity, Missingness, Leakage, Target)
- **Exact File & Line:** [modeling/feature_validation.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/feature_validation.py#L65-L70)
- **Observed Behavior:**
  - Missingness $> 50\%$ -> raises `ValueError` (**VERIFIED**).
  - Infinite values -> raises `ValueError` (**VERIFIED**).
  - Target or excluded features in $X$ -> raises `ValueError` (**VERIFIED**).
  - Zero-variance constant features -> reported in report dictionary, but `is_valid` remains `True` and does not raise `ValueError`.
- **Status:** **VERIFIED**.

### 4.3 Silent Shift of Validation Window Under Temporal Sampling
- **Exact File & Line:** [modeling/pipeline.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/pipeline.py#L52-L72)
- **Observed Behavior:**
  ```python
  if sample_size is not None and len(X) > sample_size:
      if is_temporal:
          X = X.iloc[-sample_size:].copy().reset_index(drop=True)
          y = y.iloc[-sample_size:].copy().reset_index(drop=True)
  ...
  if is_temporal:
      split_idx = int(len(X) * 0.85)
      X_train, X_test = X.iloc[:split_idx].copy()..., X.iloc[split_idx:].copy()...
  ```
- **Status:** **NOT SATISFIED (CRITICAL DEFECT)**.
- **Proof & Finding:**
  If a developer specifies `sample_size = 2000` on a 100,000-row time-series dataset:
  1. The code slices the last 2,000 rows (e.g., August 2017).
  2. It then recalculates `split_idx = 2000 * 0.85 = 1700`.
  3. `X_train` becomes rows 0..1700 of the sample, and `X_test` becomes rows 1700..2000 (e.g. late August 2017).
  The intended holdout test window (the final 15% of the overall dataset timeline, e.g. February to August 2017) has been **silently compressed and shifted** into a 300-row window at the very end of August!
- **Recommended Correction:**
  In `pipeline.py`, partition the full dataset into `X_train_full` and `X_test_holdout` first using fixed calendar date cutoffs. Only sample from `X_train_full` for rapid prototyping, leaving `X_test_holdout` fixed and uncompressed.
- **Approval Required:** No (Correction to pipeline orchestration).

### 4.4 Preprocessor Fitting Strictly on Training Folds
- **Exact File & Line:** [modeling/cross_validator.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/cross_validator.py#L115-L135)
- **Observed Behavior:**
  Inside each CV fold, `build_preprocessor()` creates a fresh transformer instance. `train_single_model()` executes `preprocessor.fit_transform(X_train)`, and `artifact.predict(X_val)` executes `preprocessor.transform(X_val)`.
  In `hyperparameter_tuning.py`, the preprocessor is wrapped inside a Pipeline and fitted within CV splits.
- **Status:** **VERIFIED**.

---

## 5. Domain 5: Artifact Provenance & Model Governance

### 5.1 Dataset Content Fingerprinting vs Schema Hashing
- **Exact File & Line:** [modeling/model_persistence.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/model_persistence.py#L27-L38)
- **Observed Behavior:**
  ```python
  schema_str = f"{dataset_name}:{record_count}:{','.join(sorted(feature_names))}"
  digest = hashlib.sha256(schema_str.encode("utf-8")).hexdigest()
  ```
- **Status:** **PARTIALLY VERIFIED WITH ARCHITECTURAL DISTINCTION**.
- **Finding:**
  The function calculates a SHA-256 digest of column names, dataset name, and record count.
  It is a **schema-level digest**, NOT a data-content hash. If underlying values in the dataset change without altering column names or row counts, the digest remains identical.
- **Recommended Correction:**
  For true dataset provenance, compute a checksum of the raw parquet file or sample 1,000 data rows to generate a true data content fingerprint.
- **Approval Required:** No.

### 5.2 Metadata Persistence Parameter Omission
- **Exact File & Line:** [modeling/pipeline.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/pipeline.py#L154-L160)
- **Observed Behavior:**
  In `pipeline.py`:
  ```python
  save_model_artifact(
      champion_artifact,
      task_cfg,
      cv_summary=champ_summary,
      test_metrics=test_evaluation["metrics"],
      selection_rationale=rationale,
  )
  ```
  `save_model_artifact()` defines optional parameters `dataset_records_count` and `date_ranges`, but `pipeline.py` never passes them!
- **Status:** **NOT SATISFIED (DEFECT)**.
- **Finding:**
  In generated `metadata.json` files, `dataset_fingerprint["record_count"]` is saved as `null`, and `date_ranges` is saved as `{}`.
- **Recommended Correction:**
  Update `pipeline.py` to pass `dataset_records_count=len(X)` and `date_ranges={"min_date": ..., "max_date": ...}` into `save_model_artifact()`.
- **Approval Required:** No.

### 5.3 Multi-File Atomic Persistence Integrity
- **Exact File & Line:** [modeling/model_persistence.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/modeling/model_persistence.py#L70-L80)
- **Observed Behavior:**
  ```python
  joblib.dump(artifact.estimator, tmp_estimator, compress=3)
  os.replace(tmp_estimator, estimator_path)  # Step 1: estimator replaced!

  if artifact.preprocessor is not None:
      joblib.dump(artifact.preprocessor, tmp_preprocessor, compress=3)
      os.replace(tmp_preprocessor, preprocessor_path)  # Step 2: preprocessor replaced!
  ...
  os.replace(tmp_metadata, metadata_path)  # Step 3: metadata replaced!
  ```
- **Status:** **PARTIALLY VERIFIED (ATOMIC AT FILE LEVEL, NON-ATOMIC AT CONTAINER LEVEL)**.
- **Finding:**
  Each individual file write is atomic via `os.replace`.
  However, the multi-file container is non-atomic. If the process terminates or crashes during Step 2 (preprocessor write), `estimator.joblib` has already replaced the champion, but `preprocessor.joblib` and `metadata.json` remain from the previous run. The resulting artifact bundle is mismatched and corrupted.
- **Recommended Correction:**
  Write all three files into a temporary staging directory `target_dir / ".staging_<timestamp>"`, and only swap files or rename the directory after all dumps successfully complete.
- **Approval Required:** No.

### 5.4 Preservation of Existing Champion Artifacts
- **Exact File & Line:** Directory `data/models/`
- **Observed Behavior:**
  Inspection of file system modification times confirmed all 5 model directories (`demand_forecasting`, `flight_price`, `hotel_cancellation`, `inventory_forecasting`, `supplier_lead_time_prediction`) have timestamps from Mon Nov 23 and Tue Nov 24.
- **Status:** **VERIFIED**. Zero artifacts were modified or overwritten.

---

## 6. Domain 6: Test Suite and Verification Restrictions

### 6.1 Test Suite Edge Case Coverage
- **Observed Behavior:**
  Unit tests were authored in `tests/modeling/` for leakage fail-closed behavior, zero lookahead in demand price aggregation, deterministic inventory sorting, stockout metrics, and persistence.
- **Status:** **PARTIALLY VERIFIED**.
- **Finding:**
  The new tests verify components in isolation with synthetic inputs, but do **not** cover:
  1. Full panel pipeline execution with entity-major ordering.
  2. Passing `groups` to `PurgedGroupTimeSeriesSplit` inside `execute_cross_validation()`.
  3. Validating that threshold optimization does not evaluate on test sets.
  4. Non-atomic multi-file serialization crashes.
  In strict accordance with project instructions, test suites were **not executed** and are acknowledged strictly as static AST-verified syntax checks.

---

## 7. Master Finding-by-Finding Matrix

| Finding ID | Exact File & Function | Relevant Implementation Behavior | Audit Verification Status | Remaining Risk & Recommended Correction | Approval Required |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F-01** | `modeling/evaluator.py:evaluate_test_set` | Invokes `optimize_classification_threshold(y_test_arr, probs)` on the final holdout test set. | **NOT SATISFIED** | Threshold is tuned directly on test data (data leakage). Optimize on validation predictions only; apply fixed $T^*$ to test set. | No |
| **F-02** | `modeling/splitters.py:PurgedGroupTimeSeriesSplit` & `modeling/cross_validator.py` | `splitter.split(X, y)` called without `groups`; falls back to row-based `TimeSeriesSplit(gap=7)`. | **NOT SATISFIED** | CV split ignores calendar dates; treats 7-day embargo as 7 flat rows. Pass `groups=dates` to `splitter.split()`. | No |
| **F-03** | `modeling/target_builder.py:prepare_task_dataset` | Demand forecasting panel concatenated per group; entity-major ordering (DEST001..DEST010). | **NOT SATISFIED** | Slicing at 85% produces an entity holdout (DEST010) instead of a chronological test set. Sort panel globally by `date`. | No |
| **F-04** | `modeling/hyperparameter_tuning.py:tune_model_hyperparameters` | `get_cross_validation_splitter` called without `gap`; defaults to `gap=0`. | **NOT SATISFIED** | Hyperparameter tuning operates with zero embargo gap. Retrieve `embargo_gap_days` from config. | No |
| **F-05** | `modeling/pipeline.py:run_task_pipeline` | `X = X.iloc[-sample_size:]` takes tail slice before 85% split. | **NOT SATISFIED** | Temporal sampling silently compresses and shifts the holdout test window. Fix test partition first; sample only from train. | No |
| **F-06** | `modeling/pipeline.py:run_task_pipeline` | Calls `save_model_artifact()` without passing `dataset_records_count` or `date_ranges`. | **NOT SATISFIED** | Metadata records `null` for record count and empty dictionary for date ranges. Pass metadata explicitly. | No |
| **F-07** | `modeling/model_persistence.py:save_model_artifact` | Replaces `estimator.joblib` before `preprocessor.joblib` and `metadata.json`. | **PARTIALLY VERIFIED** | Container-level non-atomicity: process crash during preprocessor dump leaves mismatched artifacts. Use staging directory. | No |
| **F-08** | `modeling/model_persistence.py:compute_dataset_fingerprint` | Hashes dataset name, record count, and sorted column names. | **PARTIALLY VERIFIED** | Hashes schema only, not data content. Acknowledge as schema digest or implement content checksum. | No |
| **F-09** | `feature_engineering/hotel_features.py:transform` | `booking_date = arrival_date - lead_time_days`. | **PARTIALLY VERIFIED** | Synthesized proxy date, not an observed system booking timestamp. Document as synthesized transaction date. | Yes |
| **F-10** | `optimization/predictions/demand_forecasting.py` | `DemandForecastingService` uses empirical 30-day raw search count, bypassing ML model. | **PARTIALLY VERIFIED** | Target semantics mismatch (point volume at $t+7$ vs 7-day cumulative rate). Downstream service ignores ML model. Reconcile Phase 5 contract. | Yes |

---

## 8. Final Production Readiness Decision

### **DECISION: NOT READY FOR CONTROLLED RETRAINING**

### Justification:
While critical data leakage paths (such as the exclusion of `market_segment_historical_cancel_rate`, `deposit_type_historical_cancel_rate`, and future `.bfill()` lookahead) were successfully removed in Stage 4A, this independent audit uncovered **critical architectural defects** in the validation and evaluation harness:

1. **Test-Set Threshold Optimization (F-01):** Evaluating decision thresholds directly on `X_test` contaminates holdout metrics.
2. **Entity-Major Grouped CV & Embargo Bypass (F-02, F-03, F-04):** The demand forecasting panel is ordered by entity rather than globally by date, and `cross_validator.py` fails to pass `groups` to `PurgedGroupTimeSeriesSplit`. This causes cross-validation to fall back to flat 7-row splits with full calendar overlap across destinations.
3. **Silent Test Window Shifting under Sampling (F-05):** Sampling truncates the dataset tail, invalidating the intended chronological holdout window.
4. **Incomplete Metadata Provenance (F-06):** Core provenance fields (`record_count`, `date_ranges`) are omitted during persistence.

Proceeding with model retraining before resolving these 4 defects would produce invalid, overfitted, and misleading validation benchmarks.

**Required Action:** Remediate findings F-01 through F-06 in code before authorizing Phase 4B model retraining.
