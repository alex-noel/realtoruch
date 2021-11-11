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

## Authentication-review corrections (2026-11-11 CET)

Independent review reproduced two failures on the first implementation: a delayed refresh resurrected a confirmed logout, and an old account's delayed 401 could replay a mutation under a new account. Both supplied regressions are preserved and now pass. Auth intent generations fence sign-in, invalidation, logout, network results and retries; refresh rotation retains the same intent. SecureStore operations are serialized and fenced before and after writes, with barrier tests for logout and account switch during a write. The UI consumes signed-out and cleanup events and does not replace reauthentication with offline state after a failed rotated-token write. Empty native storage publishes signed-out. Bounded validation feedback only includes known messages or allowed field names.

Web refresh, login/register and logout use the same Web Lock to order actual cookie mutations as well as JS state; logout can refresh inside its held lock without nesting. Controlled tests model refresh-versus-login, refresh-versus-logout and a refresh queued behind logout. Real browser behavior remains T18 work. On confirmed logout, local state clears before storage deletion. A cleanup failure has a distinct visible outcome and blocks same-instance restoration. If storage is unavailable across a process restart, local deletion cannot be guaranteed; server revocation remains authoritative and prevents restoration of the revoked credential.

Final rerun from `apps/mobile`: `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH npm run test:unit -- session` — 17 passed, 0 failed, 0 skipped; `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH npm run typecheck` — exit 0, no diagnostics. Root: `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_accounts.py -q` — 7 passed, 0 failed, 0 skipped, same dependency deprecation warning. During correction an intermediate run had 7 passed and 2 failed; both were corrected before the final run. Independent authentication re-review is required before acceptance.

## Parent integration review

On 2026-11-11 at approximately 22:00 Europe/Warsaw, the parent accepted the implementation as a dependency, retaining LOCAL_PARTIAL until T18 supplies real browser evidence. Account deletion now shares the auth-cookie lock and intent check, with a further deletion-versus-new-login regression. Independently repeated: 18 frontend tests passed, TypeScript passed, and 7 backend account tests passed; zero skips.

The initially proposed Vitest 3.2.4 was rejected by the dependency audit. The final pinned runner is **4.1.12**, which removes the added critical findings; a standard `npm ci --ignore-scripts` succeeds, and all pre-existing locked package versions remain unchanged. Resolving the new runner initially hit npm 11.5.1's optional-peer resolver error; lock generation with `--legacy-peer-deps` succeeded, then normal `npm ci` and checks passed without that option. Four existing moderate npm package findings remain. The rejection is supported by the [Vitest advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-5xrq-8626-4rwp) and [Tinypool advisory](https://github.com/tinylibs/tinypool/security/advisories/GHSA-85c8-ppgw-ccpr); this is a test dependency change, not an Expo/React upgrade. T17/T19/T21 must use the final shared runner.
