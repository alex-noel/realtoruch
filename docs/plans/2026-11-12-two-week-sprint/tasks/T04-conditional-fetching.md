# T04 — Reduce download volume with conditional requests and bounded retries

**User instruction:** I want you to reduce unnecessary listing downloads while preserving accurate freshness, price history and source-specific request limits.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D3–D4 (2026-11-16–2026-11-17) |
| Worker slot | B |
| Dependencies | [T03](T03-collector-leases.md) |
| Required review | network/data review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | collector-runner, source-state |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The collector already skips fresh records and keeps one unchanged daily checkpoint. It does not retain HTTP validators or Retry-After timing. A 304 response must only reuse a known valid representation, never invent a listing.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T04/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/connectors.py`
- `backend/realtoruch/worker.py`
- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/ingest.py`
- `backend/tests/test_connectors.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/connectors.py`
- `backend/realtoruch/worker.py`
- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/models.py (reserved fetch-state addition)`
- `infra/sql/005_collection_fetch_state.sql (new)`
- `infra/sql/migrations.json`
- `backend/tests/test_connectors.py`
- `backend/tests/test_collection_cloud.py`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Persist ETag/Last-Modified and representation provenance privately per source plus canonical URL. Bound stored header lengths; do not persist Authorization, cookies or raw phone numbers. Use reserved migration 005 for rental state if needed.

2. Send If-None-Match/If-Modified-Since only for the same source URL with a previously validated payload. A 304 may advance checked freshness using that payload while unchanged-history limits and no-alert rules still apply.

3. For an orphan 304, make at most one unconditional retry inside the existing budget; if it still cannot be interpreted, report an error and leave canonical state unchanged.

4. Honor Retry-After delta seconds and HTTP-date for 429/503. Persist the defer time and exit the source; do not sleep a worker indefinitely or retry a 403. On timeouts/502, allow at most two bounded attempts with jitter, retaining provider pacing.

5. Account for every network attempt, including robots, retries and conditional requests, in run telemetry. Preserve the 5 MB page cap, HTTPS allowlist, redirect rejection and robots semantics.

6. Define cloud state payload compatibility with optional validator fields and fake-client tests only. Do not change the live enabled-source set or apply infrastructure.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

## Acceptance criteria

- **T04-AC01:** Unchanged supported pages transfer no body after a valid cached validator exists.

- **T04-AC02:** A 304 cannot create a new home or restore previously invalid/missing payloads.

- **T04-AC03:** Freshness advances without extra same-day unchanged history or notifications.

- **T04-AC04:** 429/503 backoff survives process restart; 403 stops without retry loops.

- **T04-AC05:** Retries never exceed the declared per-source request rate or attempt cap.

- **T04-AC06:** Legacy SQL/Bigtable payloads without validators remain readable and public responses expose no validator/credential metadata.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T04-TC01 — covers T04-AC01, T04-AC03

**Given:** A valid 200 page with ETag followed by 304.

**When:** Collect twice on the same day.

**Then:** Conditional header is present; freshness advances; history/notification counts do not.

### T04-TC02 — covers T04-AC02

**Given:** 304 for an unknown URL or mismatched cached URL.

**When:** Collect with one unconditional fallback.

**Then:** At most one fallback; no invented property if still invalid.

### T04-TC03 — covers T04-AC03

**Given:** A 304 on the next UTC day.

**When:** Ingest the reused valid representation.

**Then:** Exactly one unchanged daily checkpoint is retained.

### T04-TC04 — covers T04-AC04

**Given:** 429 with delta and date Retry-After variants.

**When:** Restart collector before and after the deadline.

**Then:** No early request; source becomes eligible after the stored deadline.

### T04-TC05 — covers T04-AC04, T04-AC05

**Given:** 403 and repeated timeout fixtures.

**When:** Run collection.

**Then:** 403 has no retry; timeout attempts are capped and paced.

### T04-TC06 — covers T04-AC05, T04-AC06

**Given:** A redirect carrying Authorization and a >5 MB stream.

**When:** Fetch through the adapter.

**Then:** Redirect/oversize fail; no forwarded credential or partial persistence.

### T04-TC07 — covers T04-AC06

**Given:** Legacy source state without validator fields.

**When:** Recheck and serialize publicly.

**Then:** Normal unconditional request succeeds; private fields are absent.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_connectors.py backend/tests/test_collection_cloud.py backend/tests/test_lifecycle.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Conditional-fetch implementation and migration if required
- Before/after request/body-byte evidence using controlled fixtures
- Updated source-report field contract
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No HTML caching service, credential harvesting or login-cookie automation.
- Do not use a 304 as proof of any fact not present in the validated cached representation.
