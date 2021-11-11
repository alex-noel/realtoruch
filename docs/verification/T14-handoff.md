# T14 session resilience handoff

- Status: IMPLEMENTED_LOCAL; authentication review and real browser verification remain outstanding.
- Base: e2577067c2ea9bd16d97d7f457944baa8ff6df1e. Result: the commit containing this report, created with `python3 scripts/commit.py`.
- Actual verification: 2026-11-11 Europe/Warsaw (CET), macOS, Node 24.6.0, Python 3.12.9.
- A transient outage preserves native refresh material and exposes retry; confirmed invalidity clears account state. Integrator approved minimal App.tsx wiring.

## Changes and recovery

`apps/mobile/src/api.ts` adds classified errors, per-instance single-flight, locked web refresh, observable session states, and bounded retry. `App.tsx` displays retry/reauthentication and clears private account lists/dialog on invalidation. `tests/session.test.ts` supplies isolated mocked platform/storage/network/lock tests; package files pin Vitest 3.2.4 and expose `npm run test:unit`. `backend/tests/test_accounts.py` adds a production cookie assertion. No schema, migration, or API contract changes. Existing server single-use rotation/replay policy is unchanged.

A refresh response lost after server consumption is ambiguous: retain the native credential for a transient failure, but the next attempt can detect replay, revoke the family and require password sign-in. No grace or JS-readable web refresh storage is introduced. Browsers without Web Locks must sign in again instead of attempting a risky automatic refresh. A SecureStore read failure retains stored values; inability to persist a rotated token requires sign-in. Revert the application changes to roll back; no data migration is required.

## Acceptance and test cases

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC01 | PASS locally | TC01: fake SecureStore 503 then successful retry, unit suite. |
| AC02 | PARTIAL | TC02: ten delayed 401s, one refresh, all ten retries carry rotated access; TC03 simulated two instances serialize against shared cookie. Real multi-tab browser verification belongs to T18 and has not run. |
| AC03 | PASS locally | TC03 deliberate old-token replay invalidates family and protected endpoint; backend account suite uses SQLite and in-process clients. |
| AC04 | PASS locally | TC04 backend revocation/reset/deletion deny access immediately; TC05 unit suite tests offline logout, retry and invalidity; App subscription clears private state. UI interaction itself remains for T18. |
| AC05 | PASS locally | TC06 account suite verifies production Secure, HttpOnly, Strict and scoped cookie plus hostile/missing Origin rejection. |
| AC06 | PASS locally | TC01, TC05, TC07 and storage/no-lock tests; a lost response then rejected replay transitions to reauthentication, with no secret emitted by test output. |

## Verification

Commands were run in this checkout; all exit 0 and no tests skipped:

- Root: `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_accounts.py -q` — 7 passed, 0 failed, 0 skipped; SQLite and FastAPI in-process clients, one dependency deprecation warning.
- `apps/mobile`: `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH npm run typecheck` — passed, 0 diagnostics.
- `apps/mobile`: `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH npm run test:unit -- session` — 1 file, 7 passed, 0 failed, 0 skipped. A deferred refresh gates ten 401 responses; lock test queues two separate modules against a shared fake cookie, then backend test separately verifies replay revocation.
- Root: `git diff --check` — passed. No existing package versions changed in the lock.

The initial attempt to edit App from the mobile working directory used an incorrect path and failed before changing files; rerun with the correct path succeeded. No cloud, real email, live portal or installed device was used. Test fixtures are synthetic. No credentials or private artifacts were retained.

## Review and remaining work

The integrator must review auth/session security and merge App/api/package-lock changes with T02/T18/T19/T21. T18 must verify actual browser Web Locks/cookie behavior, visible logout retry and private UI clearing across tabs; simulated locks are not browser evidence. Native tests mock SecureStore; installed iOS/Android behavior is not claimed. The server continues to treat true replay as family compromise. Offline logout cannot confirm remote revocation; the visible retry remains available. Do not push or deploy as part of this handoff.
