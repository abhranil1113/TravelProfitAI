# Complete Source Code Audit — Stage 13

**Audit Scope:** Full repository inventory, populated module analysis, defect identification, and remediation verification across `c:\Users\AbhranilPal\Programs\Projects\TBO-InventoryIQ`.  
**Syntax Check Result:** `0` Python syntax errors across all populated `.py` modules.  
**Placeholder Marker Scan:** Single abstract base method `NotImplementedError` in `feature_engineering/base_transformer.py:82` (`BaseFeatureTransformer.transform`).

---

## 1. Authoritative Repository Inventory

| Directory | Total Files | Populated | Empty (0-byte scaffolds) | `.py` Files | Populated LOC | Audit Status |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `<root>` | 14 | 10 | 4 | 2 | 123 | Configs, `requirements.txt`, empty `docker-compose.yml`, `Makefile`, `LICENSE`, stray `=` |
| `.github/` | 2 | 0 | 2 | 0 | 0 | Disabled CI scaffolds (`backend-ci.yml.disabled`, `frontend-ci.yml.disabled`) |
| `analytics/` | 14 | 0 | 14 | 0 | 0 | Empty scaffold package (live analytics implemented in `backend/app/services/analytics_service.py` & `eda/`) |
| `backend/` | 171 | 149 | 22 | 146 | 30,717 | Core FastAPI API, ORM (`67` app tables + `alembic_version`), services, RBAC/security, WebSockets, tests |
| `data/` | 232 | 229 | 3 | 0 | 0 | Raw/processed CSV & Parquet datasets + serialized model artifacts (`hotel_cancellation`, `flight_price`, `demand_forecasting`, `inventory_forecasting`) |
| `data_pipeline/` | 46 | 18 | 28 | 18 | 2,475 | Ingestion cleaning & validation engine + legacy empty scaffold submodules |
| `docs/` | 25* | 14* | 11* | 0 | 0 | Technical specs & audit reports (*pre-Stage-13 count; +6 reports added in Stage 13) |
| `eda/` | 12 | 12 | 0 | 12 | 2,870 | Safe data loaders, KPIs, profiling, statistical/leakage checks, plotting |
| `feature_engineering/` | 19 | 19 | 0 | 19 | 2,752 | Hotel, flight, inventory, search, demand, supplier feature builders & leakage detection |
| `frontend/` | 22 | 0 | 22 | 0 | 0 | Unimplemented UI scaffold (`src/`, `package.json`, `Dockerfile` are 0-byte placeholders) |
| `ml_engine/` | 48 | 48 | 0 | 48 | 3,739 | Model artifact registry, drift/metrics monitoring, 4 inference services, optimization adapter |
| `modeling/` | 27 | 27 | 0 | 23 | 3,447 | Chronological splitters, purged CV, baselines, trainer, tuning, evaluation |
| `notebooks/` | 14 | 14 | 0 | 0 | 0 | Exploratory & training Jupyter notebooks |
| `optimization/` | 43 | 30 | 13 | 30 | 3,753 | OR-Tools MILP solvers (`SCIP`/`HIGHS`/`CBC`), economics, PIT candidate builder, risk/CVaR integration |
| `reports/` | 108 | 108 | 0 | 0 | 0 | Generated EDA/validation/modeling markdown, JSON, CSV, and figure outputs |
| `scripts/` | 19 | 14 | 5 | 14 | 2,637 | Pipeline & benchmark runners; 5 empty CLI wrapper scripts (`seed_database.py`, `run_*.py`, `train_models.py`) |
| `tests/` | 63* | 63* | 0 | 63* | 5,990* | Core data/EDA/FE/modeling/optimization suites (*pre-Stage-13 count; `test_stage13_math_verification.py` added) |

---

## 2. Confirmed Defects Remediated in Stage 13

### 2.1 Backend & Real-Time Architecture
1. **Cross-Thread SQLAlchemy Session Corruption (`backend/app/services/notification_service.py`)**:
   - **Defect:** `NotificationService.notify_sync(..., db=db)` scheduled the async `notify()` coroutine via `asyncio.run_coroutine_threadsafe(..., main_loop)` while passing the request thread's synchronous SQLAlchemy `Session` (`db`) and calling `active_session.rollback()` on exceptions inside `finally`/`except`. Under concurrent request thread commits (observed in `POST /api/v1/optimization-runs/{run_id}/retry`), both threads touched the same `Session`, causing `SAWarning: Session.add() during flush`, transaction rollback, and `InvalidRequestError: This session is in 'inactive' state`.
   - **Fix:** Refactored `notify_sync` to perform DB lookups and `Notification`/`NotificationDelivery` persistence synchronously on the caller's thread inside a `begin_nested()` savepoint when `db` is supplied, and dispatch only pure-data async Socket.IO emissions via `_emit_socket_only(...)` returning `NotificationDispatchResult`. Prevented injected caller session rollbacks inside `notify()`.
