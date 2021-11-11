# T08 handoff — versioned search indexing

## Identity and outcome

- Task/status: T08, VERIFIED for local scope after independent concurrency/data review and the controlled reference-profile benchmark below.
- Base: `a74ca26`. Result: the commit containing this handoff, created with `python3 scripts/commit.py`.
- Actual work and verification: 2026-11-11, Europe/Warsaw (CET); all test timestamps below are actual UTC, independent of Git dates.
- Search projection writes use SQL revisions, bounded bulk requests and strict external versions. Pending work remains pending if a newer canonical revision appears during an in-flight request.
- The integrator approved a separate counter table to preserve T01's immutable SQLite baseline, and coordination with T13's cancellation hook.

## Changed files and contracts

- `backend/realtoruch/indexing.py`: transaction-scoped counters and pending-work coalescing; brief consistent snapshots; <=100 documents and <=5 MiB per NDJSON request; per-item acknowledgements; conflict GET verification; rebuild gate and alias switch.
- `ingest.py`, `identity_review.py`, `marketplace.py`: revision hooks for recomputation, merge tombstones, and profile edits. Existing withdrawal and moderation paths call recomputation in their transaction. The account-erasure path's withdrawal also uses it. `worker.py` delegates indexing and exposes `python -m realtoruch.worker rebuild-index`; collection code is unchanged. `search.py` changes the search target to `rentals-search`.
- `models.py`, `migrations.py`, `infra/sql/006_search_revision.sql`, `infra/sql/migrations.json`: rentals 006 creates `search_revisions` and `outbox.last_index_status`; existing homes receive revision 1 and pending work. The additive SQLite 006 hook runs after unchanged baseline 001. No applied migration or 001 hook checksum is changed. `Outbox` index metadata is unchanged.
- `test_indexing.py`, `test_service_integration.py`: mixed results, oversize fairness, public profile canaries, upgrades, races, rebuild and 100-change measurements.

Each public mutation increments its counter under a database row lock and keeps/creates pending work in the same transaction. Snapshot and acknowledgement transactions lock counter rows briefly; no canonical row lock is held during Elasticsearch requests. Acknowledgement rechecks the sent revision, so it cannot consume an update that arrived during network I/O. Inactive and alias records remain as documents; hidden entries are forced inactive. An ES 409 is acknowledged only after realtime GET confirms an equal/newer stored version. Status 429 remains retryable; 400 and locally detected oversize 413 remain pending but held, preventing head-of-queue starvation. A later mutation clears the hold. After fixing the cause, an operator may clear `last_index_status` on the affected pending outbox row to retry. Search remains eventually consistent.

The rebuild uses a PostgreSQL session advisory shared/exclusive gate: indexers hold shared across their pass, while rebuild holds exclusive through candidate validation and alias switch. Canonical writers continue and leave pending work for indexers after switch. SQLite uses a local cross-process file lock and is suitable only for a single machine. The operator must deploy the application/search and indexer with this coordinated protocol together; an old indexer which does not take the gate is unsafe during rebuild. Existing physical `rentals-v1` is never deleted: versioned indexing refuses to adopt it directly because internal ES versions do not establish the new revision contract. Run `python -m realtoruch.worker rebuild-index` before enabling the new search alias on such installations. It creates the alias to the old index, fills and validates a new candidate, then atomically switches; a failed candidate leaves the old index usable. Candidate/old index cleanup is an explicit operator decision.

## Acceptance evidence

| AC | Status | Cases and evidence |
| --- | --- | --- |
| AC01 | PASS | TC01: `test_versioned_interleaving_and_tombstone`, real ES 8.19.6, sends newer then older and equal revisions with conflicting active/price content; stored newer inactive/4,200 remains. |
| AC02 | PASS | TC02: same real-service test pauses before bulk, commits a new revision, releases old work and confirms the event is still pending before the next pass. |
| AC03 | PASS | TC03: `test_mixed_bulk_acknowledges_only_success_and_verified_conflict`, SQLite/fake per-item bulk: 201 and verified 409 acknowledged; 429 and 400 persisted pending. An oversized item is held as 413 without starving 100 later valid homes. |
| AC04 | PASS (local interleaving; parent review complete) | TC04: two actual PostgreSQL indexers, controlled barrier, inactive transition, later response first then earlier response; final ES document remains inactive and newer. Existing identity integration covers merge; source tombstone explicitly queued. No claim of production multi-indexer rollout. |
| AC05 | PASS | TC05: `test_profile_change_reindexes_public_only` uses real ES; profile rename advances ES version and updates name; phone, phone hash, draft and email/password canaries absent. SQLite test also checks the allowlisted serializer. |
| AC06 | PASS | TC06: real-service `test_rebuild_failure_retry_and_concurrent_writes` fails after half of a two-home candidate, confirms original alias, retries while committing a change, confirms gate drains it, deletes the replacement to simulate reset and rebuilds again. |
| AC07 | PASS on controlled container profile | TC07: parent test on clean `a30d1d5` converged 100 changed homes in 0.431287 seconds under disjoint CPU sets/quotas totalling four CPUs and memory limits totalling 8 GiB, including the containerized test driver. One test passed without skips. See [reference profile and limits](../performance/index-convergence.md). The earlier unrestricted measurement is not used for acceptance. |

