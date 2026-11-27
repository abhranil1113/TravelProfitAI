# Security, Authentication, RBAC & Concurrency Audit — Stage 13

**Verification Basis:** Code review of security/auth/socket/locking layers, live PostgreSQL (`127.0.0.1:5432/Travelprofitai`) multi-threaded `ThreadPoolExecutor` concurrency test (`backend/tests/test_stage13_postgres_concurrency_e2e.py`), and RBAC/auth HTTP tests (`test_auth.py`, `test_users.py`, `test_enterprise_apis_rbac.py`, `test_remediation_regression.py`, `test_socketio_notifications.py`).

---

## 1. Authentication, Token Lifecycle & Transport Security

| Security Area | Findings & Controls Verified |
| :--- | :--- |
| **Password Hashing & Lockout** | bcrypt (`hash_password`/`verify_password`), brute-force lockout after 5 consecutive failures (`locked_until`), `password_changed_at` enforced in `get_current_user` so tokens with `iat < password_changed_at` are rejected (`401`). |
| **JWT Validation** | Validates signature, expiration, active status (`403` for deactivated users), and safe integer `sub` conversion inside `try/except` (`401` on malformed `sub`). |
| **Refresh Token Rotation** | `AuthService.rotate_refresh_token` acquires `.with_for_update()` lock on `RefreshToken`, detects reuse of revoked tokens, and revokes the entire `token_family_id`. Fixed inverted `replaced_by_token_id` assignment (`token_record.replaced_by_token_id = new_token_record.id`). |
| **Action Token Redaction** | `auth.py` hides raw verification/reset tokens (`action_token=None`). Remediated `backend/app/api/v1/users.py::force_password_reset` to redact `action_token=None` when `ENVIRONMENT == "production"`. |
| **Production Startup Guards** | `Settings` (`backend/app/core/config.py`) rejects default `SECRET_KEY`, default `WORKER_SECRET_TOKEN`, and wildcard `"*"` in `BACKEND_CORS_ORIGINS` and `SOCKET_IO_CORS_ORIGINS` when `ENVIRONMENT == "production"`. |
| **Machine Credentials** | Worker endpoints require `X-Worker-Token` (`require_worker_token`, rejecting Admin/Analyst JWTs). Supplier Portal machine endpoints require SHA-256-hashed `X-Supplier-Key` (`tbo_sup_*`), enforcing scopes (`rates:write`, `availability:write`, `sync:read`), sliding-window rate limits (`429`), expiry, atomic rotation (`POST /credentials/{id}/rotate`), and immediate revocation (`POST /credentials/{id}/revoke`). |
| **Socket.IO Authentication** | Query-string tokens explicitly rejected (`CWE-598`); handshake `auth={"token": ...}` requires explicit valid JWT `role` claim and optionally verifies active DB status (`test_socketio_notifications.py` `16/16 PASSED`). |

---

## 2. Authorization (RBAC) & Separation of Duties (SoD)

- **Role Matrix Verified:** `ADMIN`, `PROCUREMENT_MANAGER`, and `ANALYST` permissions verified across positive (`200`/`201`) and negative (`403`) paths in `test_enterprise_apis_rbac.py` and `test_stage13_api_coverage.py`.
- **Object-Level Supplier Isolation:** Supplier machine pushes strictly verify `existing_offer.supplier_id == credential.supplier_id`, rejecting cross-supplier mutation attempts (`offers_rejected == 1`), and `/me/sync-logs` filters strictly by `credential.supplier_id`.
- **Policy Exception Separation of Duties:** `PolicyService.decide_exception` rejects self-approval when `exception.requested_by_user_id == admin_user_id` (`403 Forbidden`), verified in both unit/API and PostgreSQL workflows.

---

## 3. Real PostgreSQL Concurrency & Transaction Integrity Testing

All concurrency tests in `backend/tests/test_stage13_postgres_concurrency_e2e.py::test_real_postgresql_concurrent_for_update_locking` executed concurrently across OS threads (`concurrent.futures.ThreadPoolExecutor`) with independent SQLAlchemy sessions against live PostgreSQL (`127.0.0.1:5432/Travelprofitai`):

1. **PO Budget Reservation Race (`ProcurementBudget` `SELECT ... FOR UPDATE`)**:
   - **Scenario:** 4 concurrent threads each create a `₹20,000.00` Purchase Order against a single `₹50,000.00` `ACTIVE` budget.
   - **Observed Result:** Exactly **2 threads succeeded** (`reserved_amount_inr == Decimal("40000.00")`) and **2 threads raised `BadRequestException`** ("Insufficient available budget"). Zero budget over-allocation.
2. **MLOps Concurrent `CANARY` Deployment Race (Phantom-Insert Defect Remediated)**:
   - **Initial Defect Discovered:** Under PostgreSQL `READ COMMITTED`, locking `ModelDeployment` alone returned 0 rows when no canary existed yet, allowing 2 concurrent threads to both insert active `CANARY` deployments (`assert 2 == 1` failure).
   - **Fix Applied & Verified:** Serialized `create_deployment` by locking `MLModel` rows of `model.model_type` in deterministic primary-key order (`order_by(MLModel.id.asc()).with_for_update()`).
   - **Observed Result:** Exactly **1 thread succeeded** and **1 thread raised `ConflictException` (`409`)**.
3. **Concurrent Refresh Token Rotation Reuse Detection**:
   - **Scenario:** 2 concurrent threads call `AuthService.rotate_refresh_token` on the exact same `RefreshToken`.
   - **Observed Result:** Exactly **1 thread succeeded** and **1 thread failed with `AuthenticationError`**.
4. **Concurrent Supplier Portal Idempotent Push (Race Defect Remediated)**:
   - **Fix Applied & Verified:** Serialized `SupplierPortalService.push_rates_and_availability` with a `Supplier` row lock (`with_for_update()`) prior to checking `SupplierRateSyncLog`.
   - **Observed Result:** 3 concurrent threads pushing with the same `Idempotency-Key` converged cleanly on **1 canonical `SupplierRateSyncLog.id`** with zero `UniqueViolation` errors.
5. **Cross-Thread Notification Session Race & Enum Safety (Remediated)**:
   - Eliminated request `Session` sharing across asyncio event-loop threads in `NotificationService.notify_sync` and prevented PostgreSQL `InvalidTextRepresentation` (`FINANCE_USER`/`EXECUTIVE`) aborts by filtering against `UserRole` enum values.

**Post-Test Database Cleanliness:** Verified `0` leftover `STG13` test rows remain across all PostgreSQL tables after teardown.
