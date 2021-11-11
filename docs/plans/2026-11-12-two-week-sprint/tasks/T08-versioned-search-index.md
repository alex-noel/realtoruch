# T08 — Make search indexing monotonic, batched and safe under retries

**User instruction:** I want you to prevent an older indexing attempt from restoring stale prices or active status, and reduce indexing round trips without losing updates.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 10 hours |
| Proposed window | D2–D3 (2026-11-13–2026-11-16) |
| Worker slot | C |
| Dependencies | [T01](T01-isolated-verification.md) |
| Required review | mandatory concurrency/data review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | canonical-writes, search-index |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

worker.index_once reads canonical rows and writes documents one by one while its transaction owns outbox rows. The deployment currently requires one indexer. Add a verified ordering contract before allowing more than one worker.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T08/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/worker.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/search.py`
- `backend/realtoruch/query.py`
- `backend/realtoruch/identity_review.py`
- `backend/realtoruch/marketplace.py`
- `backend/tests/test_service_integration.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/indexing.py (new, preferred extraction)`
- `backend/realtoruch/worker.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/search.py`
- `infra/sql/006_search_revision.sql (new)`
- `infra/sql/migrations.json`
- `backend/tests/test_indexing.py (new)`
- `backend/tests/test_service_integration.py`
- `backend/realtoruch/identity_review.py (public-change revision hook only)`
- `backend/realtoruch/marketplace.py (public-change revision hook only)`
- `backend/realtoruch/api.py (account withdrawal/moderation revision hook only)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Introduce a positive monotonic canonical search revision assigned in the same SQL transaction as every public-document change. Cover ingestion, moderation, merge/split, account withdrawal and advertiser-profile changes; never use wall-clock timestamps as version counters.

2. Use bounded Elasticsearch bulk requests (default <=100 documents and <=5 MiB encoded payload). Inspect each item, not only the HTTP status. Batch-load source/profile data to avoid per-document query multiplication.

3. Use strict external versioning for document writes, verified against the installed Elasticsearch 8.19.6 server. Treat a version conflict as acknowledged only when the stored version is equal/newer; never use external_gte to overwrite equal revisions with different content.

4. Claim work with short SQL transactions and fencing/lease ownership as needed. Send network requests outside long-held canonical locks; acknowledge only revisions that were actually sent or superseded. A newer pending revision must remain pending.

5. Keep inactive/hidden alias tombstone documents with a newer revision so replay cannot resurrect discovery entries. Avoid deleting version evidence prematurely.

6. Provide a local rebuild command that populates a new index, checks counts/sample versions and switches an alias only after validation. Keep the current single-indexer deployment default until concurrency tests pass; no cloud reindex is executed.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

8. Measure healthy local index convergence after a committed batch of 100 changed homes: all expected revisions should be visible within 30 seconds on the declared four-core/8-GiB benchmark profile. Record the polling/refresh configuration and report an unmet target; never hide lag by returning a fabricated zero.

## Acceptance criteria

- **T08-AC01:** Older or duplicate writes never overwrite a newer indexed price/status.

- **T08-AC02:** Ingestion during an in-flight index request leaves the newer revision queued and eventually searchable.

- **T08-AC03:** Mixed-success bulk responses acknowledge successes only; retryable failures remain retryable.

- **T08-AC04:** Two indexers do not lose updates or resurrect hidden/delisted/merged homes.

- **T08-AC05:** Public indexed payloads contain only approved fields; profile changes produce a revision update.

- **T08-AC06:** The rebuild command can fail before alias switch without disrupting the existing index and can rebuild after a reset.

- **T08-AC07:** A healthy local batch of 100 committed changed homes reaches all expected search revisions within the declared 30-second convergence target.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T08-TC01 — covers T08-AC01

**Given:** Revisions 10 at 4,500 PLN and 11 at 4,200 PLN.

**When:** Deliver 11, then 10, then replay 11.

**Then:** Search remains 4,200; conflicts are handled without overwriting.

### T08-TC02 — covers T08-AC02

**Given:** Worker snapshots revision 12 and pauses before network completion.

**When:** Commit revision 13 and then release worker.

**Then:** 12 acknowledgement cannot consume 13; second pass indexes 13.

### T08-TC03 — covers T08-AC03

**Given:** Bulk response contains success, 429, mapping failure and version conflict.

**When:** Process acknowledgements.

**Then:** Each item receives the correct persisted status; no blanket success.

### T08-TC04 — covers T08-AC04

**Given:** Two PostgreSQL/indexer workers and a hide/delist transition.

**When:** Interleave work using barriers.

**Then:** Latest hidden/inactive state wins; no active result after convergence.

### T08-TC05 — covers T08-AC05

**Given:** Advertiser profile edit and private-data canaries.

**When:** Index affected homes.

**Then:** Display name updates; email, phone hash, draft and job secrets are absent.

### T08-TC06 — covers T08-AC06

**Given:** A rebuild fails after writing half the candidate index.

**When:** Inspect alias, then retry rebuild.

**Then:** Original alias remains usable until fully validated replacement succeeds.

### T08-TC07 — covers T08-AC02, T08-AC04, T08-AC07

**Given:** Healthy local SQL/Elasticsearch and 100 committed changed homes.

**When:** Run indexing with the documented polling/refresh settings.

**Then:** All expected revisions become visible within 30 seconds; otherwise AC07 is recorded as failed, with measured lag retained.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_indexing.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Revision migration, indexer implementation and rebuild command
- Real PostgreSQL/Elasticsearch ordering tests
- Documented maximum observed convergence time
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not deploy additional indexers or change Elasticsearch versions.
- No arbitrary public Elasticsearch DSL or port-9200 exposure.

## Primary technical references

- [Elasticsearch bulk/version semantics](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk).

Use these with the installed project versions; recheck current version-specific details before implementation.
