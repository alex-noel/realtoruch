# T11 handoff

## Identity and outcome

- Task: T11; status: VERIFIED locally, subject to integrator data/query review.
- Base: `87cfd3438b7dec064f2a7759fe8f585047d88ff9`.
- Implementation commit: `3bdf3379e91e634210f0a0ce8bd52e9425d37075`, created with `python3 scripts/commit.py`. This handoff is committed separately using the same helper; its containing commit is available as `git log -1 -- docs/verification/T11-handoff.md`.
- Actual work/test date: 2026-11-11, Europe/Warsaw (UTC+01:00); Git dates are intentionally five years earlier.
- Outcome: history and summary calculate bounded aggregates in SQL, preserving one observed active-source vote per canonical home and fractional medians.
- Scope changes: none; API response fields unchanged. No shared migration or new index was justified by this workload.

## Changed files and contracts

- `backend/realtoruch/query.py`: calendar-month range, two levels of SQL window ranking, median selection/aggregation and SQL summary. Timestamp ties are resolved by descending source then observation ID. Returns at most one row per observed month to Python; summary returns aggregates and distinct location strings.
- `backend/realtoruch/api.py`: summary delegates to SQL helper; route and response shape stay unchanged.
- `backend/tests/test_market_history.py`: independent Python reference, leap/year boundaries, sparse months, source removal, empty/even/odd results, tie and actual merge/split checks on SQLite and PostgreSQL. PostgreSQL fixture refuses a nonempty database.
- `scripts/seed_benchmark.py`: deterministic isolated 10,000-home/100,000-observation fixture and local API measurements. Seeding refuses a nonempty database; API lifespan is isolated in in-memory SQLite.
- `docs/performance/history-baseline.md`: methodology, measurements, index decision and reproduction.
- Reserved rentals migration 007 remains unused. No schema/index changes or cache; existing migrations, checksums and SQLite upgrade callbacks remain byte-for-byte intact. Consequently no new schema-specific upgrade is necessary. Existing registry/service migration regressions were run.

## Acceptance evidence

| AC | Result | Test cases | Evidence |
| --- | --- | --- | --- |
| T11-AC01 | PASS | TC01, TC06 | Independent reference and explicit hand values, SQLite and PostgreSQL, 19-test targeted run. |
| T11-AC02 | PASS | TC01–03 | UTC leap/year/start/end boundaries, sparse months, latest removal with another source active and deterministic tie, both engines. |
| T11-AC03 | PASS | TC03, TC06 | Identical independent reference and explicit values on both engines; empty and fractional even medians. |
| T11-AC04 | PASS | TC04 | 100,000-observation local API benchmark, one SQL history query, monthly rows only; fresh-process peak RSS growth 4.17 MiB PostgreSQL and 56.8 MiB SQLite, under 150 MiB. |
| T11-AC05 | PASS | TC04 | Local warm p95 history 364.0/453.7 ms and summary 30.3/21.2 ms for PostgreSQL/SQLite respectively. Profile and caveats in performance report. |
| T11-AC06 | PASS | TC05 | Actual identity merge/split on both engines; sample changes 2→1→2, all eight raw observations retained. |

All TC01–TC06 passed locally. TC04's timings are TestClient local process measurements, not a remote/deployed service claim. Raw timing samples and actual PostgreSQL EXPLAIN are under ignored `.local/verification/T11/20261111-local/`; the committed performance report gives their aggregate values. EXPLAIN read 100,000 observations, chose sequential scans and spilled a 7,272 kB sort; no new index decision is generalized to selective workloads.

## Verification

All commands ran in the assigned worktree on 2026-11-11. Runtime: macOS 15.7.7 arm64, Apple M4 Pro, 64 GiB, Python 3.12.9, SQLite 3.50.2, Node v24.6.0, disposable Docker PostgreSQL 16.15 and Elasticsearch 8.19.6. `T11_TEST_POSTGRES_URL` below points only to the disposable T11 PostgreSQL container.

