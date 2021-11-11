# T13 — Make email, push and account-job delivery safe under concurrent workers

**User instruction:** I want you to make delivery workers safe when leases expire, recipients unsubscribe, accounts are deleted, or two workers process the same job.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 8 hours |
| Proposed window | D2–D3 (2026-11-13–2026-11-16) |
| Worker slot | D |
| Dependencies | [T01](T01-isolated-verification.md) |
| Required review | mandatory concurrency/security review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | delivery-workers |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Rental email uses a lease timestamp and acknowledges after network I/O; auth jobs use compare-and-set claiming but no per-attempt fence in the final acknowledgement. Inspect all delivery paths and reproduce races before making shared changes.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T13/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/email_alerts.py`
- `backend/realtoruch/auth_jobs.py`
- `backend/realtoruch/push.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/auth.py`
- `backend/tests/test_email_alerts.py`
- `backend/tests/test_push.py`
- `backend/tests/test_accounts.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/email_alerts.py`
- `backend/realtoruch/auth_jobs.py`
- `backend/realtoruch/push.py`
- `backend/realtoruch/models.py (delivery fields)`
- `backend/realtoruch/auth.py (AuthJob fields only)`
- `infra/sql/008_delivery_leases.sql (new)`
- `infra/sql/005_delivery_leases_auth.sql (new)`
- `infra/sql/migrations.json`
- `backend/tests/test_delivery_races.py (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Use a unique attempt/claim token for every job claim and conditional acknowledge/retry updates requiring that token. A stale worker must not clear a new owner’s lease or resurrect a cancelled job.

2. Use PostgreSQL row locking and an atomic SQLite-compatible claim. Keep transport I/O outside database transactions; bound lease duration, transport timeout and exponential retry attempts.

3. Handle missing delivery/user/notification/subscription rows after transport returns. Deletion/unsubscribe/read/delist/unlike invalidations must not crash the worker or re-enable delivery.

4. Preserve stable logical notification identities and Message-IDs. Explain the unavoidable SMTP ambiguity if a process dies after acceptance but before acknowledgement; do not claim exactly-once physical email.

5. Keep account erasure jobs retrying until completed; mail attempts remain bounded. A disabled email transport must not starve due account-erasure jobs behind mail jobs.

6. Add sanitized per-status/attempt diagnostics for T26. Do not log recipient addresses, link tokens, push endpoints or SMTP credentials. Preserve Expo receipt handling and avoid resending accepted tickets while awaiting receipts.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

## Acceptance criteria

- **T13-AC01:** Concurrent healthy workers claim a logical delivery once and produce one normal transport attempt.

- **T13-AC02:** A stale acknowledgement/retry cannot alter a replacement claim or a cancellation.

- **T13-AC03:** Unsubscribe/delete/read/delist/unlike during dispatch causes no crash or later replay of cancelled work.

- **T13-AC04:** Mail retries remain bounded; erasure remains retryable and is not blocked by disabled mail.

- **T13-AC05:** Logical notification uniqueness survives process restart; uncertain transport acceptance is documented accurately.

- **T13-AC06:** Existing email confirmation/unsubscribe and push receipt semantics remain intact without private diagnostics leakage.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T13-TC01 — covers T13-AC01

**Given:** Two PostgreSQL and two SQLite workers target one due job.

**When:** Synchronize claim attempts.

**Then:** Exactly one claim owns the attempt; one normal send occurs.

### T13-TC02 — covers T13-AC02

**Given:** A’s lease expires, B claims, then A returns.

**When:** A acknowledges or schedules retry.

**Then:** B’s claim and status are unchanged.

### T13-TC03 — covers T13-AC03

**Given:** Subscription/delivery/account removed between send and acknowledge.

**When:** Complete transport callback.

**Then:** No AttributeError/rollback loop; no recreated or re-enabled row.

### T13-TC04 — covers T13-AC03, T13-AC06

**Given:** Notification read, home delisted or favorite removed before a due send.

**When:** Run dispatcher.

**Then:** Delivery is cancelled according to existing policy; no send.

### T13-TC05 — covers T13-AC04

**Given:** Disabled email with pending mail followed by due erasure.

**When:** Run account worker.

**Then:** Erasure is processed; mail remains pending/cancelled by documented policy.

### T13-TC06 — covers T13-AC04, T13-AC05

**Given:** Repeated transient errors and simulated crash after SMTP acceptance.

**When:** Restart and exhaust retry policy.

**Then:** One logical notification; bounded attempts and explicit at-least-once transport caveat.

### T13-TC07 — covers T13-AC06

**Given:** Accepted Expo ticket and delayed receipt.

**When:** Run multiple dispatch cycles.

**Then:** No resend while receipt is pending; receipt reconciliation remains correct.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_delivery_races.py backend/tests/test_email_alerts.py backend/tests/test_push.py backend/tests/test_accounts.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Fenced delivery state transitions and migrations
- Controlled race/crash tests for both databases
- Operational retry and uncertain-delivery notes
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No real external email/push send; T30 owns real email validation.
- Do not promise physical exactly-once delivery from SMTP.
