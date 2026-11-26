# Stage 12 — Registered HTTP Route Inventory

**Total Registered HTTP Routes:** `253` (`186` Pre-existing = `182` Application Routes + `4` FastAPI Built-in OpenAPI/Docs Routes; **`67` New Enterprise Domain Routes**)

## 1. Baseline Reconciliation (`182` vs `186`)

- Earlier project documentation counted `182` pre-existing application routes.
- Direct inspection of the live FastAPI `app.routes` registry yields `186` pre-existing HTTP routes: those `182` application routes plus `4` FastAPI built-in schema/documentation endpoints (`/api/v1/openapi.json`, `/api/v1/docs`, `/docs/oauth2-redirect`, `/api/v1/redoc`).
- Adding the `67` newly implemented Stage 11 enterprise routes produces **`253` total HTTP routes** (`186 + 67 = 253`), with **`0` duplicate `(method, path)` pairs** and **`0` shadowed routes**.

## 2. Authorization Breakdown (All 253 Routes)

| Auth Mechanism | Total Routes | Pre-existing (`186`) | New Enterprise (`67`) |
|---|---:|---:|---:|
| `PUBLIC` | 13 | 13 | 0 |
| `AUTHENTICATED_USER` | 27 | 27 | 0 |
| `ROLE_PROTECTED` | 208 | 145 | 63 |
| `WORKER_TOKEN` | 3 | 1 | 2 |
| `SUPPLIER_KEY` | 2 | 0 | 2 |

## 3. Domain Route Count Summary

| Domain | Route Count |
|---|---:|
| Domain 1: Risk & CVaR | 10 |
| Domain 2: MLOps Governance | 14 |
| Domain 3: Supplier Collaboration Hub | 16 |
| Domain 4: Multi-Currency Treasury & FX | 15 |
| Domain 5: Policy & Compliance | 12 |
| Pre-existing Baseline | 186 |

## 4. Domain 1: Risk & CVaR (10 Routes)

| Method | Path | Auth | Allowed Roles / Guard | Response Schema | Tags |
|---|---|---|---|---|---|
| `POST` | `/api/v1/optimization-runs/cvar` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | `<class 'backend.app.schemas.risk.CVaROptimizationRecordResponse'>` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/risk-adjusted-comparison` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | `<class 'backend.app.schemas.risk.RiskAdjustedComparisonResponse'>` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs/{run_id}/stress-test` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | `<class 'backend.app.schemas.risk.StressTestBatchResponse'>` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/stress-tests` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | `typing.List[backend.app.schemas.risk.PortfolioStressTestResponse]` | 13. Optimization Runs |
| `GET` | `/api/v1/risk/portfolio-summary` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.risk.PortfolioRiskSummaryResponse'>` | 23. Portfolio Risk & Scenarios |
| `GET` | `/api/v1/risk/scenarios` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.risk.RiskScenarioListResponse'>` | 23. Portfolio Risk & Scenarios |
| `POST` | `/api/v1/risk/scenarios` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.risk.RiskScenarioResponse'>` | 23. Portfolio Risk & Scenarios |
| `DELETE` | `/api/v1/risk/scenarios/{scenario_id}` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.risk.RiskScenarioResponse'>` | 23. Portfolio Risk & Scenarios |
| `GET` | `/api/v1/risk/scenarios/{scenario_id}` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.risk.RiskScenarioResponse'>` | 23. Portfolio Risk & Scenarios |
| `PATCH` | `/api/v1/risk/scenarios/{scenario_id}` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.risk.RiskScenarioResponse'>` | 23. Portfolio Risk & Scenarios |

## 4. Domain 2: MLOps Governance (14 Routes)

