# Stage 14 Remaining Remediation Report

## Git baseline

Continued from commit `e2f220e` (`Half of bugs are fixed now in the stage 14`) and preserved its supplier/socket changes.

## Fixed and verified

| Severity | Area | Root cause | Fix |
|---|---|---|---|
| Critical | Notifications | Recipient role constants included names absent from `UserRole` and event defaults could generate invalid role resolution | Reduced notification role mappings to `ADMIN`, `PROCUREMENT_MANAGER`, and `ANALYST`, matching the actual enum |
| Critical | Notifications | Identical role and user resolution could cause duplicate Socket.IO emissions | Removed role-room notification broadcasts; persistence and emission now resolve to and emit only to persisted user recipients |
| High | Notifications | Idempotency was reserved before persistence and persistence failure suppressed retries | Idempotency is reserved only after a successful database commit |
| High | Notifications | Connected users were persisted as `SENT` even though no acknowledgement occurred | Initial delivery status is now `PENDING`; acknowledgement remains the transition to `DELIVERED` |
| Critical | Treasury | Forward creation accepted client spot-rate and source values | FX forward creation now ignores client spot-rate fields and selects the verified `ExchangeRate` by trade-date currency pair; request payload rejects extra fields |
| High | Treasury | Hedge effectiveness always used the latest rate, not the measurement-date rate | Added point-in-time exchange-rate lookup using `as_of_date <= measurement_date` |
| High | Treasury | Execution could proceed and silently retain stale MTM on missing/stale spot rates | FX execution now requires a fresh verified rate and blocks execution otherwise |
| High | Treasury | Stale rates were never bounded by a freshness policy | Added `FX_RATE_MAX_AGE_DAYS=7` and freshness validation |
| Critical | MLOps | Training API stored fake `celery_task_id` values and reported PENDING although no worker existed | Removed fake task IDs and changed the audit/notes to state that no executable worker dispatched the job |
| High | MLOps | Cancellation changed jobs to `FAILED` instead of `ABORTED` | Cancellation now sets `ABORTED` |
| High | Configuration | Production validator did not reject SQLite or inadequately long worker secrets | Production now rejects SQLite, malformed database URLs, wildcard CORS, weak secrets, and weak worker tokens |
| High | Notifications | Explicit recipient IDs could include nonexistent users and cause FK/persistence failures | Recipient resolution now intersects explicit recipients with active database users |

## Additional findings

Confirmed no Celery package, task consumer, or worker implementation exists in the backend. Existing pipeline and training code contains synthetic task identifiers and is not a real queue workflow. This remains an implementation limitation rather than a fake success.

The hedge-effectiveness implementation is explicitly a simplified dollar-offset ratio and must not be represented as full IFRS 9 or IAS 39 compliance.

## PostgreSQL verification

No local PostgreSQL service was available in the executed environment. The enterprise PostgreSQL-specific test module was inspected but not executed against a live PostgreSQL instance. SQLite test execution and compilation passed for the remediation scope.

## Migrations

No schema migration was required.