## Verification

Working directory for all commands: the assigned T08 worktree. Python 3.12.9, Node 24.6.0, macOS 15.7.7 arm64; services are disposable local PostgreSQL 16 and Elasticsearch 8.19.6. No cloud, live portal, email or push actions were performed.

- `PYTHONPATH=backend .venv/bin/pytest backend/tests/test_indexing.py -q`: exit 0, 5 passed, 0 failed, 0 skipped, after oversize handling. Includes existing SQLite rows and a null favorite floor, missing `last_index_status`, upgrade repeated twice, retained rent and revision.
- `PYTHONPATH=backend .venv/bin/pytest backend/tests -q --junitxml=.local/verification/T08/offline.xml`: exit 0, 175 passed, 0 failed, 12 skipped, 4.414 s on 2026-11-11 20:27 UTC; service tests skipped deliberately in the offline environment. This run predates the added oversize test; the targeted run above covers that subsequent change.
- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t08-shipping'`: exit 0, 12 passed, 0 failed, 0 skipped; 2026-11-11 20:28:37–20:29:16 UTC; raw report `.local/verification/T01/t08-shipping/report.json`. This includes fresh and repeatable tracked-baseline PostgreSQL upgrade retaining an existing listing at 4,200 and queuing it at revision 1. Index namespaces and databases are run-owned. The real-service code tested contains the final oversize change; the subsequent only change was a test-fixture URL type correction.
- Earlier service runs: `t08-first` 9/0/0, `t08-final` 11/0/0, `t08-confirm` 11/0/0, `t08-release` 11/0/0 and `t08-complete` 12/0/0. They were repeated as additional cases and status persistence were added. Raw sanitized reports are under `.local/verification/T01/<run-id>/report.json`.
- The local 100-home workload inserts 100 synthetic homes, commits 100 rent changes in one transaction, immediately polls one indexer, explicitly refreshes ES on each poll, and checks 100 searchable IDs, prices and ES versions. Poll fallback interval is 0.2 s; normal worker loop sleeps 5 s. No warm-up; one sample per run. Recorded elapsed seconds: 0.259602, 0.287444, 0.321803, 0.306794 and 0.325006. Raw samples are `.local/verification/T01/<run-id>/t08-convergence.json`. This is a local observation, not the four-core/8-GiB acceptance measurement.
- Version semantics cross-checked against [Elastic's Elasticsearch 8.19 Index API](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/docs-index_.html) and the [Bulk API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk).

## Recovery and review

Back up SQL and the existing search index before upgrade. Apply registry migration 006; do not alter recorded baseline checksums. Build the replacement and switch only after validation, leaving the old physical index intact. For a failed candidate, correct the issue and rerun; the unchanged alias remains usable. After reset, rerun rebuild. Prefer a forward fix or tested restore; no automatic destructive downgrade is provided. Pending held records need operator correction as described above.

The integrator should review revision and cancellation lock ordering with T13, combine only additive models/registry/SQLite hooks for 006 and 008, merge T03's collection changes without overwriting either worker, and rerun integrated migrations and concurrency suites. PostgreSQL advisory gates require all participating indexers to use this code and the same database. SQLite file gating is not a multi-host guarantee. The deployment default remains one indexer. Profile-version correctness and alias tombstones depend on future public writers using `queue_listing` in the same transaction; downstream canonical-write changes need review.

## Blockers and next action

Parent concurrency/data review is complete. TC07 passed the explicit four-CPU/8-GiB container resource profile on 2026-11-11 at 22:38:55–22:39:21 UTC; the [benchmark report](../performance/index-convergence.md) defines the limits, images, workload and one-sample scope. T32 will retain current integrated functional regression evidence. No production multi-indexer rollout, availability claim, push or deployment has occurred.