| Method | Path | Auth | Allowed Roles / Guard | Response Schema | Tags |
|---|---|---|---|---|---|
| `GET` | `/api/v1/mlops/deployments` | `ROLE_PROTECTED` | `ADMIN` | `typing.List[backend.app.schemas.mlops.ModelDeploymentResponse]` | 24. MLOps Production Governance |
| `POST` | `/api/v1/mlops/deployments` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.mlops.ModelDeploymentResponse'>` | 24. MLOps Production Governance |
| `PATCH` | `/api/v1/mlops/deployments/{deployment_id}` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.mlops.ModelDeploymentResponse'>` | 24. MLOps Production Governance |
| `GET` | `/api/v1/mlops/deployments/{deployment_id}/shadow-predictions` | `ROLE_PROTECTED` | `ADMIN` | `typing.List[backend.app.schemas.mlops.ShadowPredictionLogResponse]` | 24. MLOps Production Governance |
| `POST` | `/api/v1/mlops/deployments/{deployment_id}/shadow-predictions` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.mlops.ShadowPredictionLogResponse'>` | 24. MLOps Production Governance |
| `GET` | `/api/v1/mlops/drift` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | `<class 'backend.app.schemas.mlops.ModelDriftReportListResponse'>` | 24. MLOps Production Governance |
| `POST` | `/api/v1/mlops/drift/compute` | `WORKER_TOKEN` | `-` | `<class 'backend.app.schemas.mlops.ModelDriftReportResponse'>` | 24. MLOps Production Governance |
| `GET` | `/api/v1/mlops/feature-freshness` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.mlops.FeatureFreshnessResponse]` | 24. MLOps Production Governance |
| `POST` | `/api/v1/mlops/feature-freshness/check` | `WORKER_TOKEN` | `-` | `<class 'backend.app.schemas.mlops.FeatureFreshnessResponse'>` | 24. MLOps Production Governance |
| `GET` | `/api/v1/mlops/history` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | `typing.List[backend.app.schemas.mlops.ModelLifecycleEventResponse]` | 24. MLOps Production Governance |
| `POST` | `/api/v1/mlops/models/{model_id}/promote` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.ml_registry.MLModelResponse'>` | 24. MLOps Production Governance |
| `POST` | `/api/v1/mlops/models/{model_id}/rollback` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.ml_registry.MLModelResponse'>` | 24. MLOps Production Governance |
| `GET` | `/api/v1/mlops/retraining-triggers` | `ROLE_PROTECTED` | `ADMIN` | `typing.List[backend.app.schemas.mlops.RetrainingTriggerConfigResponse]` | 24. MLOps Production Governance |
| `PUT` | `/api/v1/mlops/retraining-triggers` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.mlops.RetrainingTriggerConfigResponse'>` | 24. MLOps Production Governance |

## 4. Domain 3: Supplier Collaboration Hub (16 Routes)

| Method | Path | Auth | Allowed Roles / Guard | Response Schema | Tags |
|---|---|---|---|---|---|
| `GET` | `/api/v1/supplier-portal/credentials` | `ROLE_PROTECTED` | `ADMIN` | `typing.List[backend.app.schemas.supplier_portal.SupplierCredentialResponse]` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/credentials` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.supplier_portal.SupplierCredentialCreateResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/credentials/{credential_id}/revoke` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.supplier_portal.SupplierCredentialResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/credentials/{credential_id}/rotate` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.supplier_portal.SupplierCredentialCreateResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `GET` | `/api/v1/supplier-portal/me/sync-logs` | `SUPPLIER_KEY` | `-` | `<class 'backend.app.schemas.supplier_portal.SupplierRateSyncLogListResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `GET` | `/api/v1/supplier-portal/onboarding` | `ROLE_PROTECTED` | `ADMIN` | `typing.List[backend.app.schemas.supplier_portal.SupplierOnboardingResponse]` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/onboarding` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.supplier_portal.SupplierOnboardingResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/onboarding/{onboarding_id}/advance` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.supplier_portal.SupplierOnboardingResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/rates/push` | `SUPPLIER_KEY` | `-` | `<class 'backend.app.schemas.supplier_portal.SupplierRateSyncLogResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `GET` | `/api/v1/supplier-portal/settlement-netting` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.supplier_portal.SettlementNettingResponse]` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/settlement-netting` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.supplier_portal.SettlementNettingResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/settlement-netting/{batch_id}/approve` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.supplier_portal.SettlementNettingResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `POST` | `/api/v1/supplier-portal/settlement-netting/{batch_id}/settle` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.supplier_portal.SettlementNettingResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `GET` | `/api/v1/supplier-portal/suppliers/{supplier_id}/tier-verification` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.supplier_portal.SupplierVerificationProfileResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `PUT` | `/api/v1/supplier-portal/suppliers/{supplier_id}/tier-verification` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.supplier_portal.SupplierVerificationProfileResponse'>` | 25. Supplier Collaboration & Connectivity Hub |
| `GET` | `/api/v1/supplier-portal/sync-logs` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.supplier_portal.SupplierRateSyncLogListResponse'>` | 25. Supplier Collaboration & Connectivity Hub |