2. **PostgreSQL `userrole` Enum Transaction Abortion (`backend/app/services/notification_service.py`)**:
   - **Defect:** Role filtering passed non-ORM role labels such as `RoleNames.FINANCE_USER` and `RoleNames.EXECUTIVE` directly into `User.role.in_(resolved_roles)`. SQLite (`VARCHAR`) ignored this, whereas live PostgreSQL aborted transactions with `psycopg2.errors.InvalidTextRepresentation: invalid input value for enum userrole: "FINANCE_USER"` (`InFailedSqlTransaction` cascading thereafter).
   - **Fix:** Filtered target roles against `UserRole._value2member_map_` and cast to `UserRole` enum members prior to querying.
3. **PostgreSQL Phantom-Insert Race on `CANARY` Deployment (`backend/app/services/mlops_service.py`)**:
   - **Defect:** Under PostgreSQL `READ COMMITTED`, `select(ModelDeployment).where(deployment_mode == CANARY, status == ACTIVE).with_for_update()` acquired 0 row locks when no active canary existed yet, allowing concurrent `create_deployment` requests for `MLModelType` to both insert active `CANARY` deployments (proven via live multi-threaded PG test: `2 == 1`).
   - **Fix:** Locked parent `MLModel` rows for `model.model_type` ordered deterministically (`order_by(MLModel.id.asc()).with_for_update()`) before checking `active_canary`.
4. **Supplier Portal Concurrent Idempotency Race (`backend/app/services/supplier_portal_service.py`)**:
   - **Defect:** Concurrent `push_rates_and_availability` requests carrying an identical `Idempotency-Key` could race between checking `SupplierRateSyncLog` and committing, risking duplicate insert conflicts under PostgreSQL concurrency.
   - **Fix:** Acquired a per-supplier `SELECT ... FOR UPDATE` row lock on `Supplier` prior to checking `existing_sync` and upserting offers.
5. **Unhandled HTTP 500 on Empty Catalog Optimization (`backend/app/services/optimization_service.py`)**:
   - **Defect:** Triggering optimization against a fresh/unseeded catalog DB propagated `optimization.exceptions.CurrencyMismatchError` out of `CandidateOpportunityBuilder` as HTTP 500, and persisting extended `RejectionReasonCode` values like `DESTINATION_CAP_BINDING` caused SQLAlchemy `LookupError` when reading `RejectedOpportunity` rows (`SAEnum` only permits 6 codes).
   - **Fix:** Added pre-run active `SupplierOffer` count guard raising HTTP 400 `BadRequestException`, and mapped extended engine rejection codes cleanly to PostgreSQL-safe `RejectionReasonCode` members while preserving the raw code in `reason_detail`.
6. **Production Password-Reset Token Exposure (`backend/app/api/v1/users.py`)**:
   - **Defect:** `POST /api/v1/users/{id}/force-password-reset` unconditionally returned raw `action_token` in JSON responses (`auth.py` redacted it).
   - **Fix:** Returned `action_token=None` when `get_settings().ENVIRONMENT.lower() == "production"`.
7. **Schema, ORM & Lock Fixes Across Services (Wave 2)**:
   - Fixed invalid enum `PipelineStatus.COMPLETED` -> `PipelineStatus.SUCCESS` and duplicate-count key lookups in `pipeline_service.py`.
   - Fixed broken ORM attribute names in `report_service.py`, `health_service.py` (`storage_uri` -> `artifact_dir`), `ml_registry_service.py` (`FeatureSet.model_type` -> `entity_type`), and `mlops_service.py` (case-insensitive `MLModelType`).
   - Changed string ID filter parameters (`supplier_id`, `dest_id`) from `Optional[int]` to `Optional[str]` in `recommendations.py`, `recommendation_service.py`, `procurement.py`, and `procurement_service.py`; moved `PolicyService.enforce_workflow_policies` before `with_for_update()` budget locks in `create_purchase_order` and marked consumed recommendations `ORDERED`.
   - Replaced static mock metrics in `analytics_service.py` with live `OfferPrediction` / `PurchaseOrder` SQL aggregations.
   - Added `.with_for_update()` row locking on run/recommendation/treasury/supplier/policy state mutations and fixed inverted `RefreshToken.replaced_by_token_id` rotation pointer in `auth_service.py`.
   - Wrapped `supplier_offer_service.py` CSV rows in `begin_nested()` savepoints and required explicit `role` JWT claims in `socket_manager.py` plus non-wildcard `SOCKET_IO_CORS_ORIGINS` validation in production `config.py`.

### 2.2 ML Engine, Modeling, Optimization, Data & EDA
1. **Persisted Demand Forecaster Index Mismatch (`ml_engine/demand_forecasting/forecast_service.py` & `modeling/baselines.py`)**:
   - **Defect:** `ColumnTransformer` placed numeric features before categorical columns, moving `lag_1` from raw column index `5` to transformed index `3` (`index 5` was `lag_14`). Unpickled `data/models/demand_forecasting/estimator.joblib` (`NaiveForecaster`) lacked `lag_col_idx_` and defaulted to index `5`, predicting `0.0` whenever `lag_14` was absent (causing `OptimizationPipeline` to compute zero demand and `best_objective_inr == 0.00`).
   - **Fix:** Updated `DemandForecastService.__init__` to resolve `estimator.lag_col_idx_` dynamically via `preprocessor.get_feature_names_out()`, fixed `NaiveForecaster.__setstate__` fallback index to `3`, and aligned `inventory_type` casing before `OrdinalEncoder.transform()`.
