# Enterprise Production Features — RBAC & Authentication Matrix

## Authentication Mechanisms

1. **Human User JWT Authentication (`Authorization: Bearer <access_token>`)**
   - Validated via `backend.app.dependencies.get_current_user` and `backend.app.core.security.decode_access_token`.
   - Roles enforced via `require_roles(*allowed_roles)` (`ADMIN`, `ANALYST`, `PROCUREMENT_MANAGER`).
   - Missing, invalid, or expired tokens return **401 Unauthorized**; deactivated users or unauthorized roles return **403 Forbidden**.

2. **Monitoring Service Authentication (`X-Worker-Token`)**
   - Validated via `backend.app.dependencies.require_worker_token` using constant-time digest comparison against `settings.WORKER_SECRET_TOKEN`.
   - Required for trusted PSI/KS drift metric computation and feature freshness checks. Human user JWTs cannot submit pre-computed drift metrics.

3. **Supplier Machine-to-Machine Authentication (`X-Supplier-Key`)**
   - Validated via `backend.app.dependencies.get_authenticated_supplier` -> `SupplierPortalService.authenticate_machine_credential`.
   - Completely isolated from human JWT accounts (`users` table). Enforces SHA-256 secret lookup, active status, expiration, active `Supplier` record, sliding-window per-minute rate limiting (`429`), and strict `supplier_id` ownership isolation.

---

## Role-Based Access Control Matrix

| Capability | Endpoint Group | ADMIN | ANALYST | PROCUREMENT_MANAGER | Machine / Worker |
|---|---|---|---|---|---|
| Configure risk scenarios | `POST/PATCH/DELETE /api/v1/risk/scenarios*` | Yes | No (403) | No (403) | No |
| View risk scenarios & portfolio risk | `GET /api/v1/risk/*`, `GET /optimization-runs/{id}/stress-tests`, `GET .../risk-adjusted-comparison` | Yes | Yes | Yes | No |
| Run stress tests | `POST /api/v1/optimization-runs/{run_id}/stress-test` | Yes | No (403) | Yes | No |
| Run CVaR optimization | `POST /api/v1/optimization-runs/cvar` | Yes | No (403) | Yes | No |
| View model drift & lifecycle history | `GET /api/v1/mlops/drift`, `GET /api/v1/mlops/history` | Yes | Yes | No (403) | No |
| Compute & record trusted drift metrics | `POST /api/v1/mlops/drift/compute` | No (403) | No (403) | No (403) | **Worker Token (`X-Worker-Token`)** |
| Record feature freshness check | `POST /api/v1/mlops/feature-freshness/check` | No (403) | No (403) | No (403) | **Worker Token (`X-Worker-Token`)** |
| View feature freshness | `GET /api/v1/mlops/feature-freshness` | Yes | Yes | Yes | No |
| Manage shadow/canary deployments & shadow logs | `/api/v1/mlops/deployments*` | Yes | No (403) | No (403) | No |
| Governed model promote & rollback | `POST /api/v1/mlops/models/{id}/promote`, `.../rollback` | Yes | No (403) | No (403) | No |
| Configure/view retraining triggers | `PUT/GET /api/v1/mlops/retraining-triggers` | Yes | No (403) | No (403) | No |
| Manage supplier API credentials | `/api/v1/supplier-portal/credentials*` | Yes | No (403) | No (403) | No |
| Submit supplier rate & availability push | `POST /api/v1/supplier-portal/rates/push` | No (401) | No (401) | No (401) | **Supplier Key (`X-Supplier-Key`)** |
| View own supplier sync logs | `GET /api/v1/supplier-portal/me/sync-logs` | No (401) | No (401) | No (401) | **Supplier Key (`X-Supplier-Key`)** |
| View supplier sync logs (internal) | `GET /api/v1/supplier-portal/sync-logs` | Yes | No (403) | Yes | No |
| Manage supplier tiers & verification | `PUT /api/v1/supplier-portal/suppliers/{id}/tier-verification` | Yes | No (403) | No (403) | No |
| View supplier tiers & verification | `GET /api/v1/supplier-portal/suppliers/{id}/tier-verification` | Yes | No (403) | Yes | No |
| Manage supplier onboarding | `/api/v1/supplier-portal/onboarding*` | Yes | No (403) | No (403) | No |
| Manage settlement netting | `/api/v1/supplier-portal/settlement-netting*` | Yes | No (403) | Yes | No |
| Manage & execute FX forward contracts | `POST /api/v1/treasury/fx-contracts*`, `POST /treasury/hedge-effectiveness` | Yes | No (403) | No (403) | No |
| View currency exposure, contracts, alerts | `GET /api/v1/treasury/*`, `POST /treasury/exposure/snapshot` | Yes | Yes | Yes | No |
| Manage margin protection rules | `POST/PATCH /api/v1/treasury/margin-rules*` | Yes | No (403) | No (403) | No |
| Evaluate margin protection & ack alerts | `POST /api/v1/treasury/margin-impact/evaluate`, `POST /treasury/alerts/{id}/acknowledge` | Yes | No (403) | Yes | No |
| Manage policy rules | `POST/PATCH /api/v1/policy/rules*` | Yes | No (403) | No (403) | No |
| View policy rules, evaluations, evaluate | `GET /api/v1/policy/rules*`, `GET /policy/evaluations`, `POST /policy/evaluate` | Yes | Yes | Yes | No |
| Submit policy exception requests | `POST /api/v1/policy/exceptions` | Yes | No (403) | Yes | No |
| View policy exceptions | `GET /api/v1/policy/exceptions` | Yes (all) | Yes (all) | Yes (own submissions) | No |
| Approve / reject policy exceptions | `POST /api/v1/policy/exceptions/{id}/approve`, `.../reject` | Yes | No (403) | No (403) | No |
| Run compliance audits | `POST /api/v1/compliance/audits` | Yes | No (403) | No (403) | No |
| View compliance audit results | `GET /api/v1/compliance/audits` | Yes | Yes | Yes | No |
