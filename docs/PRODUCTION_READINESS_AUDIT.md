# Stage 12 — Five Enterprise Domains: Production Readiness Audit & Remediation Report

**Audit Date:** `2026-11-26`  
**Scope:** Domains 1–5 (Risk & CVaR, MLOps Governance, Supplier Collaboration Hub, Multi-Currency Treasury & FX Hedging, Policy-as-Code & Compliance), RBAC/Auth, ORM/PostgreSQL Schema Parity, and Alembic Migrations.  
**Pre-Audit Git Baseline:** `f2ce1c1` (`eda part fix and ML`) + Stage 11 implementation.

---

## 1. Architecture & Route Inventory Verification

Detailed per-route tables are recorded in `docs/ROUTE_INVENTORY_STAGE12.md`. Key findings:

- **Total Registered HTTP Routes:** `253`
  - **Pre-existing Baseline (`186`):** `182` documented application endpoints plus `4` FastAPI built-in schema/docs routes (`/api/v1/openapi.json`, `/api/v1/docs`, `/docs/oauth2-redirect`, `/api/v1/redoc`). This reconciles the earlier `182`-route application baseline with the `186` pre-existing FastAPI route count.
  - **Stage 11 Enterprise Routes (`67`):** `10` (Domain 1 Risk/CVaR) + `14` (Domain 2 MLOps) + `16` (Domain 3 Supplier Portal) + `15` (Domain 4 Treasury/FX) + `12` (Domain 5 Policy/Compliance).
- **Uniqueness & Shadowing:** `0` duplicate `(method, path)` entries; no existing route was replaced or shadowed.
- **Authorization Distribution Across All `253` Routes:**
  - `ROLE_PROTECTED`: `208` (`145` pre-existing, `63` new)
  - `AUTHENTICATED_USER`: `27` (`27` pre-existing, `0` new)
  - `PUBLIC`: `13` (`13` pre-existing open health/auth/docs, `0` new)
  - `WORKER_TOKEN` (`X-Worker-Token`): `3` (`1` pre-existing `/api/v1/search-events/bulk`, `2` new `/api/v1/mlops/drift/compute` and `/api/v1/mlops/feature-freshness/check`)
  - `SUPPLIER_KEY` (`X-Supplier-Api-Key`): `2` (`0` pre-existing, `2` new `/api/v1/supplier-portal/rates/push` and `/api/v1/supplier-portal/me/sync-logs`)

---

## 2. Confirmed Defects Identified & Remediated

### Domain 1: Advanced Portfolio Risk & Scenario Engine
| Severity | Defect Found | Remediation Applied | File(s) |
|---|---|---|---|
| **High** | `RiskService.run_cvar_optimization` bypassed `PolicyScope.OPTIMIZATION_RUN` checks enforced in standard `OptimizationService.trigger_run`. | Invoked `PolicyService.enforce_workflow_policies` in `OPTIMIZATION_RUN` scope before MILP execution. | `backend/app/services/risk_service.py` |
| **Medium** | Infeasible CVaR solves produced `achieved_availability_pct = 100.0` when `not selected_qty`; `risk_adjusted_profit_inr` clamped negative `cvar_loss` differently from the Rockafellar-Uryasev MILP objective `(1 - lam)*E[P] - lam*CVaR(Loss)`. | Forced zeroed metrics + `infeasible: True` flag on `INFEASIBLE` solves; aligned `risk_adjusted_profit_inr` with exact MILP objective. | `backend/app/services/risk_service.py` |
| **Medium** | `CVaROptimizationRequest` accepted `[id, id]` duplicates; `budget_id` did not enforce `BudgetStatus.ACTIVE`; `RiskScenarioUpdateRequest` lacked correlation matrix symmetry/diagonal/NaN validation; `update_scenario` skipped destination/supplier existence checks; Cholesky input wasn't re-symmetrized after eigen-projection. | Added distinct-ID & finite correlation validators (`_validate_correlation_matrix`), `BudgetStatus.ACTIVE` guard, FK existence checks in `update_scenario`, positive weight sum check, and pre-Cholesky symmetrization. | `backend/app/schemas/risk.py`, `backend/app/services/risk_service.py` |

