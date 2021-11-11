# T25 — Measure and optimize search, ingestion and storage at a representative local scale

**User instruction:** I want evidence that fetching, deduplication, search and price history remain fast as the catalog grows, with optimizations that preserve rental and notification correctness.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 8 hours |
| Proposed window | D7–D8 (2026-11-20–2026-11-23) |
| Worker slot | A |
| Dependencies | [T08](T08-versioned-search-index.md), [T11](T11-history-storage.md), [T12](T12-public-search-contract.md) |
| Required review | strong: query correctness and measurement |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | query-backend, ingest-backend, benchmark-harness |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The recorded load sample used only 66 canonical homes and is not a capacity result. The current ingest candidate path may load source rows per candidate; history and search are improved by earlier tasks. Measure the integrated implementation before changing it.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T25/<run-id>/`; commit sanitized reports only.

## Read first

- `scripts/load_check.py`
- `backend/realtoruch/seed.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/query.py`
- `backend/realtoruch/api.py`
- `backend/realtoruch/search.py`
- `backend/realtoruch/indexing.py (from T08)`
- `docs/performance/history-baseline.md (from T11)`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `scripts/load_check.py`
- `scripts/seed_benchmark.py (extend T11 seed; do not create a competing generator)`
- `backend/realtoruch/ingest.py (measured query optimizations only)`
- `backend/realtoruch/query.py (measured query optimizations only)`
- `backend/tests/test_query_budgets.py (new)`
- `docs/performance/catalog-load.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Create a deterministic synthetic dataset of at least 10,000 canonical homes, 100,000 historical observations and 2,000 saved searches, with duplicate source ads, relists, inactive homes, owner/agency/unknown classifications and geographic boundaries. Seed only a disposable namespaced database/index; never grow or rewrite the user's local live catalog.

2. Record hardware, container limits, OS/runtime versions, seed, data counts, commit, warm-up and request mix. Target a local environment with at least four CPU cores and 8 GiB available RAM; if different, label it and report target gaps rather than extrapolating production throughput.

3. Run five minutes at 20 concurrent clients after warm-up for SQL search, Elasticsearch search, summary/history and a small independent ingestion batch. Set performance targets: warm SQL search p95 <=300 ms, ES-backed REST search p95 <=250 ms, history p95 <=750 ms and API process RSS <500 MiB. Require zero unexpected 5xx and correct result/notification counts.

4. Measure production-like rate limits separately: expected 429 is a quota outcome, not a hidden latency success. For the capacity run use an explicit isolated test limit and record it. Bound requests/time and retain raw aggregate measurements without storing contact data.

5. Use PostgreSQL EXPLAIN (ANALYZE, BUFFERS) on the disposable dataset and query counters to identify repeated source/candidate loads, full scans and oversized IN lists. Batch source/candidate retrieval or use appropriate joins/indexes only where evidence shows a benefit. Preserve transactional locking and revision/outbox semantics.

6. Compare before/after correctness and performance using the identical seed and query mix, with warm and cold samples labelled separately. Report cost/storage growth in measured rows/bytes per run, not unverified cloud prices. Hand any new schema/index change to the migration coordinator with a reserved next migration; never modify an applied file.

## Acceptance criteria

- **T25-AC01:** The benchmark seeds and cleans up an isolated representative dataset reproducibly.

- **T25-AC02:** Performance report records the full environment, workload and raw sample counts.

- **T25-AC03:** Declared latency/memory/error targets are met on the documented profile; unmet targets remain failed acceptance criteria rather than being waived by a report.

- **T25-AC04:** Optimizations remove measured query amplification without changing canonical/filter/history/alert results.

- **T25-AC05:** Quota tests and capacity tests are separate and production limits stay enabled.

- **T25-AC06:** Storage growth and before/after query plans provide an inspectable basis for scaling decisions.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T25-TC01 — covers T25-AC01

**Given:** Two fresh run IDs and the same seed.

**When:** Generate catalogs independently.

**Then:** Counts and expected canonical/alert outcomes agree; no shared live database is touched.

### T25-TC02 — covers T25-AC02, T25-AC03

**Given:** Recorded dataset and hardware after warm-up.

**When:** Run the five-minute 20-client mix.

**Then:** Report includes p50/p95/p99, RSS, status counts, throughput and pass/fail for every target.

### T25-TC03 — covers T25-AC04

**Given:** Candidate sets of 1, 10 and 100 source ads.

**When:** Count queries and compare optimized outputs.

**Then:** Query growth is bounded by documented batches; canonical decisions/history/alerts match the baseline.

### T25-TC04 — covers T25-AC04

**Given:** Concurrent ingest, lower-price relist and ES indexing.

**When:** Run under load with barriers for conflicting operations.

**Then:** No missing revision, duplicate logical alert or stale public document persists after drain.

### T25-TC05 — covers T25-AC05

**Given:** Unmodified production quota and separate explicit test quota.

**When:** Run quota and capacity profiles.

**Then:** Expected 429 is tested; capacity measurements do not conceal throttled responses as successes.

### T25-TC06 — covers T25-AC01, T25-AC06

**Given:** Benchmark interrupted and subsequently resumed/cleaned.

**When:** Inspect namespace ownership, plans and storage report.

**Then:** Only its resources are cleaned; reproducible row/byte deltas and plans remain in sanitized evidence.


## Verification commands and checks

- `python3 scripts/load_check.py --help, then the new documented isolated profile`
- Run focused query-budget and lifecycle tests
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Deterministic scalable benchmark and bounded query improvements
- Before/after latency, memory, query-plan and storage report
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not claim production SLA/capacity from a laptop benchmark.
- Do not add Redis, another database, another search engine or speculative caches.