- `T11_TEST_POSTGRES_URL=postgresql+psycopg://postgres:t11@127.0.0.1:64989/t11 PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_market_history.py backend/tests/test_ingestion.py -q` — exit 0, 19 passed, 0 failed, 0 skipped. The initial fixture run had 15 passed/2 failed because the merge fixture mixed demo and non-demo homes; the fixture was corrected and rerun, then tie and empty-database guards added and final run passed.
- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t11-regression'` — exit 0; 90 passed, 0 failed, 0 skipped, actual PostgreSQL and Elasticsearch. Report: `.local/verification/T01/t11-regression/report.json`. Temporary `.venv` symlink removed after the run. This ran before the final test-only tie and script safety additions; production query code was unchanged.
- PostgreSQL benchmark: `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/seed_benchmark.py --url postgresql+psycopg://postgres:t11@127.0.0.1:64989/t11 > /tmp/t11-bench.json`, followed by `DATABASE_URL=sqlite:// AUTH_DATABASE_URL=sqlite:// PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/seed_benchmark.py --measure-only --url postgresql+psycopg://postgres:t11@127.0.0.1:64989/t11 > /tmp/t11-api-bench.json` — each exit 0. First direct-function measurement preceded the TestClient measurement; the latter supplies reported numbers. Final script additionally forces its own API lifespan databases to memory.
- SQLite benchmark: `DATABASE_URL=sqlite:// AUTH_DATABASE_URL=sqlite:// PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/seed_benchmark.py --url sqlite:////tmp/t11-benchmark.db --samples 2 > /tmp/t11-sqlite-seed.json && DATABASE_URL=sqlite:// AUTH_DATABASE_URL=sqlite:// PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/seed_benchmark.py --measure-only --url sqlite:////tmp/t11-benchmark.db > /tmp/t11-sqlite-bench.json` — exit 0. The separate measurement has 30 samples and three warmups.
- PostgreSQL query plan captured using SQLAlchemy `before_cursor_execute` on the actual history statement, then `EXPLAIN (ANALYZE, BUFFERS)` with its bound parameters, exit 0. Raw plan in the local artifact directory. See performance report for exact percentile calculation, seed, sample counts, concurrency and memory limitations.
- `git diff --cached --check` — exit 0 before implementation commit.

## Reproduction and review

Run the targeted test command against an empty disposable PostgreSQL database; run the seed/measurement instructions in the performance report against another empty database. Negative coverage includes empty city, month omission, future observation exclusion, inactive latest status and ties. The benchmark records a process high-water RSS difference, not a separate per-request allocator profile, and TestClient excludes network overhead. Summary's four statements do not promise snapshot consistency across concurrent writes. No migration rollback is required; revert the implementation commit using a reviewed patch and the required commit helper if necessary. The integrator should review query semantics and coordinate the small history/summary changes in `api.py` with T12/T26; no identity lock ordering or writes were changed.

## Blockers and next action

No external blocker. Integrator to review SQL/methodology and integrate the implementation and handoff commits, retaining the raw local artifacts as needed. No cloud resources, real emails, live provider requests, pushes or deployments were used.

## Parent integration acceptance

The parent reviewed the SQL ranking, even-sample medians, UTC range, unchanged response fields and benchmark limitations. The PostgreSQL fixtures now reuse T01's `TEST_POSTGRES_URL` and per-test migrated private schema instead of the task-specific empty-database fixture. `make verify-services ARGS='--run-id integrated-t11-review'` independently passed **101 tests, zero skips**, including all six history cases on SQLite/PostgreSQL and combined T04/T10/T13 cases. The new history module is registered in the service profile, so CI cannot silently omit its PostgreSQL checks. Historical worker commands above retain their original environment names; current standalone reproduction uses `TEST_POSTGRES_URL` pointing to a disposable service. No schema change or 007 migration was introduced.