### Domain 2: MLOps Production Governance
| Severity | Defect Found | Remediation Applied | File(s) |
|---|---|---|---|
| **High** | `MLOpsService.rollback_model` only demoted `current.is_champion = False`; rolling back a non-champion canary to a third model left the existing champion active, violating `uq_ml_model_single_champion`. | Demoted all active champions of `current.model_type` and flushed prior to promoting target; blocked rollback to `RETIRED` models. | `backend/app/services/mlops_service.py` |
| **High** | `MLOpsService.compute_and_record_drift` passed raw arrays with `NaN`/`Inf` straight to `scipy.stats.ks_2samp`, yielding `NaN` statistics. | Filtered arrays via `np.isfinite`, enforced `>= 10` finite samples per window/column, and verified finite KS outputs. | `backend/app/services/mlops_service.py` |
| **Medium** | `check_feature_freshness` never invoked `_evaluate_retraining_triggers` for `FEATURE_STALENESS`; `_evaluate_retraining_triggers` picked any active `FeatureSet` regardless of `entity_type`. | Wired `FEATURE_STALENESS` evaluation in `check_feature_freshness` and prioritized matching `FeatureSet.entity_type == model_type.value`. | `backend/app/services/mlops_service.py` |

### Domain 3: Supplier Collaboration & Connectivity Hub
| Severity | Defect Found | Remediation Applied | File(s) |
|---|---|---|---|
| **Critical** | `SupplierPortalService.create_netting_batch` did not filter `PurchaseOrder.currency == req.currency` or exclude POs already included in prior non-cancelled `SettlementNettingBatch` records, permitting duplicate PO settlement. | Filtered by `req.currency.upper()`, normalized naive/aware `ordered_at`, and excluded `po_number`s already in non-cancelled batches for that supplier. | `backend/app/services/supplier_portal_service.py` |
| **High** | `push_rates_and_availability` caught Python exceptions per item without DB savepoints or `db.flush()`, allowing DB errors on one offer to corrupt the entire batch; lacked `InventoryItem.dest_id` parity check and credential scope allowlist validation. | Wrapped per-item upsert/snapshot in `with db.begin_nested():` + `db.flush()`; verified `inv_item.dest_id == item.dest_id`; restricted scopes to `{"rates:write", "availability:write", "sync:read"}`. | `backend/app/schemas/supplier_portal.py`, `backend/app/services/supplier_portal_service.py` |

### Domain 4: Multi-Currency Treasury & FX Hedging
| Severity | Defect Found | Remediation Applied | File(s) |
|---|---|---|---|
| **High** | `TreasuryService.execute_fx_forward` allowed executing `DRAFT` contracts whose `maturity_date < date.today()`. | Rejected expired forward contract execution with `BadRequestException`. | `backend/app/services/treasury_service.py` |
| **Medium** | `record_hedge_effectiveness` accepted `DRAFT`/`CANCELLED` contracts; `evaluate_margin_impact` used float arithmetic (`1.0 + req.fx_shock_pct`) before `Decimal`. | Restricted effectiveness tests to `APPROVED`/`ACTIVE`/`SETTLED` contracts; computed shock factor with pure `Decimal("1") + Decimal(str(...))`. | `backend/app/services/treasury_service.py` |