2. **Flight Carrier & IATA Code Normalization (`ml_engine/price_prediction/price_prediction_service.py` & `ml_engine/preprocessing/preprocess_flight.py`)**:
   - **Defect:** `PricePredictionService.SUPPORTED_AIRLINES` rejected `"Air_India"` and `"GO_FIRST"` (spaces only) while trained artifacts expected underscores, and `SUPPORTED_CITIES` rejected canonical IATA codes (`DEL`, `BOM`, `BLR`, `MAA`, `HYD`, `CCU`). Also `price_dataset.py` referenced nonexistent `FEATURE_NAMES` instead of `EXPECTED_FEATURES`.
   - **Fix:** Added deterministic alias/IATA normalization while preserving strict rejection of unsupported carriers/routes or missing fields.
3. **Inventory Indicator & Bucket Mismatch (`optimization/predictions/inventory_forecasting.py` & `ml_engine/inventory_forecasting/inventory_forecast_service.py`)**:
   - **Defect:** `InventoryForecastingService` defaulted `availability_bucket` to `"MEDIUM"` and boolean indicators to `"TRUE"`/`"FALSE"` strings despite `preprocessor.joblib` fitting `['Critical', 'High', 'Low', 'Moderate']` and Python `[False, True]` booleans. `ml_engine/inventory_forecasting` also rejected raw snapshots lacking derived deterministic ratio fields even when quantities existed.
   - **Fix:** Mapped availability buckets to fitted labels and coerced boolean flags cleanly while continuing to reject missing historical lag deltas (`days_since_prev_snapshot`, velocities) to prevent fabricated trend assumptions.
4. **Optimization Engine, Solvers & Evaluation (Wave 1)**:
   - Fixed `CandidateOpportunityBuilder` config attribute access (`total_budget`), expanded cache keys with `models_base_dir`, `loader.base_dir`, financial/risk configs, and missing `unique_resolved_inventory_items` key on empty snapshots in `point_in_time.py`.
   - Enforced `hotel_budget_min` / `flight_budget_min` in single-category MILP solvers, fixed solver gap parameter mapping (`SCIP`, `HIGHS`, `CBC`) and feasible zero-objective gap divide-by-zero handling, computed real `gc_lift` in `pipeline.py`, aligned mode-aware budget filters in `baselines.py`/`metrics.py`, and removed fabricated `"0.0% cancellation risk"` prose in `explanations.py`.
5. **EDA, Feature Engineering, Modeling & Data Validation**:
   - Replaced `"purchase_cost"` fallback in `eda/kpi_calculations.py` (`avg_margin_pct`) and `feature_engineering/aggregation.py` (`avg_supplier_margin_pct`) with genuine margin-percentage math `(selling - cost) / selling * 100`.
   - Extended `data_pipeline/validation/validation_report.py` to evaluate duplicates, business rules, and outliers across `processed` datasets as well as `raw` datasets (`stage="raw"`/`"processed"`).
   - Fixed chronological sorting prior to train/test & CV splits in `modeling/pipeline.py` & `cross_validator.py`, wired `PurgedGroupTimeSeriesSplit`, and fixed lowercase `flight_operations_features` leakage rules and `bin_series` null handling.

---

## 3. Known Architectural Scaffolds & Intentional Caveats
- **Empty Scaffolds:** `frontend/` (22 empty files), `analytics/` (14 empty files), root ops stubs (`docker-compose.yml`, `Makefile`, `LICENSE`, `.github/workflows/*.disabled`), and CLI wrappers in `scripts/` remain unimplemented placeholders outside the FastAPI backend + ML/optimization core.
- **Unmodified Test Divergences (Preserved Without Weakening):**
  1. `tests/optimization/test_point_in_time_and_ml.py::TestPointInTimeAndML::test_hotel_cancellation_adr_scaling` supplies only `{travel_date, selling_price, cost_per_unit}` and fails with `TypeError` because `HotelCancellationService` enforces Stage 4c zero-fabrication (`REQUIRED_BOOKING_FIELDS` missing -> returns `None`).
  2. `backend/tests/test_workflows.py::test_workflow_b_reference_and_ml` expects `"PENDING"` after `POST /api/v1/pipelines/batches` for nonexistent `"data/rates.csv"`, whereas synchronous execution (`PipelineService.trigger_batch`) marks it `"FAILED"`.
- **Legacy On-Disk Demand Artifact:** `data/models/demand_forecasting/estimator.joblib` remains `NaiveForecaster`; however runtime index resolution via `preprocessor.get_feature_names_out()` restores true `lag_1` prediction behavior without invalidating disk checksum manifests.
