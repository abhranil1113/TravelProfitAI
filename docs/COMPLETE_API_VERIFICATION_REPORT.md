# Complete API Verification Report — All 253 Registered HTTP Routes

**Application Factory:** `backend/app/main.py` -> `api_router` mounted at `/api/v1`  
**Total Registered HTTP Routes:** **253** (`249` application `APIRoute` endpoints + `4` built-in FastAPI OpenAPI/documentation routes: `/api/v1/openapi.json`, `/api/v1/docs`, `/docs/oauth2-redirect`, `/api/v1/redoc`).  
**Non-HTTP Protocols (Segregated):** Socket.IO / WebSocket ASGI handlers (`socket_manager.py`, mounted separately via ASGI wrapper; not counted among the 253 HTTP routes).  
**Automated Route Coverage Verification (`check_coverage.py`):** **`249 / 249` application `APIRoute` paths covered (`0` uncovered)** after adding `backend/tests/test_stage13_api_coverage.py`.

---

## 1. Route Distribution by API Router Tag (`249` Application Routes)

| Router Tag | Route Count | Auth / Access Model | Test Suites Covering Tag |
| :--- | ---: | :--- | :--- |
| `1. Authentication & Session` | 10 | Public (`register`, `login`, `refresh`, `verify`, `forgot`, `reset`) + JWT (`me`, `logout`, `logout-all`, `change-password`) | `test_auth.py` |
| `2. User Management` | 9 | `ADMIN` RBAC (self-profile read/update permitted where scoped) | `test_users.py`, `test_stage13_api_coverage.py` |
| `3. Destinations` | 7 | Authenticated read; `ADMIN` mutating endpoints | `test_destinations.py`, `test_stage2_catalog.py` |
| `4. Suppliers & Contacts` | 13 | `ADMIN` / `PROCUREMENT_MANAGER` / `ANALYST` reads; `ADMIN` writes | `test_suppliers.py`, `test_stage2_catalog.py` |
| `5. Inventory Items & Snapshots` | 8 | Authenticated reads; `ADMIN` / `PROCUREMENT_MANAGER` mutations | `test_inventory.py`, `test_stage2_catalog.py` |
| `6. Supplier Offers` | 7 | Authenticated reads; `ADMIN` / `PM` mutations & CSV bulk-import | `test_supplier_offers.py`, `test_stage2_catalog.py` |
| `7. Reference Data - Baselines/FX/Signals` | 9 | Authenticated reads; `ADMIN` mutations (FX 3, Signals 4, Baselines 2) | `test_reference_data.py` |
| `8. Data Pipeline & Quality` | 6 | `ADMIN` trigger/retry; authenticated monitoring reads | `test_pipelines.py`, `test_stage13_api_coverage.py` |
| `9. Feature Sets & ML Registry` | 12 | `ANALYST` / `ADMIN` create/list; `ADMIN` promote/retire | `test_ml_registry.py`, `test_stage13_api_coverage.py` |
| `10. Forecasts & Predictions` | 6 | Authenticated reads + `PM`/`ADMIN`/`ANALYST` triggers (Forecasts 4, Predictions 2) | `test_forecasts.py`, `test_forecasting.py` |
| `11. Admin Config` | 9 | `ADMIN` writes; authenticated active config reads | `test_admin_config.py` |
| `12. Budgets & Ledger` | 9 | `ADMIN` budget activation/mutation; `PM` / `ANALYST` reads | `test_budgets.py` |
| `13. Optimization Runs` | 24 | `PM` / `ADMIN` trigger/cancel/approve/reject/retry/generate-PO; all auth reads | `test_optimization.py`, `test_remediation_regression.py`, `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `14. Recommendations & Rejections` | 10 | `PM` / `ADMIN` single & bulk approve/reject; all auth reads & export | `test_recommendations.py`, `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `15. Purchase Orders & Fulfillment` | 11 | `PM` / `ADMIN` PO creation, confirmation, fulfillment; all auth reads | `test_procurement.py`, `test_remediation_regression.py`, `test_enterprise_apis_rbac.py` |
| `16. Reports & Schedules` | 11 | Authenticated report generation, artifact download, schedule CRUD | `test_reports.py` |
| `17. Notifications` | 9 | User-scoped inbox, read/acknowledge, preferences + `ADMIN` deliveries | `test_notifications.py`, `test_socketio_notifications.py`, `test_stage13_api_coverage.py` |
| `18. Search Events` | 4 | `X-Worker-Token` bulk ingest + authenticated query endpoints | `test_search_events.py`, `test_workflows.py` |
| `19. Analytics` | 4 | Authenticated executive dashboard, profitability, cancellation/pricing, scorecard | `test_analytics.py` |
| `20. Economics` | 1 | Authenticated expected-contribution preview calculation | `test_economics.py` |
| `21. Audit Logs` | 2 | `ADMIN` audit trail inspection | `test_audit_logs.py` |
| `22. Health & System` + `Health` | 5 | Public liveness (`/health`, `/api/v1/health`) & system diagnostics | `test_health.py` |
| `23. Portfolio Risk & Scenarios` | 6 | `ADMIN` scenario CRUD; `PM` stress-test & CVaR run; all auth reads | `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `24. MLOps Production Governance` | 14 | `X-Worker-Token` drift & freshness compute; `ADMIN` deploy/promote/rollback | `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `25. Supplier Collaboration & Hub` | 16 | `X-Supplier-Key` push & own sync logs; `ADMIN`/`PM` portal governance & netting | `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `26. Multi-Currency Treasury & FX` | 15 | `ADMIN` FX forward lifecycle & rules; `PM`/`ADMIN` impact eval & alert ack | `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `27. Policy-as-Code Engine` | 10 | `ADMIN` rules & exception review (SoD enforced); `PM` exception submit & evaluate | `test_enterprise_apis_rbac.py`, `test_stage13_api_coverage.py` |
| `28. Compliance Audits` | 2 | `ADMIN` audit execution; all auth reads | `test_enterprise_apis_rbac.py` |
| **Total Application `APIRoute`s** | **249** | **(+4 OpenAPI/Docs = 253 total HTTP routes)** | **100% route inventory verified** |

