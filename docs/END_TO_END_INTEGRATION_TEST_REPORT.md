# End-to-End Integration Test Report — Stage 13

**Execution Environment:** Windows 10/11, Python 3.10.0, pytest 8.3.4; FastAPI `TestClient` (SQLite `:memory:` for unit/API regression) + Live PostgreSQL `127.0.0.1:5432/Travelprofitai` (for real DB locking & Alembic schema verification).  
**Final Authoritative Post-Edit Test Run (`task-1269`):**
- **`tests/` (ML, Optimization, FE, EDA, Data Quality):** **`261 passed, 1 failed`** (`262` collected, `102.09s`) — improved from `252 passed, 5 failed` baseline + `5` new Stage 13 math tests.
- **`backend/tests/` (API, Services, RBAC, Notifications, PostgreSQL Concurrency):** **`96 passed, 1 failed`** (`97` collected, `119.64s`) — improved from `86 passed, 6 failed` baseline + `5` new Stage 13 API & PG concurrency tests.
- **Combined Total:** **`357 passed, 2 failed` (`359` total tests collected)**.

---

## 1. Suite-by-Suite Breakdown (`backend/tests/` & `tests/`)

| Suite Category | Collected | Passed | Failed | Notes / Verification Highlights |
| :--- | ---: | ---: | ---: | :--- |
| `tests/data_quality/*` | 36 | 36 | 0 | Cleaning, outlier, schema, ID consistency, and audit reconciliation |
| `tests/eda/*` | 48 | 48 | 0 | Currency isolation, KPI calculations (post margin fix), snapshots, charts |
| `tests/feature_engineering/*` | 29 | 29 | 0 | Dataset builder, date/demand/hotel/flight/inventory/search/supplier features & leakage |
| `tests/modeling/*` | 67 | 67 | 0 | Baselines, purged CV, evaluator, registry, `ml_engine` 22/22 verification |
| `tests/optimization/*` | 82 | 81 | 1 | `test_solvers` (7/7), `test_pipeline`, `test_config`, `test_stage13_math_verification` (5/5) pass; `test_hotel_cancellation_adr_scaling` fails on intentional anti-fabrication guard |
| `backend/tests/` Core & Enterprise | 97 | 96 | 1 | All 249 `APIRoute`s covered; Socket.IO `16/16`, `test_remediation_regression` `8/8`, `test_stage11a_regression` `6/6`, `test_stage13_api_coverage` `4/4`, `test_stage13_postgres_concurrency_e2e` `1/1` pass; `test_workflow_b_reference_and_ml` fails on legacy `PENDING` assertion |

---

## 2. End-to-End Business Workflow Coverage

| Workflow | Status | Verified Path & Assertions |
| :--- | :--- | :--- |
| **WF-1: Auth -> Password Reset -> Refresh Rotation** | **PASS** | User register/login, JWT expiry/revocation, refresh token rotation & reuse detection (`test_auth.py`, PG concurrency suite) |
| **WF-2: Supplier & Inventory Catalog -> Bulk CSV Import -> Optimization -> Approval -> PO -> Fulfillment** | **PASS** | Multi-supplier/destination DB catalog (`seeded_optimization_db`), SCIP MILP optimization, scorecard, compare, approve, PO generation, partial/over-delivery guard (`test_optimization.py`, `test_remediation_regression.py`, `test_workflows.py::test_workflow_c`, `test_stage2_catalog.py`) |
| **WF-3: Real CSV Ingestion Batch** | **PASS** (`new CSV`) / **Legacy Failure** (`missing file`) | Valid CSV upload succeeds (`SUCCESS`, `rows_ingested=2`, `rows_duplicates_removed=1` in `test_stage13_api_coverage.py`); legacy `test_workflow_b_reference_and_ml` fails because missing `"data/rates.csv"` accurately returns `FAILED` instead of `PENDING` |
| **WF-4: Forecast Materialization -> Demand Chart** | **PASS** | Daily metrics materialized into demand/inventory forecasts with `OptimizationConfig` fix (`test_forecasts.py`) |
| **WF-5: Risk Scenario -> Correlation Cholesky -> Stress Test -> CVaR Optimization -> Comparison** | **PASS** | PSD scenario validation, stress test execution, Rockafellar-Uryasev CVaR optimization (`min_availability_target_pct`, `min_demand_fulfillment_pct`), risk-adjusted comparison (`test_enterprise_apis_rbac.py`, `test_enterprise_domains_services.py`) |
| **WF-6: MLOps Worker Drift (PSI/KS) -> Shadow Log -> Canary -> Governed Promote -> Rollback -> Cache Invalidation** | **PASS** | Trusted `X-Worker-Token` PSI/KS drift + freshness checks, 0%-impact SHADOW isolation, CANARY PG lock serialization, drift-gated promote/rollback, `ModelRegistry` cache clear (`test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py`, PG test) |
| **WF-7: Supplier Portal Credential -> Rate Push -> Rotation/Revoke -> Onboarding -> Settlement Netting** | **PASS** | One-time secret reveal, old-key 401 after rotation, cross-supplier rejection, onboarding stage progression (`INITIATED` -> `DOCUMENT_REVIEW`), PO netting batch approve -> settle (`test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py`) |
| **WF-8: FX Forward Draft -> Execute -> Settle/Cancel -> Exposure Snapshot -> Margin Breach Alert -> Hedge Effectiveness** | **PASS** | Expired FX rejection (400), Decimal exposure snapshot, IFRS/IAS dollar-offset logging, margin rule breach alert generation & ack |
| **WF-9: Policy AST Rule -> Block Recommendation/PO -> Submit Exception -> SoD Enforcement -> Compliance Audit** | **PASS** | AST validation, workflow blocking (`403`), PM exception submission, Admin self-approval block (`403`), cross-admin waiver -> unblock, compliance audit (`test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py`) |
| **WF-10: Empty DB Catalog Optimization Safety** | **PASS** | Unseeded DB returns deterministic HTTP `400 BadRequestException` ("No active supplier offers available in database") instead of unhandled HTTP 500 `CurrencyMismatchError` (`test_stage13_api_coverage.py`) |
| **WF-11: Notification Persistence, Preference Opt-Out & Socket.IO Delivery** | **PASS** | Real-time threadpool dispatch (`test_stage11a_regression.py`), idempotency dedup, read/acknowledge, user preference opt-out (`test_socketio_notifications.py`, `test_notifications.py`) |

---

## 3. Exact Explanations of Remaining 2 Pre-Existing Failures

1. **`tests/optimization/test_point_in_time_and_ml.py::TestPointInTimeAndML::test_hotel_cancellation_adr_scaling`**:
   - Passes minimal dict `{"travel_date": "2026-07-01", "selling_price": 4500.0, "cost_per_unit": 3800.0}` lacking `REQUIRED_BOOKING_FIELDS`. `HotelCancellationService.predict_cohort_cancellation_probability` intentionally returns `None` rather than fabricating synthetic guest cohorts, raising `TypeError: '<=' not supported between instances of 'float' and 'NoneType'`. Kept intentionally unweakened.
2. **`backend/tests/test_workflows.py::test_workflow_b_reference_and_ml`**:
   - Submits `"file_path": "data/rates.csv"` (nonexistent on disk) to `POST /api/v1/pipelines/batches` and asserts `batch["status"] == "PENDING"`. Because commit `ee93841` switched `PipelineService.trigger_batch` from a stub to real synchronous cleaning (`_execute_batch_cleaning`), missing source files return `"FAILED"`. Kept intentionally unweakened.
