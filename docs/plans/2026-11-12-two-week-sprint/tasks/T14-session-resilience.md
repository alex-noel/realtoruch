# T14 — Preserve safe sign-in behavior across tabs, offline periods and revocation

**User instruction:** I want you to harden account sessions so a brief outage does not discard a valid native refresh credential, and simultaneous requests do not create refresh/revocation bugs.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D3 (2026-11-16) |
| Worker slot | A |
| Dependencies | [T01](T01-isolated-verification.md) |
| Required review | mandatory authentication review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | auth-service, frontend-api-client, frontend-dependencies |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Web refresh tokens are HttpOnly cookies, native tokens use SecureStore, and api.ts serializes refresh attempts. restoreToken currently clears tokens on any error. Preserve these boundaries and the existing single-use rotation/replay policy.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T14/<run-id>/`; commit sanitized reports only.

## Read first

- `apps/mobile/src/api.ts`
- `apps/mobile/src/components/AccountDialog.tsx`
- `backend/realtoruch/auth.py`
- `backend/realtoruch/security.py`
- `backend/tests/test_accounts.py`
- `apps/mobile/src/App.tsx`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/api.ts`
- `apps/mobile/src/session.ts (new extraction if helpful)`
- `apps/mobile/src/components/AccountDialog.tsx`
- `backend/realtoruch/auth.py (session endpoints only)`
- `backend/tests/test_accounts.py`
- `apps/mobile/tests/session.test.ts (new)`
- `apps/mobile/package.json and package-lock.json (shared unit-test runner only)`
- `apps/mobile test-runner configuration and test setup (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Introduce typed HTTP/session errors separating 401/403 from timeout/network/503. On transient restore failure, preserve native stored refresh material and expose an offline/retry state; never persist web refresh tokens in JS-readable storage.

2. Keep one refresh in flight per app instance and cross-tab coordination where supported. Specify a safe fallback for browsers without Web Locks; do not weaken server replay detection to hide client races.

3. Bound refresh retries and avoid recursion on the refresh endpoint itself. Requests must use the new access token after a successful rotation; stale in-flight 401 responses must not consume a refresh token twice.

4. Logout must clear local account/UI state when the server confirms revocation or the session is already invalid. Distinguish an unreachable server from confirmed revocation; retain a visible retry outcome rather than falsely claiming remote logout.

5. Test reset/revocation/deletion invalidating access immediately, cookie attributes/origin checks, native storage failures and a lost refresh response. Require re-authentication when safe recovery from a consumed token is impossible.

6. Keep passwords/tokens out of console logs, reports, URL query strings and screenshots. Do not add social login or expand session lifetime.

7. Establish one pinned frontend unit-test command, npm run test:unit, compatible with the installed React/Expo/TypeScript versions. Provide mocked web storage, SecureStore, network and app-state adapters. Add only the dev dependency/config/scripts needed for these meaningful session tests; T17/T19/T21 reuse this runner and T18 owns browser tests.

## Acceptance criteria

- **T14-AC01:** A transient auth outage does not erase a still-valid native refresh credential.

- **T14-AC02:** Parallel API requests trigger at most one refresh per instance, and supported multi-tab refreshes do not spuriously revoke the session.

- **T14-AC03:** A true refresh replay revokes the session family; invalid sessions cannot access account endpoints.

- **T14-AC04:** Logout/revocation outcomes are truthful and local private UI is cleared on confirmed invalidation.

- **T14-AC05:** Web cookies remain HttpOnly/path-scoped/SameSite=Strict and Secure in production; disallowed origins fail.

- **T14-AC06:** Offline/retry/re-authentication states have deterministic tests and contain no credential leakage.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T14-TC01 — covers T14-AC01, T14-AC06

**Given:** Valid native refresh stored in a fake SecureStore and auth returns 503.

**When:** Restore then retry after recovery.

**Then:** Credential survives outage; recovery works without registration or password re-entry.

### T14-TC02 — covers T14-AC02

**Given:** Ten requests receive 401 while token is expired.

**When:** Resolve one delayed refresh.

**Then:** One refresh call; all retried requests use the rotated access token.

### T14-TC03 — covers T14-AC02, T14-AC03

**Given:** Two browser tabs with supported locks, then a deliberate reused refresh token.

**When:** Refresh concurrently and later replay old token.

**Then:** Tabs succeed normally; deliberate replay invalidates the family.

### T14-TC04 — covers T14-AC03, T14-AC04

**Given:** Another device revokes the current session or password is reset.

**When:** Retry account request and sign out.

**Then:** No protected data; local UI clears on confirmed invalidity.

### T14-TC05 — covers T14-AC04, T14-AC06

**Given:** Network goes offline during logout.

**When:** Inspect user-visible status and subsequent retry.

**Then:** App does not claim confirmed server revocation; retry remains possible.

### T14-TC06 — covers T14-AC05

**Given:** Production response and hostile/missing Origin.

**When:** Inspect Set-Cookie and request refresh.

**Then:** Required cookie flags present; disallowed browser request rejected.

### T14-TC07 — covers T14-AC06

**Given:** Refresh response lost after token consumption.

**When:** Retry according to documented policy.

**Then:** No insecure replay grace; clear re-authentication state and no infinite loop.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_accounts.py -q`
- `cd apps/mobile && npm run typecheck`
- `cd apps/mobile && npm run test:unit -- session`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Typed session error/restore handling and regression tests
- Documented offline/lost-response policy
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No localStorage/sessionStorage refresh-token storage.
- No social sign-in, new identity provider or relaxed replay rules.