---

## 2. Authentication, RBAC & Validation Checks Verified

- **Public Endpoints:** `/health`, `/api/v1/health`, `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/verify-email`, `/api/v1/auth/forgot-password`, `/api/v1/auth/reset-password`, plus FastAPI docs/OpenAPI routes (`/api/v1/openapi.json`, `/api/v1/docs`, `/docs/oauth2-redirect`, `/api/v1/redoc`).
- **Missing / Invalid / Expired / Deactivated Tokens:** Tested across core and enterprise routes -> returns `401 Unauthorized` for missing/malformed/expired JWTs and `403 Forbidden` for inactive user accounts or insufficient role claims. Invalid numeric `sub` JWT claims now return clean HTTP 401 rather than unhandled `ValueError` 500s, and `password_changed_at` invalidates older JWTs (`iat < password_changed_at`).
- **Trusted Machine Authentication:**
  - `X-Worker-Token` required for `/api/v1/mlops/drift/compute`, `/api/v1/mlops/feature-freshness/check`, `/api/v1/search-events/bulk` (`403` when Admin/Analyst JWT attempts bypass).
  - `X-Supplier-Key` required for `/api/v1/supplier-portal/rates/push` and `/api/v1/supplier-portal/me/sync-logs` (`401` for human JWTs, revoked keys, rotated-out keys, or expired keys; `403`/rejection on cross-supplier offer IDs).
- **Stage 13 API Coverage Remediation Additions (`backend/tests/test_stage13_api_coverage.py`):**
  - Covered all **37 previously uncovered `APIRoute` endpoints** across Recommendations (individual/bulk approve & reject), Stress-Tests list, Notification mark-read (`POST /notifications/{id}/read`), Risk Scenario `GET`/`PATCH`/`DELETE`, MLOps (`feature-freshness/check`, `deployments/{id}`, `shadow-predictions`, `promote`, `rollback`, `history`), Supplier Portal (`credentials/{id}/rotate` & `revoke`, `me/sync-logs`, `tier-verification` `PUT`/`GET`, `onboarding/{id}/advance`), Treasury (`fx-contracts/{id}/execute|settle|cancel`, `exposure/snapshot`, `hedge-effectiveness`, `margin-rules/{id}`, `alerts` & `acknowledge`), and Policy (`rules/{id}` `GET`/`PATCH`, `evaluate`, `evaluations`, `exceptions/{id}/reject`), plus OpenAPI docs routes, empty-catalog `400` check on `/optimization-runs`, production `action_token=None` redaction on `force-password-reset`, and real CSV pipeline ingestion (`SUCCESS`).

---

## 3. Observed Endpoint Test Caveat
- **`backend/tests/test_workflows.py::test_workflow_b_reference_and_ml`** currently fails assertion `assert batch["status"] == "PENDING"` (`FAILED != PENDING`) when posting non-existent `file_path: "data/rates.csv"` to `POST /api/v1/pipelines/batches`, because `PipelineService.trigger_batch` synchronously validates and cleans input files rather than enqueuing a deferred stub. Posting a real CSV produces `status == "SUCCESS"` (verified in `test_stage13_api_coverage.py::test_openapi_docs_and_regression_fixes`).
