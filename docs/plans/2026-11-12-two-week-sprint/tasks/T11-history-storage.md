# T11 — Bound historical-rent queries and preserve their methodology

**User instruction:** I want you to make rent-history and market-summary queries scale beyond the small sample catalog without changing what their numbers mean.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 8 hours |
| Proposed window | D5–D6 (2026-11-18–2026-11-19) |
| Worker slot | C |
| Dependencies | [T10](T10-identity-correctness.md) |
| Required review | data/query review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | query-model |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

query.market_history currently loads matching observation/listing pairs into Python and groups them there; api.summary loads all active homes. Preserve advertised base-rent semantics and one canonical vote per observed month.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T11/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/query.py`
- `backend/realtoruch/api.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/worker.py`
- `backend/tests/test_ingestion.py`
- `docs/architecture.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/query.py`
- `backend/realtoruch/api.py (history/summary only)`
- `backend/realtoruch/models.py (indexes if justified)`
- `infra/sql/007_history_indexes.sql (new, only if justified)`
- `infra/sql/migrations.json`
- `backend/tests/test_market_history.py (new)`
- `scripts/seed_benchmark.py (new/shared with T25)`
- `docs/performance/history-baseline.md (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Implement database-side pruning/window aggregation for PostgreSQL and a correct bounded SQLite equivalent. Select the latest observation per source/month, active sources only, then one latest active source price per canonical home/month before computing medians.

2. Preserve the existing contract unless adding explicitly documented fields. Use exact integer PLN rent values, current documented area semantics, deterministic ties and explicit sample_size/is_demo. No interpolation into unobserved months.

3. Replace months*31 ambiguity with a documented calendar-month UTC range; add boundary tests. Do not silently reinterpret historic amounts as transaction/lease prices or all-inclusive costs.

4. Use indexes supported by EXPLAIN evidence. A summary request must not materialize full Listing ORM objects for every active home. Avoid an unbounded IN list of all matching IDs.

5. Benchmark deterministic synthetic data with at least 10,000 homes and 100,000 observations, isolated from real catalogs. Record latency, query counts and Python peak memory on a named local profile.

6. Ensure manual merges/splits update results correctly from source observations, and retain stale/removed history according to methodology. Keep any materialized cache optional and invalidatable; do not add one without measured need.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

8. Define months=N as the current UTC calendar month plus N-1 preceding calendar months, using an inclusive first-of-month lower boundary and current observation time upper boundary. The history reference must apply the latest-per-source status before selecting active sources, so a removal does not erase another active source's vote. Input rents stay integer PLN, but an even-sample median may be fractional; do not truncate it.

## Acceptance criteria

- **T11-AC01:** Small-fixture results match a simple independent reference calculation exactly.

- **T11-AC02:** Month boundaries, duplicate portals, removals and sparse months follow documented methodology.

- **T11-AC03:** PostgreSQL and SQLite return equivalent values for the same fixtures.

- **T11-AC04:** A 100,000-observation request does not load the full observation table into Python; peak API-process growth stays under 150 MiB for the benchmark.

- **T11-AC05:** Warm history response p95 is <=750 ms and summary p95 <=300 ms on the declared local benchmark profile; exceeding either target fails this criterion.

- **T11-AC06:** Identity corrections and price/status changes produce correct subsequent aggregates without losing raw history.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T11-TC01 — covers T11-AC01, T11-AC02

**Given:** A hand-calculated three-home/two-portal monthly fixture.

**When:** Query history.

**Then:** Expected median, per-m² median, sample_size and absent-month behavior match exactly.

### T11-TC02 — covers T11-AC02

**Given:** Observations at UTC month/year boundaries and leap day.

**When:** Query one/three/twelve months.

**Then:** Calendar inclusion is deterministic and documented.

### T11-TC03 — covers T11-AC02, T11-AC03

**Given:** One source removed while another remains active.

**When:** Run the same fixture on SQLite and PostgreSQL.

**Then:** Canonical home contributes once with the intended latest active price.

### T11-TC04 — covers T11-AC04, T11-AC05

**Given:** 10,000 homes and 100,000 observations in isolated databases.

**When:** Run warm/cold timed queries and inspect EXPLAIN.

**Then:** Bounded result materialization; latency/memory report is reproducible.

### T11-TC05 — covers T11-AC06

**Given:** Two historical duplicates merged then a source split.

**When:** Query before/after corrections.

**Then:** Counts and medians reflect canonical identity; observation rows remain present.

### T11-TC06 — covers T11-AC01, T11-AC03

**Given:** Empty city and small even/odd sample sizes.

**When:** Compare engines to reference.

**Then:** Null/empty output and median arithmetic agree.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_market_history.py backend/tests/test_ingestion.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Bounded query implementation and measured index decisions
- Reference-calculation fixtures and benchmark seed utility
- Methodology/boundary documentation
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No representative national rental index or invented historic prices.
- Do not add BigQuery, Redis or a new production service.
