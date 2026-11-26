# Stage 12 — Enterprise Domain & Full Backend Test Report

**Execution Timestamp:** `2026-11-26`  
**Command Executed:** `python -m pytest backend/tests -v --tb=short` (run after final code and test remediation edits)  
**Test Environment:** In-memory SQLite (`sqlite:///:memory:` with `StaticPool` in `backend/tests/conftest.py`), FastAPI `TestClient`, HiGHS MILP solver (`OR-Tools` / `highs`). Live PostgreSQL schema and Alembic revision (`9a12bccfc7cb`) were verified separately via SQLAlchemy inspection.

---

## 1. Executive Test Summary

- **Total Tests Collected:** `92` across `30` test files
- **Passed:** `86` (`21/21` across the three enterprise test suites; `65/71` across pre-existing test suites)
- **Failed:** `6` (all `6` are pre-existing baseline failures outside the five new enterprise domains; verified identical before any Stage 12 edits)
- **Skipped / Errors:** `0` skipped, `0` errors
- **Runtime:** `93.60s` (`0:01:33`)

---

## 2. Per-File Test Results (`backend/tests`)

| Test File | Collected | Passed | Failed | Skipped | Errors | Notes |
|---|---:|---:|---:|---:|---:|---|
| `test_admin_config.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_analytics.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_audit_logs.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_auth.py` | 9 | 9 | 0 | 0 | 0 | Auth / JWT / RBAC baseline |
| `test_budgets.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_destinations.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_economics.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_enterprise_apis_rbac.py` | 8 | 8 | 0 | 0 | 0 | Enterprise HTTP APIs, RBAC, worker/supplier auth, SoD & expired FX regression |
| `test_enterprise_domains_services.py` | 7 | 7 | 0 | 0 | 0 | Service logic, CVaR MILP, PSI/KS, netting, treasury, policy AST, Stage 12 regressions |
| `test_enterprise_schemas_and_models.py` | 6 | 6 | 0 | 0 | 0 | Pydantic v2 validation & 24 ORM model/constraint checks |
| `test_forecasts.py` | 1 | 0 | 1 | 0 | 0 | Pre-existing baseline failure (`OptimizationConfig()` missing required `run_id`) |
| `test_health.py` | 1 | 1 | 0 | 0 | 0 | Health probes pass |
| `test_inventory.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_ml_registry.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_notifications.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_optimization.py` | 1 | 0 | 1 | 0 | 0 | Pre-existing baseline failure (`candidate_builder.py:56`) |
| `test_pipelines.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_procurement.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_recommendations.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_reference_data.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_remediation_regression.py` | 8 | 6 | 2 | 0 | 0 | 2 pre-existing optimization failures (`candidate_builder.py:56`); other 6 pass |
| `test_reports.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_search_events.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_socketio_notifications.py` | 16 | 16 | 0 | 0 | 0 | SocketIO notifications pass |
| `test_stage11a_regression.py` | 6 | 6 | 0 | 0 | 0 | Stage 11A baseline regression pass |
| `test_stage2_catalog.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_supplier_offers.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_suppliers.py` | 1 | 1 | 0 | 0 | 0 | Baseline pass |
| `test_users.py` | 7 | 7 | 0 | 0 | 0 | Baseline pass |
| `test_workflows.py` | 4 | 2 | 2 | 0 | 0 | Pre-existing failures (`FAILED == PENDING`; `candidate_builder.py:56`) |
| **Total** | **92** | **86** | **6** | **0** | **0** | **21/21 Enterprise tests pass** |

---

## 3. Root-Cause Verification of the 6 Pre-Existing Baseline Failures

Running `python -m pytest backend/tests` before any Stage 12 edits yielded the exact same 6 failures (`84 passed, 6 failed` prior to adding 2 Stage 12 regression tests, `86 passed, 6 failed` afterward):

1. `test_forecasts.py::test_forecasts_and_predictions`
   - Calls `ForecastingService.generate_predictions` (`backend/app/services/forecasting_service.py:78`), where `opt_config = OptimizationConfig()` fails Pydantic validation (`run_id Field required`).
2. `test_optimization.py::test_optimization_runs_lifecycle`
3. `test_remediation_regression.py::test_optimization_real_execution`
4. `test_remediation_regression.py::test_optimization_compare_runs`
5. `test_workflows.py::test_workflow_c_optimization_and_procurement`
   - All four invoke `OptimizationService.trigger_run` -> `OptimizationPipeline.run()` -> `CandidateBuilder.build_candidate_opportunities()` at `optimization/data/candidate_builder.py:56`, which references `self.config.financial.total_budget` on `FinancialAssumptions` (`AttributeError: 'FinancialAssumptions' object has no attribute 'total_budget'`).
6. `test_workflows.py::test_workflow_b_reference_and_ml`
   - Fails at `backend/tests/test_workflows.py:77` (`AssertionError: assert 'FAILED' == 'PENDING'`) on batch ingestion status under the isolated test environment.

Per Stage 12 audit rules, these pre-existing files (`optimization/data/candidate_builder.py`, `backend/app/services/forecasting_service.py`, `test_workflows.py`) were not modified.

---

## 4. Enterprise Regression Coverage Added in Stage 12

Added `test_stage12_audit_remediation_regressions` in `backend/tests/test_enterprise_domains_services.py` and `test_stage12_api_exception_sod_and_expired_fx_rejection` in `backend/tests/test_enterprise_apis_rbac.py`, verifying:
- **Domain 1:** Duplicate single `scenario_id` and `NaN` correlation matrix validation errors; infeasible CVaR yielding `achieved_availability_pct == 0.0` (instead of `100.0`); `PolicyScope.OPTIMIZATION_RUN` blocking on CVaR optimization.
- **Domain 2:** Rejection of non-finite (`NaN`) drift samples (`BadRequestException`); canary rollback safely demoting an unrelated champion of the same `model_type` (`MLModelType.HOTEL_CANCELLATION`) before promoting the rollback target without hitting `uq_ml_model_single_champion`; `FEATURE_STALENESS` auto-trigger evaluation on `check_feature_freshness`.
- **Domain 3:** Invalid credential scope rejection; per-item savepoint (`begin_nested`) isolation in `push_rates_and_availability`; duplicate PO exclusion across non-cancelled `SettlementNettingBatch` records.
- **Domain 4:** Rejection of expired FX forward execution (`maturity_date < today`); rejection of hedge effectiveness measurement on `DRAFT` contracts.
- **Domain 5:** Separation-of-duties block on self-approval of policy exceptions (both service and HTTP API `403`); boolean guard on numeric AST operators (`gt`, `gte`, `lt`, `lte`, `between`); list membership semantics on `contains`; atomic rollback of partial bulk mutations when `PolicyService.enforce_workflow_policies` blocks midway through `RecommendationService.bulk_approve`, while persisting the violation `PolicyEvaluationLog`.