## 4. Domain 4: Multi-Currency Treasury & FX (15 Routes)

| Method | Path | Auth | Allowed Roles / Guard | Response Schema | Tags |
|---|---|---|---|---|---|
| `GET` | `/api/v1/treasury/alerts` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.treasury.FXAlertResponse]` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/alerts/{alert_id}/acknowledge` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.treasury.FXAlertResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `GET` | `/api/v1/treasury/exposure` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.treasury.CurrencyExposureSnapshotResponse]` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/exposure/snapshot` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.treasury.CurrencyExposureSnapshotResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `GET` | `/api/v1/treasury/fx-contracts` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.treasury.FXForwardListResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/fx-contracts` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.FXForwardResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/fx-contracts/{contract_id}/cancel` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.FXForwardResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/fx-contracts/{contract_id}/execute` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.FXForwardResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/fx-contracts/{contract_id}/settle` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.FXForwardResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `GET` | `/api/v1/treasury/hedge-effectiveness` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.treasury.HedgeEffectivenessResponse]` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/hedge-effectiveness` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.HedgeEffectivenessResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/margin-impact/evaluate` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.treasury.MarginImpactEvaluateResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `GET` | `/api/v1/treasury/margin-rules` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.treasury.MarginProtectionRuleResponse]` | 26. Multi-Currency Treasury & FX Hedging |
| `POST` | `/api/v1/treasury/margin-rules` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.MarginProtectionRuleResponse'>` | 26. Multi-Currency Treasury & FX Hedging |
| `PATCH` | `/api/v1/treasury/margin-rules/{rule_id}` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.treasury.MarginProtectionRuleResponse'>` | 26. Multi-Currency Treasury & FX Hedging |

## 4. Domain 5: Policy & Compliance (12 Routes)

| Method | Path | Auth | Allowed Roles / Guard | Response Schema | Tags |
|---|---|---|---|---|---|
| `GET` | `/api/v1/compliance/audits` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.policy.ComplianceAuditRecordResponse]` | 28. Compliance Audits |
| `POST` | `/api/v1/compliance/audits` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.policy.ComplianceAuditRecordResponse'>` | 28. Compliance Audits |
| `POST` | `/api/v1/policy/evaluate` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.policy.PolicyEvaluateResponse'>` | 27. Policy-as-Code Engine |
| `GET` | `/api/v1/policy/evaluations` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.policy.PolicyEvaluationLogResponse]` | 27. Policy-as-Code Engine |
| `GET` | `/api/v1/policy/exceptions` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `typing.List[backend.app.schemas.policy.PolicyExceptionResponse]` | 27. Policy-as-Code Engine |
| `POST` | `/api/v1/policy/exceptions` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.policy.PolicyExceptionResponse'>` | 27. Policy-as-Code Engine |
| `POST` | `/api/v1/policy/exceptions/{exception_id}/approve` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.policy.PolicyExceptionResponse'>` | 27. Policy-as-Code Engine |
| `POST` | `/api/v1/policy/exceptions/{exception_id}/reject` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.policy.PolicyExceptionResponse'>` | 27. Policy-as-Code Engine |
| `GET` | `/api/v1/policy/rules` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.policy.PolicyRuleListResponse'>` | 27. Policy-as-Code Engine |
| `POST` | `/api/v1/policy/rules` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.policy.PolicyRuleResponse'>` | 27. Policy-as-Code Engine |
| `GET` | `/api/v1/policy/rules/{rule_id}` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | `<class 'backend.app.schemas.policy.PolicyRuleResponse'>` | 27. Policy-as-Code Engine |
| `PATCH` | `/api/v1/policy/rules/{rule_id}` | `ROLE_PROTECTED` | `ADMIN` | `<class 'backend.app.schemas.policy.PolicyRuleResponse'>` | 27. Policy-as-Code Engine |

