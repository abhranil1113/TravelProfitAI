# Enterprise Production Features — API Reference

**Total Registered HTTP Endpoints:** 253 (186 existing + 67 newly added)
- **Public Endpoints:** 13 (`/health`, `/api/v1/health`, `/api/v1/health/ready`, `/api/v1/health/version`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/verify-email`, `/api/v1/auth/forgot-password`, `/api/v1/auth/reset-password`, plus OpenAPI/Swagger/ReDoc routes `/api/v1/openapi.json`, `/api/v1/docs`, `/docs/oauth2-redirect`, `/api/v1/redoc`)
- **Protected Endpoints:** 240 (JWT Bearer RBAC, Worker Token `X-Worker-Token`, or Supplier Machine `X-Supplier-Key`)
- **Modified Existing Endpoints:** `POST /api/v1/optimization-runs` (policy enforcement), `POST /api/v1/optimization-runs/{run_id}/purchase-orders/generate` (policy enforcement), `POST /api/v1/recommendations/{id}/approve` & `POST /api/v1/optimization-runs/{run_id}/recommendations/bulk-approve` (policy enforcement), `POST /api/v1/purchase-orders` (policy enforcement + suspended supplier verification check).

---

## 1. Domain 1: Portfolio Risk & Scenario Engine (`/api/v1/risk/` & `/api/v1/optimization-runs/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/risk/scenarios` | Bearer JWT | List risk scenarios (filter by `scenario_type`, `is_active`, paginated) |
| `POST` | `/api/v1/risk/scenarios` | Bearer JWT (`ADMIN`) | Create single-factor or correlated multivariate scenario |
| `GET` | `/api/v1/risk/scenarios/{scenario_id}` | Bearer JWT | Get scenario details |
| `PATCH` | `/api/v1/risk/scenarios/{scenario_id}` | Bearer JWT (`ADMIN`) | Update scenario parameters |
| `DELETE` | `/api/v1/risk/scenarios/{scenario_id}` | Bearer JWT (`ADMIN`) | Soft-deactivate scenario |
| `GET` | `/api/v1/risk/portfolio-summary` | Bearer JWT | Portfolio VaR, CVaR, HHI concentration, fulfillment metrics |
| `POST` | `/api/v1/optimization-runs/cvar` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Run Rockafellar-Uryasev MILP CVaR tail-risk optimization |
| `POST` | `/api/v1/optimization-runs/{run_id}/stress-test` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Stress test an existing optimization run against scenarios |
| `GET` | `/api/v1/optimization-runs/{run_id}/stress-tests` | Bearer JWT | List stored stress test results for a run |
| `GET` | `/api/v1/optimization-runs/{run_id}/risk-adjusted-comparison` | Bearer JWT | Compare baseline vs CVaR/alternative runs on risk-adjusted return |

### Example: Create Correlated Scenario
```json
POST /api/v1/risk/scenarios
{
  "scenario_code": "SEVERE_SHOCK",
  "name": "Cancellation + FX Spike",
  "scenario_type": "CORRELATED_MULTIVARIATE",
  "probability_weight": 0.30,
  "demand_multiplier": 0.70,
  "cancellation_delta": 0.25,
  "fx_shock_pct": 0.15,
  "supplier_capacity_multiplier": 0.80,
  "correlation_matrix_json": {
    "demand": {"demand": 1.0, "cancellation": -0.5},
    "cancellation": {"demand": -0.5, "cancellation": 1.0}
  }
}
```

### Example: CVaR Optimization Request & Response
```json
POST /api/v1/optimization-runs/cvar
{
  "optimization_mode": "JOINT",
  "total_budget_inr": 800000.00,
  "confidence_level_alpha": 0.95,
  "risk_aversion_lambda": 0.50,
  "scenario_ids": [1, 2],
  "min_availability_target_pct": 75.0,
  "min_demand_fulfillment_pct": 50.0
}
```

---

## 2. Domain 2: MLOps Production Governance (`/api/v1/mlops/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/mlops/drift/compute` | `X-Worker-Token` | Compute & persist PSI + KS drift metrics from raw baseline/target distributions |
| `GET` | `/api/v1/mlops/drift` | Bearer JWT (`ADMIN`, `ANALYST`) | List drift reports |
| `POST` | `/api/v1/mlops/feature-freshness/check` | `X-Worker-Token` | Evaluate feature pipeline staleness against SLA |
| `GET` | `/api/v1/mlops/feature-freshness` | Bearer JWT | View feature freshness status |
| `POST` | `/api/v1/mlops/deployments` | Bearer JWT (`ADMIN`) | Create `SHADOW` (0% live impact) or `CANARY` deployment |
| `GET` | `/api/v1/mlops/deployments` | Bearer JWT (`ADMIN`) | List active/historical deployments |
| `PATCH` | `/api/v1/mlops/deployments/{deployment_id}` | Bearer JWT (`ADMIN`) | Update canary traffic or deployment status |
| `POST` | `/api/v1/mlops/deployments/{deployment_id}/shadow-predictions` | Bearer JWT (`ADMIN`) | Log shadow prediction vs champion (isolated from live procurement) |
| `GET` | `/api/v1/mlops/deployments/{deployment_id}/shadow-predictions` | Bearer JWT (`ADMIN`) | Inspect shadow prediction comparisons |
| `POST` | `/api/v1/mlops/models/{model_id}/promote` | Bearer JWT (`ADMIN`) | Governed promotion to champion (enforces drift gate) |
| `POST` | `/api/v1/mlops/models/{model_id}/rollback` | Bearer JWT (`ADMIN`) | Roll back champion to prior stable model & invalidate caches |
| `GET` | `/api/v1/mlops/history` | Bearer JWT (`ADMIN`, `ANALYST`) | View immutable model lifecycle history |
| `PUT` | `/api/v1/mlops/retraining-triggers` | Bearer JWT (`ADMIN`) | Upsert automated retraining trigger threshold |
| `GET` | `/api/v1/mlops/retraining-triggers` | Bearer JWT (`ADMIN`) | List retraining trigger configs |

---

## 3. Domain 3: Supplier Collaboration & Connectivity Hub (`/api/v1/supplier-portal/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/supplier-portal/credentials` | Bearer JWT (`ADMIN`) | Issue supplier API key (`raw_api_secret` returned once) |
| `GET` | `/api/v1/supplier-portal/credentials` | Bearer JWT (`ADMIN`) | List credentials (hashes/secrets omitted) |
| `POST` | `/api/v1/supplier-portal/credentials/{credential_id}/rotate` | Bearer JWT (`ADMIN`) | Rotate key and mark prior key `ROTATED` |
| `POST` | `/api/v1/supplier-portal/credentials/{credential_id}/revoke` | Bearer JWT (`ADMIN`) | Revoke active credential |
| `POST` | `/api/v1/supplier-portal/rates/push` | `X-Supplier-Key` | Idempotent, rate-limited supplier rate & availability push |
| `GET` | `/api/v1/supplier-portal/me/sync-logs` | `X-Supplier-Key` | Supplier-isolated sync log history |
| `GET` | `/api/v1/supplier-portal/sync-logs` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Internal sync log inspection |
| `PUT` | `/api/v1/supplier-portal/suppliers/{supplier_id}/tier-verification` | Bearer JWT (`ADMIN`) | Update supplier tier & verification status |
| `GET` | `/api/v1/supplier-portal/suppliers/{supplier_id}/tier-verification` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Get supplier tier & verification profile |
| `POST` | `/api/v1/supplier-portal/onboarding` | Bearer JWT (`ADMIN`) | Start supplier onboarding workflow |
| `GET` | `/api/v1/supplier-portal/onboarding` | Bearer JWT (`ADMIN`) | List onboarding workflows |
| `POST` | `/api/v1/supplier-portal/onboarding/{onboarding_id}/advance` | Bearer JWT (`ADMIN`) | Advance or reject onboarding stage |
| `POST` | `/api/v1/supplier-portal/settlement-netting` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Compute & create settlement netting batch |
| `GET` | `/api/v1/supplier-portal/settlement-netting` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | List settlement netting batches |
| `POST` | `/api/v1/supplier-portal/settlement-netting/{batch_id}/approve` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Approve calculated netting batch |
| `POST` | `/api/v1/supplier-portal/settlement-netting/{batch_id}/settle` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Settle approved netting batch |

---

## 4. Domain 4: Multi-Currency Treasury & FX Hedging (`/api/v1/treasury/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/treasury/fx-contracts` | Bearer JWT (`ADMIN`) | Draft FX forward contract |
| `GET` | `/api/v1/treasury/fx-contracts` | Bearer JWT | List FX forward contracts |
| `POST` | `/api/v1/treasury/fx-contracts/{contract_id}/execute` | Bearer JWT (`ADMIN`) | Execute draft FX forward (policy-enforced) |
| `POST` | `/api/v1/treasury/fx-contracts/{contract_id}/settle` | Bearer JWT (`ADMIN`) | Settle active FX forward |
| `POST` | `/api/v1/treasury/fx-contracts/{contract_id}/cancel` | Bearer JWT (`ADMIN`) | Cancel draft/active FX forward |
| `POST` | `/api/v1/treasury/exposure/snapshot` | Bearer JWT | Calculate & snapshot currency exposure from live offers/POs/hedges |
| `GET` | `/api/v1/treasury/exposure` | Bearer JWT | List currency exposure snapshots |
| `POST` | `/api/v1/treasury/hedge-effectiveness` | Bearer JWT (`ADMIN`) | Compute IFRS 9 / IAS 39 dollar-offset hedge effectiveness |
| `GET` | `/api/v1/treasury/hedge-effectiveness` | Bearer JWT | List hedge effectiveness records |
| `POST` | `/api/v1/treasury/margin-rules` | Bearer JWT (`ADMIN`) | Create margin protection rule |
| `PATCH` | `/api/v1/treasury/margin-rules/{rule_id}` | Bearer JWT (`ADMIN`) | Update margin protection rule |
| `GET` | `/api/v1/treasury/margin-rules` | Bearer JWT | List margin protection rules |
| `POST` | `/api/v1/treasury/margin-impact/evaluate` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Evaluate FX margin impact & generate alerts on breach |
| `GET` | `/api/v1/treasury/alerts` | Bearer JWT | List FX alerts |
| `POST` | `/api/v1/treasury/alerts/{alert_id}/acknowledge` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Acknowledge FX alert |

---

## 5. Domain 5: Policy-as-Code & Compliance Engine (`/api/v1/policy/` & `/api/v1/compliance/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/policy/rules` | Bearer JWT (`ADMIN`) | Create versioned declarative policy rule (`BLOCK`, `WARN`, `INFO`) |
| `GET` | `/api/v1/policy/rules` | Bearer JWT | List policy rules & versions |
| `GET` | `/api/v1/policy/rules/{rule_id}` | Bearer JWT | Get policy rule details |
| `PATCH` | `/api/v1/policy/rules/{rule_id}` | Bearer JWT (`ADMIN`) | Update rule (creates new immutable `PolicyRuleVersion`) |
| `POST` | `/api/v1/policy/evaluate` | Bearer JWT | Evaluate active policy rules for a scope/context |
| `GET` | `/api/v1/policy/evaluations` | Bearer JWT | View immutable policy evaluation log history |
| `POST` | `/api/v1/policy/exceptions` | Bearer JWT (`ADMIN`, `PROCUREMENT_MANAGER`) | Submit policy exception request |
| `GET` | `/api/v1/policy/exceptions` | Bearer JWT | List exception requests (PM sees own submissions) |
| `POST` | `/api/v1/policy/exceptions/{exception_id}/approve` | Bearer JWT (`ADMIN`) | Approve pending exception request |
| `POST` | `/api/v1/policy/exceptions/{exception_id}/reject` | Bearer JWT (`ADMIN`) | Reject pending exception request |
| `POST` | `/api/v1/compliance/audits` | Bearer JWT (`ADMIN`) | Run end-to-end compliance audit |
| `GET` | `/api/v1/compliance/audits` | Bearer JWT | View compliance audit records |