### Domain 5: Policy-as-Code & Compliance Engine
| Severity | Defect Found | Remediation Applied | File(s) |
|---|---|---|---|
| **Critical** | `PolicyService.enforce_workflow_policies` called `db.commit()` on `BLOCK` before raising `PermissionDeniedError`. In multi-item loops (`OptimizationService.generate_purchase_orders`, `RecommendationService.bulk_approve`), a block on item #2 committed item #1's partial mutations. | Updated `enforce_workflow_policies` to run `db.rollback()` on caller mutations first before persisting violation logs and raising `403`, AND refactored `generate_purchase_orders` and `bulk_approve` to evaluate all items prior to mutating state. | `backend/app/services/policy_service.py`, `backend/app/services/optimization_service.py`, `backend/app/services/recommendation_service.py` |
| **High** | `PolicyService.decide_exception` permitted an Admin who requested an exception to approve their own request. | Enforced Separation of Duties (`exc.requested_by_user_id != admin_user_id` required for approval). | `backend/app/services/policy_service.py` |
| **Medium** | `_evaluate_condition_ast` accepted `bool` values (`True`/`False`) as numeric floats in `gt/gte/lt/lte/between` and treated list `contains` via `str(list)` substring matching. | Explicitly rejected `bool` operands in numeric operators and implemented element membership for collection `contains`. | `backend/app/services/policy_service.py` |

### Alembic Migration (`9a12bccfc7cb_add_five_enterprise_domains.py`)
| Severity | Defect Found | Remediation Applied | File(s) |
|---|---|---|---|
| **Low/Medium** | `downgrade()` dropped all 24 tables without dropping the 24 newly created PostgreSQL `ENUM` types, which could leave orphaned types on rollback. | Added PostgreSQL `DROP TYPE IF EXISTS` cleanup in `downgrade()` for the 24 new enums (explicitly preserving pre-existing `mlmodeltype` owned by `0c9324adb980`). Downgrade was NOT executed destructively. | `backend/alembic/versions/9a12bccfc7cb_add_five_enterprise_domains.py` |

---

## 3. Database, Auth & Security Verification Summary

- **PostgreSQL Live Schema Parity (Verified):** `alembic_version` at `9a12bccfc7cb`; `68` total DB tables (`67` ORM models + `alembic_version`), `IN_ORM_NOT_PG = []`, `IN_PG_NOT_ORM = []`. All `24` new domain tables exist in PostgreSQL.
- **RBAC & Machine Auth:**
  - Verified by `test_enterprise_apis_rbac.py` (`8/8` pass): Analyst/PM/Admin role checks, `X-Worker-Token` exclusivity on monitoring compute routes, and `X-Supplier-Api-Key` supplier isolation on `rates/push` and `me/sync-logs` (including cross-supplier `403` and expired/revoked key `401`).
  - Verified by code inspection across all endpoints: identity (`user_id`, `role`, `supplier_id`, `service_identity`) is derived exclusively from JWT claims, `X-Worker-Token`, or authenticated `SupplierApiCredential`, never from request body fields.

---

## 4. Known Scope Boundaries & Deployment Considerations

1. **Test vs. Live Database Engine:** The automated `pytest` suite (`86 passed, 6 pre-existing failed`) executes against in-memory SQLite (`conftest.py`), whereas live DB checks verified table/revision parity against PostgreSQL `9a12bccfc7cb`. PostgreSQL-only concurrency (e.g., `SELECT ... FOR UPDATE` contention on `create_netting_batch` or `run_cvar_optimization`) was inspected in code rather than load-tested against live PostgreSQL.
2. **In-Memory Supplier Rate Limiter:** `SupplierPortalService._enforce_rate_limit` uses an in-process `threading.Lock` + `deque` sliding window per credential ID. This is production-safe for single-worker deployment, whereas horizontal multi-worker scaling requires migrating the sliding window counter to Redis.
3. **Treasury Accounting Scope:** Margin impact and hedge effectiveness follow a simplified dollar-offset calculation (`80%–125%` band) on `FXForwardContract` and `ExchangeRate` records; this is **not** full multi-ledger GAAP/IFRS 9 hedge accounting (no OCI reserve journal entries, yield curve discounting, or CVA/DVA valuation adjustments).
4. **Pre-Existing Baseline Gaps:** Six pre-existing tests fail identically before and after Stage 12 changes due to `FinancialAssumptions.total_budget` (`optimization/data/candidate_builder.py:56`), `OptimizationConfig()` missing `run_id` (`backend/app/services/forecasting_service.py:78`), and `test_workflow_b_reference_and_ml`.
