# T15 — Prevent account-data resurrection and add a scoped data export

**User instruction:** I want you to make account deletion durable even when requests are already in flight, and let an authenticated user export their own account data without exposing another user’s private information.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 8 hours |
| Proposed window | D5–D6 (2026-11-18–2026-11-19) |
| Worker slot | D |
| Dependencies | [T10](T10-identity-correctness.md), [T13](T13-delivery-fencing.md), [T14](T14-session-resilience.md) |
| Required review | mandatory privacy/data review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | account-erasure, canonical-writes, public-api |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Auth disables an account immediately and queues rental-data cleanup. Cross-service requests authorized just before deletion can race cleanup. Existing erasure retains non-account property price history; preserve that explicit boundary.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T15/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/api.py (internal account cleanup)`
- `backend/realtoruch/auth.py`
- `backend/realtoruch/auth_jobs.py`
- `backend/realtoruch/security.py`
- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/models.py`
- `backend/tests/test_accounts.py`
- `backend/tests/test_marketplace.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/account_data.py (new)`
- `backend/realtoruch/api.py (router/cleanup integration)`
- `backend/realtoruch/marketplace.py (account write guard hooks)`
- `backend/realtoruch/email_alerts.py (guard hook only)`
- `backend/realtoruch/models.py`
- `infra/sql/009_account_closure.sql (new)`
- `infra/sql/migrations.json`
- `backend/tests/test_account_data.py (new)`
- `docs/privacy-data-map.md (new)`
- `backend/realtoruch/auth.py (scoped password reauthentication for own-data export only)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Introduce a private rental-side account-closure fence/tombstone and one shared transactional write guard. Account-owned writes must acquire the same per-user serialization boundary as cleanup and reject a closed account even if introspection happened before closure.

2. Cover favorites, seen state, saved searches, reports, subscriptions, profile/adverts and conversation creation/replies. Account deletion must remain idempotent and retryable across partial service failures.

3. Retain only the minimum opaque closure evidence needed to prevent resurrection; do not store deleted email/password/contact data in the tombstone. Document its retention/recreation semantics: a new registration gets a new ID.

4. Add an authenticated, password-reauthenticated bounded export containing the user’s own settings, favorites, searches, seen records, own adverts and messages they sent. Include only public reference identifiers for other participants; exclude their private messages/emails and all hashes/tokens/credentials.

5. Produce the export from a consistent read snapshot with a maximum size and explicit pagination/job status if necessary. Do not email exports or expose them at a public URL; download must be account-scoped and no-store.

6. Document what remains: non-account market observations, minimal audit/closure records and time-limited backups. Add a restore rehearsal scenario showing a pending erasure completes after recovery; this is engineering behavior, not a legal compliance certification.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

8. Define a concrete bounded export contract before implementation: POST /v1/auth/reauthenticate accepts the current password and returns a short-lived purpose=account_export token bound to user/session; GET /v1/me/export requires normal auth plus that token in a dedicated header. Default expiry is five minutes, with no tokens in query strings. Return a versioned JSON export capped at 10 MiB; if over the cap, return a documented explicit error and a follow-up requirement rather than truncating data or adding a new background export service in this task.

## Acceptance criteria

- **T15-AC01:** A request authorized before deletion cannot recreate private rental data after cleanup commits.

- **T15-AC02:** Repeated cleanup succeeds without orphan messages, subscriptions, draft payloads or own-advert personal content.

- **T15-AC03:** Closed-account access is rejected; a new account ID does not inherit the deleted account’s private data.

- **T15-AC04:** Export includes only the requesting user’s allowed data and requires reauthentication.

- **T15-AC05:** Export is bounded, consistent and unavailable to another account or anonymous caller.

- **T15-AC06:** Deletion/export/backup retention boundaries are documented and covered by tests.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T15-TC01 — covers T15-AC01

**Given:** Favorite/profile/message write pauses after auth but before SQL mutation.

**When:** Delete account, then release write.

**Then:** Write is rejected or completed before cleanup; no data exists after final cleanup.

### T15-TC02 — covers T15-AC02

**Given:** Cleanup fails halfway through an injected transaction/service outage.

**When:** Retry job twice.

**Then:** Rollback/retry is safe; final account-owned records are removed once.

### T15-TC03 — covers T15-AC03

**Given:** Deleted email re-registers with a new generated user ID.

**When:** Read saved data and attempt old-ID operations.

**Then:** New account starts empty; old closure remains effective.

### T15-TC04 — covers T15-AC04, T15-AC05

**Given:** Two users with private conversations and distinct canary data.

**When:** Export as one user with correct/wrong password.

**Then:** Correct export contains only allowed own data; wrong password/other user fails.

### T15-TC05 — covers T15-AC05

**Given:** Export dataset exceeds configured size and changes concurrently.

**When:** Request export.

**Then:** Bounded documented result; snapshot is internally consistent and no partial secret dump.

### T15-TC06 — covers T15-AC06

**Given:** Backup contains pending erasure and is restored into isolation.

**When:** Resume erasure worker.

**Then:** Cleanup converges without reactivating notifications or withdrawing unrelated homes.

### T15-TC07 — covers T15-AC04, T15-AC05

**Given:** Valid ordinary session without export-purpose reauthentication, then expired/wrong-user purpose token and an oversized export fixture.

**When:** Request export for each case.

**Then:** Access is rejected safely or the explicit size-limit error is returned; no partial/private payload leaks.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_account_data.py backend/tests/test_accounts.py backend/tests/test_marketplace.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Transactional closure guard, export endpoint and migration
- Cross-service race tests
- Data-retention/export map and restore case
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not delete unrelated imported market data or other accounts’ entire history.
- No third-party privacy/legal certification, new document-verification system or unsolicited data export.