## 5. Pre-existing Baseline Routes (186 Routes)

| Method | Path | Auth | Allowed Roles / Guard | Tags |
|---|---|---|---|---|
| `GET` | `/api/v1/admin/config-templates` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 11. Admin Config |
| `POST` | `/api/v1/admin/config-templates` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `DELETE` | `/api/v1/admin/config-templates/{id}` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `PATCH` | `/api/v1/admin/config-templates/{id}` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `GET` | `/api/v1/admin/platform-config` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 11. Admin Config |
| `POST` | `/api/v1/admin/platform-config` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `GET` | `/api/v1/admin/platform-config/history` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `PATCH` | `/api/v1/admin/platform-config/{id}` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `POST` | `/api/v1/admin/platform-config/{id}/activate` | `ROLE_PROTECTED` | `ADMIN` | 11. Admin Config |
| `GET` | `/api/v1/analytics/cancellation-and-pricing` | `ROLE_PROTECTED` | `ANALYST,PROCUREMENT_MANAGER,ADMIN` | 19. Analytics |
| `GET` | `/api/v1/analytics/dashboard` | `AUTHENTICATED_USER` | `-` | 19. Analytics |
| `GET` | `/api/v1/analytics/profitability` | `ROLE_PROTECTED` | `ANALYST,PROCUREMENT_MANAGER,ADMIN` | 19. Analytics |
| `GET` | `/api/v1/analytics/suppliers/scorecard` | `ROLE_PROTECTED` | `ANALYST,PROCUREMENT_MANAGER,ADMIN` | 19. Analytics |
| `GET` | `/api/v1/audit-logs` | `ROLE_PROTECTED` | `ADMIN` | 21. Audit Logs |
| `GET` | `/api/v1/audit-logs/{id}` | `ROLE_PROTECTED` | `ADMIN` | 21. Audit Logs |
| `POST` | `/api/v1/auth/change-password` | `AUTHENTICATED_USER` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/forgot-password` | `PUBLIC` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/login` | `PUBLIC` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/logout` | `AUTHENTICATED_USER` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/logout-all` | `AUTHENTICATED_USER` | `-` | 1. Authentication & Session |
| `GET` | `/api/v1/auth/me` | `AUTHENTICATED_USER` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/refresh` | `PUBLIC` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/register` | `ROLE_PROTECTED` | `ADMIN` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/reset-password` | `PUBLIC` | `-` | 1. Authentication & Session |
| `POST` | `/api/v1/auth/verify-email` | `PUBLIC` | `-` | 1. Authentication & Session |
| `GET` | `/api/v1/budgets` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 12. Budgets & Ledger |
| `POST` | `/api/v1/budgets` | `ROLE_PROTECTED` | `ADMIN` | 12. Budgets & Ledger |
| `GET` | `/api/v1/budgets/{id}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 12. Budgets & Ledger |
| `PATCH` | `/api/v1/budgets/{id}` | `ROLE_PROTECTED` | `ADMIN` | 12. Budgets & Ledger |
| `POST` | `/api/v1/budgets/{id}/activate` | `ROLE_PROTECTED` | `ADMIN` | 12. Budgets & Ledger |
| `POST` | `/api/v1/budgets/{id}/adjust` | `ROLE_PROTECTED` | `ADMIN` | 12. Budgets & Ledger |
| `POST` | `/api/v1/budgets/{id}/close` | `ROLE_PROTECTED` | `ADMIN` | 12. Budgets & Ledger |
| `GET` | `/api/v1/budgets/{id}/ledger` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 12. Budgets & Ledger |
| `GET` | `/api/v1/budgets/{id}/utilization` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 12. Budgets & Ledger |
| `GET` | `/api/v1/destinations` | `AUTHENTICATED_USER` | `-` | 3. Destinations |
| `POST` | `/api/v1/destinations` | `ROLE_PROTECTED` | `ADMIN` | 3. Destinations |
| `DELETE` | `/api/v1/destinations/{dest_id}` | `ROLE_PROTECTED` | `ADMIN` | 3. Destinations |
| `GET` | `/api/v1/destinations/{dest_id}` | `AUTHENTICATED_USER` | `-` | 3. Destinations |
| `PATCH` | `/api/v1/destinations/{dest_id}` | `ROLE_PROTECTED` | `ADMIN` | 3. Destinations |
| `GET` | `/api/v1/destinations/{dest_id}/daily-metrics` | `AUTHENTICATED_USER` | `-` | 3. Destinations |
| `GET` | `/api/v1/destinations/{dest_id}/search-velocity` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 3. Destinations |
| `GET` | `/api/v1/docs` | `PUBLIC` | `-` | - |
| `POST` | `/api/v1/economics/simulate` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 20. Economics |
| `GET` | `/api/v1/exchange-rates` | `AUTHENTICATED_USER` | `-` | 7. Reference Data - Exchange Rates |
| `POST` | `/api/v1/exchange-rates` | `ROLE_PROTECTED` | `ADMIN` | 7. Reference Data - Exchange Rates |
| `GET` | `/api/v1/exchange-rates/latest` | `AUTHENTICATED_USER` | `-` | 7. Reference Data - Exchange Rates |
| `GET` | `/api/v1/forecasts/demand` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 10. Forecasts |
| `GET` | `/api/v1/forecasts/demand/{dest_id}/chart` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 10. Forecasts |
| `GET` | `/api/v1/forecasts/inventory` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 10. Forecasts |
| `POST` | `/api/v1/forecasts/materialize` | `ROLE_PROTECTED` | `ADMIN` | 10. Forecasts |
| `GET` | `/api/v1/health` | `PUBLIC` | `-` | 22. Health & System |
| `GET` | `/api/v1/health/champion-models` | `ROLE_PROTECTED` | `ADMIN` | 22. Health & System |
| `GET` | `/api/v1/health/ready` | `PUBLIC` | `-` | 22. Health & System |
| `GET` | `/api/v1/health/version` | `PUBLIC` | `-` | 22. Health & System |
| `GET` | `/api/v1/inventory-items` | `AUTHENTICATED_USER` | `-` | 5. Inventory Items & Snapshots |
| `POST` | `/api/v1/inventory-items` | `ROLE_PROTECTED` | `ADMIN` | 5. Inventory Items & Snapshots |
| `GET` | `/api/v1/inventory-items/{inventory_id}` | `AUTHENTICATED_USER` | `-` | 5. Inventory Items & Snapshots |
| `PATCH` | `/api/v1/inventory-items/{inventory_id}` | `ROLE_PROTECTED` | `ADMIN` | 5. Inventory Items & Snapshots |
| `GET` | `/api/v1/inventory-items/{inventory_id}/offers` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 5. Inventory Items & Snapshots |
| `GET` | `/api/v1/inventory-items/{inventory_id}/snapshots` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 5. Inventory Items & Snapshots |
| `POST` | `/api/v1/inventory-snapshots` | `ROLE_PROTECTED` | `ADMIN` | 5. Inventory Items & Snapshots |
| `POST` | `/api/v1/inventory-snapshots/bulk` | `ROLE_PROTECTED` | `ADMIN` | 5. Inventory Items & Snapshots |
| `GET` | `/api/v1/market-segment-baselines` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 7. Reference Data - Baselines |
| `PUT` | `/api/v1/market-segment-baselines/{segment_name}` | `ROLE_PROTECTED` | `ADMIN` | 7. Reference Data - Baselines |
| `GET` | `/api/v1/market-signals` | `AUTHENTICATED_USER` | `-` | 7. Reference Data - Market Signals |
| `POST` | `/api/v1/market-signals` | `ROLE_PROTECTED` | `ADMIN` | 7. Reference Data - Market Signals |
| `DELETE` | `/api/v1/market-signals/{id}` | `ROLE_PROTECTED` | `ADMIN` | 7. Reference Data - Market Signals |
| `PATCH` | `/api/v1/market-signals/{id}` | `ROLE_PROTECTED` | `ADMIN` | 7. Reference Data - Market Signals |
| `GET` | `/api/v1/ml/feature-sets` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | 9. Feature Sets & ML Registry |
| `POST` | `/api/v1/ml/feature-sets` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/ml/feature-sets/{id}` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/ml/models` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/ml/models/champions` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/ml/models/{id}` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 9. Feature Sets & ML Registry |
| `POST` | `/api/v1/ml/models/{id}/promote` | `ROLE_PROTECTED` | `ADMIN` | 9. Feature Sets & ML Registry |
| `POST` | `/api/v1/ml/models/{id}/retire` | `ROLE_PROTECTED` | `ADMIN` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/ml/training-runs` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | 9. Feature Sets & ML Registry |
| `POST` | `/api/v1/ml/training-runs` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/ml/training-runs/{id}` | `ROLE_PROTECTED` | `ADMIN,ANALYST` | 9. Feature Sets & ML Registry |
| `POST` | `/api/v1/ml/training-runs/{id}/cancel` | `ROLE_PROTECTED` | `ADMIN` | 9. Feature Sets & ML Registry |
| `GET` | `/api/v1/notification-preferences` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `PUT` | `/api/v1/notification-preferences` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `GET` | `/api/v1/notifications` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `GET` | `/api/v1/notifications/deliveries` | `ROLE_PROTECTED` | `ADMIN` | 17. Notifications |
| `POST` | `/api/v1/notifications/mark-all-read` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `GET` | `/api/v1/notifications/unread-count` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `DELETE` | `/api/v1/notifications/{id}` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `POST` | `/api/v1/notifications/{id}/acknowledge` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `POST` | `/api/v1/notifications/{id}/read` | `AUTHENTICATED_USER` | `-` | 17. Notifications |
| `GET` | `/api/v1/openapi.json` | `PUBLIC` | `-` | - |
| `GET` | `/api/v1/optimization-runs` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs/compare` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/compare/{comparison_group_id}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs/{run_id}/approve` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/artifacts` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/artifacts/{filename}` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/baselines` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs/{run_id}/cancel` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/constraints` | `ROLE_PROTECTED` | `ANALYST,ADMIN` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs/{run_id}/purchase-orders/generate` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/recommendations` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 14. Recommendations & Rejections |
| `POST` | `/api/v1/optimization-runs/{run_id}/recommendations/bulk-approve` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 14. Recommendations & Rejections |
| `POST` | `/api/v1/optimization-runs/{run_id}/recommendations/bulk-reject` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 14. Recommendations & Rejections |
| `GET` | `/api/v1/optimization-runs/{run_id}/recommendations/export` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 14. Recommendations & Rejections |
| `POST` | `/api/v1/optimization-runs/{run_id}/reject` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/rejections` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 14. Recommendations & Rejections |
| `GET` | `/api/v1/optimization-runs/{run_id}/rejections/summary` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 14. Recommendations & Rejections |
| `POST` | `/api/v1/optimization-runs/{run_id}/retry` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/risk-metrics` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/scorecard` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/sensitivity` | `ROLE_PROTECTED` | `ANALYST,PROCUREMENT_MANAGER,ADMIN` | 13. Optimization Runs |
| `POST` | `/api/v1/optimization-runs/{run_id}/sensitivity` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/status` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/optimization-runs/{run_id}/stream` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 13. Optimization Runs |
| `GET` | `/api/v1/pipelines/batches` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | 8. Data Pipeline & Quality |
| `POST` | `/api/v1/pipelines/batches` | `ROLE_PROTECTED` | `ADMIN` | 8. Data Pipeline & Quality |
| `GET` | `/api/v1/pipelines/batches/{batch_uid}` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | 8. Data Pipeline & Quality |
| `GET` | `/api/v1/pipelines/batches/{batch_uid}/quality-reports` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | 8. Data Pipeline & Quality |
| `POST` | `/api/v1/pipelines/batches/{batch_uid}/retry` | `ROLE_PROTECTED` | `ADMIN` | 8. Data Pipeline & Quality |
| `GET` | `/api/v1/pipelines/quality-summary` | `ROLE_PROTECTED` | `ADMIN,ANALYST,PROCUREMENT_MANAGER` | 8. Data Pipeline & Quality |
| `GET` | `/api/v1/predictions/offers` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 10. Predictions |
| `POST` | `/api/v1/predictions/offers/generate` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 10. Predictions |
| `PATCH` | `/api/v1/purchase-order-fulfillments/{id}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `POST` | `/api/v1/purchase-order-fulfillments/{id}/dispute` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `GET` | `/api/v1/purchase-orders` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `POST` | `/api/v1/purchase-orders` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `GET` | `/api/v1/purchase-orders/{po_number}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `POST` | `/api/v1/purchase-orders/{po_number}/cancel` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `POST` | `/api/v1/purchase-orders/{po_number}/confirm` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `GET` | `/api/v1/purchase-orders/{po_number}/export` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `GET` | `/api/v1/purchase-orders/{po_number}/fulfillments` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `GET` | `/api/v1/purchase-orders/{po_number}/lines` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `POST` | `/api/v1/purchase-orders/{po_number}/lines/{line_id}/fulfillments` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 15. Purchase Orders & Fulfillment |
| `GET` | `/api/v1/recommendations` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 14. Recommendations & Rejections |
| `GET` | `/api/v1/recommendations/{id}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 14. Recommendations & Rejections |
| `POST` | `/api/v1/recommendations/{id}/approve` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 14. Recommendations & Rejections |
| `POST` | `/api/v1/recommendations/{id}/reject` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ADMIN` | 14. Recommendations & Rejections |
| `GET` | `/api/v1/redoc` | `PUBLIC` | `-` | - |
| `GET` | `/api/v1/report-schedules` | `ROLE_PROTECTED` | `ADMIN` | 16. Reports & Schedules |
| `POST` | `/api/v1/report-schedules` | `ROLE_PROTECTED` | `ADMIN` | 16. Reports & Schedules |
| `DELETE` | `/api/v1/report-schedules/{id}` | `ROLE_PROTECTED` | `ADMIN` | 16. Reports & Schedules |
| `PATCH` | `/api/v1/report-schedules/{id}` | `ROLE_PROTECTED` | `ADMIN` | 16. Reports & Schedules |
| `POST` | `/api/v1/report-schedules/{id}/enable` | `ROLE_PROTECTED` | `ADMIN` | 16. Reports & Schedules |
| `GET` | `/api/v1/reports` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 16. Reports & Schedules |
| `POST` | `/api/v1/reports` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 16. Reports & Schedules |
| `DELETE` | `/api/v1/reports/{report_id}` | `ROLE_PROTECTED` | `ADMIN` | 16. Reports & Schedules |
| `GET` | `/api/v1/reports/{report_id}` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 16. Reports & Schedules |
| `GET` | `/api/v1/reports/{report_id}/download` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 16. Reports & Schedules |
| `POST` | `/api/v1/reports/{report_id}/regenerate` | `ROLE_PROTECTED` | `PROCUREMENT_MANAGER,ANALYST,ADMIN` | 16. Reports & Schedules |
| `GET` | `/api/v1/search-events` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 18. Search Events |
| `GET` | `/api/v1/search-events/analytics/funnel` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 18. Search Events |
| `GET` | `/api/v1/search-events/analytics/velocity` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 18. Search Events |
| `POST` | `/api/v1/search-events/bulk` | `WORKER_TOKEN` | `-` | 18. Search Events |
| `DELETE` | `/api/v1/supplier-contacts/{id}` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `PATCH` | `/api/v1/supplier-contacts/{id}` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `POST` | `/api/v1/supplier-contacts/{id}/set-primary` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/supplier-offers` | `AUTHENTICATED_USER` | `-` | 6. Supplier Offers |
| `POST` | `/api/v1/supplier-offers` | `ROLE_PROTECTED` | `ADMIN` | 6. Supplier Offers |
| `POST` | `/api/v1/supplier-offers/bulk-import` | `ROLE_PROTECTED` | `ADMIN` | 6. Supplier Offers |
| `GET` | `/api/v1/supplier-offers/{offer_id}` | `AUTHENTICATED_USER` | `-` | 6. Supplier Offers |
| `PATCH` | `/api/v1/supplier-offers/{offer_id}` | `ROLE_PROTECTED` | `ADMIN` | 6. Supplier Offers |
| `POST` | `/api/v1/supplier-offers/{offer_id}/expire` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 6. Supplier Offers |
| `GET` | `/api/v1/supplier-offers/{offer_id}/predictions` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 6. Supplier Offers |
| `GET` | `/api/v1/suppliers` | `AUTHENTICATED_USER` | `-` | 4. Suppliers & Contacts |
| `POST` | `/api/v1/suppliers` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `DELETE` | `/api/v1/suppliers/{supplier_id}` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/suppliers/{supplier_id}` | `AUTHENTICATED_USER` | `-` | 4. Suppliers & Contacts |
| `PATCH` | `/api/v1/suppliers/{supplier_id}` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/suppliers/{supplier_id}/contacts` | `AUTHENTICATED_USER` | `-` | 4. Suppliers & Contacts |
| `POST` | `/api/v1/suppliers/{supplier_id}/contacts` | `ROLE_PROTECTED` | `ADMIN` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/suppliers/{supplier_id}/offers` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/suppliers/{supplier_id}/performance-snapshots` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER,ANALYST` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/suppliers/{supplier_id}/purchase-orders` | `ROLE_PROTECTED` | `ADMIN,PROCUREMENT_MANAGER` | 4. Suppliers & Contacts |
| `GET` | `/api/v1/users` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `POST` | `/api/v1/users` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `DELETE` | `/api/v1/users/{id}` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `GET` | `/api/v1/users/{id}` | `AUTHENTICATED_USER` | `-` | 2. User Management |
| `PATCH` | `/api/v1/users/{id}` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `POST` | `/api/v1/users/{id}/deactivate` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `POST` | `/api/v1/users/{id}/force-password-reset` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `POST` | `/api/v1/users/{id}/reactivate` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `POST` | `/api/v1/users/{id}/unlock` | `ROLE_PROTECTED` | `ADMIN` | 2. User Management |
| `GET` | `/docs/oauth2-redirect` | `PUBLIC` | `-` | - |
| `GET` | `/health` | `PUBLIC` | `-` | Health |
