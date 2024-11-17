# Q18 — Private collection loading

Status: IMPLEMENTED_LOCAL; independent privacy/state review pending.

Base: 931ae30e05b2e148ae5f230e84987d7e417644f3; branch: codex/q18. Changes: `App.tsx`, `useAccountCollections.ts`, `accountCollections.test.ts`. Favorites, saved searches and notifications now load independently, retain successful data on refresh failures, identify stale data and offer individual retry. Initial loading, failure and successful empty states are distinguished. Reset fences all old requests, and inbox refresh preserves loaded older pages and deduplicates overlapping items. No API, schema, configuration or dependency changes.

| Acceptance | Evidence |
| --- | --- |
| AC01 | PASS: controlled-response test injects failure independently for each collection, verifies the others succeed and distinguishes loading from successful empty. |
| AC02 | PASS: controlled-response retry/failure test retains data; UI labels retained data as potentially out of date and offers retry. Inbox page-merge test covers overlap; out-of-order refresh and mutation tests check request sequencing. |
| AC03 | PASS: reset tests clear all collections and resolve old responses for each collection after new requests; existing desktop and mobile stale-tab account-switch browser regressions pass. Independent privacy review pending. |

## Verification

Actual time: 2026-11-17 15:27 CET. Node v23.6.0, Python 3.12.9. All commands ran in the isolated checkout against synthetic fixtures.

| Command | Result |
| --- | --- |
| `cd apps/mobile && npm run test:unit -- tests/accountCollections.test.ts tests/session.test.ts` | 48 passed, exit 0. |
| `cd apps/mobile && npm run typecheck` | exit 0. |
| `source .venv/bin/activate && cd apps/mobile && VERIFY_RUN_ID=q18-final-20261117 npm run test:e2e -- journey.spec.ts smoke.spec.ts` | 8 passed (desktop/mobile), exit 0; includes synthetic journey, reload/sign-out and account-switch regression. Isolated evidence under ignored `.local/verification/T18/q18-final-20261117`. |
| `git diff --check` | exit 0. |

The first browser attempt was sandbox-blocked from binding loopback; the successful run used approved isolated loopback access. The harness did not capture before/after UI screenshots; visual review remains outstanding. No external services, real accounts or mail were used. No migration or recovery action is required. Session generation and explicit collection reset both prevent old-account responses from repopulating private views; existing notification pagination and mutation handlers are retained. Required strong private-state/session review remains with the integrator. No provider or device checks claimed.
