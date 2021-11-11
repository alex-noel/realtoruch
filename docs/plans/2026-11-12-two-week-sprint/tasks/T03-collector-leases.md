# T03 — Fence collector ownership and keep leases alive during slow or empty runs

**User instruction:** I want you to make collection safe when a worker stalls, crashes, receives no usable records, or loses its lease to another worker.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 8 hours |
| Proposed window | D2–D3 (2026-11-13–2026-11-16) |
| Worker slot | B |
| Dependencies | [T01](T01-isolated-verification.md) |
| Required review | mandatory concurrency review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | collector-runner |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

collection_health.py has a 30-minute source lease and worker.py renews it only when a record is yielded. Inspect and reproduce the consequences before changing behavior. A stale worker must not keep writing after a replacement starts.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T03/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/worker.py`
- `backend/realtoruch/connectors.py`
- `backend/realtoruch/models.py`
- `backend/tests/test_collection_health.py`
- `backend/tests/test_collection_cloud.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/worker.py`
- `backend/realtoruch/connectors.py (progress/cancellation hooks only)`
- `backend/tests/test_collection_health.py`
- `backend/tests/test_service_integration.py`
- `docs/source-connectors.md`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Use the existing run/lease ID as a fencing token. Heartbeat and finish must update only the currently owned lease, with atomic database predicates. Renew on elapsed time while discovering, pacing and fetching, not only when a valid advert is emitted.

2. Use one cooperative heartbeat mechanism with an injected clock/scheduler for tests. Set a documented interval no greater than 60 seconds, comfortably below the lease duration; do not spawn an unbounded thread per URL.

3. Check ownership before each new outbound request and before committing an observation. If lease ownership is lost, stop that run, classify it as interrupted/lease_lost and preserve the replacement’s state.

4. Keep provider pacing global within one leased provider even when cities differ. Preserve independent concurrency across Otodom, Gratka and Morizon; do not increase source request budgets.

5. A stale completion may finalize its own historical run as interrupted, but must not clear the new owner’s lease, retry-after, failure count or success timestamp.

6. Test PostgreSQL with two separate sessions/processes and deterministic synchronization barriers, not only SQLite or arbitrary sleeps. Leave cloud coordination unchanged and explicitly documented until a cloud-specific contract is implemented.

7. An HTTP request already in flight when ownership changes may still complete; fence its result at commit time. Do not promise network-level cancellation or atomicity between a SQL lease check and an external HTTP server.

## Acceptance criteria

- **T03-AC01:** Only one worker owns a provider’s collection lease at a time.

- **T03-AC02:** A run taking longer than one lease duration with zero emitted records remains owned while heartbeats succeed.

- **T03-AC03:** After detected lease loss the worker starts no new requests; after takeover no observation can commit under the old token, including results from an already in-flight request.

- **T03-AC04:** Finishing the old run cannot change the replacement’s lease or health state.

- **T03-AC05:** Kraków and Warszawa health remain distinguishable while sharing the provider request budget.

- **T03-AC06:** Interruption/restart does not create duplicate observations, alerts or inactive status from transport failure.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T03-TC01 — covers T03-AC01

**Given:** Two PostgreSQL workers claim the same provider simultaneously.

**When:** Release a start barrier.

**Then:** Exactly one owns the lease; the other reports already_running.

### T03-TC02 — covers T03-AC02

**Given:** A fake clock and a discovery stream with no valid records.

**When:** Advance beyond 30 minutes while heartbeat callbacks run.

**Then:** Lease stays current; run is not falsely interrupted.

### T03-TC03 — covers T03-AC03, T03-AC04

**Given:** Worker A stalls, its lease expires, and worker B claims.

**When:** Resume A’s fetch/commit/finish path.

**Then:** A's late result/finish is fenced and it starts no new request after detecting loss; B's ID, retry state and last-success remain unchanged.

### T03-TC04 — covers T03-AC05

**Given:** Kraków run expires and Warszawa replacement is active.

**When:** Read health for each city.

**Then:** Old run reports interrupted; replacement reports running.

### T03-TC05 — covers T03-AC06

**Given:** A worker crashes after committing one observation.

**When:** Restart and replay the same observation.

**Then:** Receipt/history/canonical data remain idempotent; no new notification.

### T03-TC06 — covers T03-AC02, T03-AC06

**Given:** Heartbeat database write fails while a request is pacing.

**When:** Advance to the next request boundary.

**Then:** Run stops safely and exposes a bounded diagnostic; no false delisting.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_collection_health.py backend/tests/test_collection_cloud.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Reproduction tests and fix
- Documented lease state transitions and restart command
- PostgreSQL race-test evidence
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No provider concurrency increase, anti-bot workaround or cloud scheduler deployment.
- Do not treat source disappearance or HTTP errors as removal.
