# Stage 14 Regression and Verification Report

## Executed verification

| Command | Result |
|---|---|
| `python -m compileall -q backend/app modeling optimization feature_engineering ml_engine data_pipeline eda` | Passed |
| `pytest -q backend/tests/test_socketio_notifications.py` | Passed, 16 tests |
| `pytest -q backend/tests/test_enterprise_domains_services.py backend/tests/test_enterprise_apis_rbac.py` | Passed, 15 tests |

## Regressions added or corrected

- Socket.IO authentication tests now use real active database users and no longer rely on JWT claims alone.
- Live ASGI Socket.IO test uses an actual database-backed user and acknowledges the user-specific notification.
- Notification idempotency test now supplies a real persisted recipient.
- Existing Socket.IO and enterprise suites verify database-backed current identity and role behavior.

## Test limitation

The broad baseline command was not rerun as a final all-repository suite. A complete PostgreSQL transaction/locking/enum run requires a live PostgreSQL test configuration and was not started in accordance with infrastructure restrictions.

