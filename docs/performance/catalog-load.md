# T25 local catalog benchmark

This is an isolated local experiment, not a production capacity claim. The source
fixture is synthetic and contains no real contact information. The fixed fixture
anchor is 2026-11-01 12:00 UTC; it creates 10,000 homes, 12,000 source ads,
100,000 observations and 2,000 saved searches, with inactive homes, crossposts,
reposts, private/agency/unknown declarations, price and area boundaries, and
points on and outside the Kraków acceptance rectangle. The second source of a
crosspost does not receive independent historical observations in this fixture.

The seed only accepts an empty loopback PostgreSQL database whose name starts
`t25_` and checks that its port belongs to the explicitly named Docker container
with the expected `realtoruch.t25.owner` label. It applies the real rental
migration registry before inserting data. Create the database in a dedicated
run-owned container first and verify the owner label before cleanup. The seed
is not resumable after an interrupted insertion; destroy and recreate that owned
database before retrying. The load client is loopback-only and read-only.
The initial two catalogs described below were created in the owned container
before the label/port guard was added; a later wrong-owner invocation was
rejected before connecting, and a nonempty owned database was also refused.

The capacity profile explicitly sets the local API and search rate limits to
1,000,000 requests per minute. The default local limiter was separately tested
at 120/minute: 120 successes followed by a 429. Production uses Cloud Armor
rules in `infra/terraform/cdn.tf` (public 120/minute, auth 20/minute per IP);
live enforcement was not tested. The application intentionally disables its
in-process limiter in production. A capacity run with a 429 is a failure, not a
successful latency sample. Percentiles use nearest-rank and HTTP 200 samples;
status counts retain all failures.

The candidate path loads source evidence in batches of at most 100 candidate
IDs, preserves candidate iteration order, and makes the same matching decision
as the unbatched path. The global identity lock and transaction, revisions,
outbox, history and alert rules are unchanged. A first-candidate match can load
more source evidence than before; the saved queries are most useful when many
candidates are rejected. No migration or new index was added.

## Run 20261111-t25: preliminary paired windows

Actual test date 2026-11-11/12, Europe/Warsaw; base `3bec9db`. Host: Apple
M4 Pro, 14 CPU cores, 64 GiB, macOS 15.7.7, Python 3.12.9; Docker 29.8.0 had
6 CPUs and 15,955,206,144 bytes available. PostgreSQL 16 Alpine was an amd64
image under emulation; Elasticsearch 8.19.6 was native arm64 with a 1 GiB heap.
API, search and client processes ran on the host, sharing the machine with the
independent T07 soak. This is not T08's exact four-core/eight-GiB gate.

Two independently generated catalogs had equal row counts and equal ordered
fixture hashes for homes (`57eff9f12a317b1886f4c399fee0da00`) and observations
(`1a4cafd43cfa5144209fa44aa65f6bc1`). A separate baseline database was cloned
from the first. Elasticsearch indexed all 10,000 initial documents with zero
bulk item failures. After ten seconds of warmup, each window used 20 clients
and an equal six-way mix of ordinary SQL search, polygon SQL search, ordinary
ES-backed REST search, polygon ES-backed REST search, market summary, and
market history. Each window also included the same two synthetic ingests and a
real PostgreSQL/ES barrier race. Request caps were 1,000,000; the clients stopped
dispatching after 300 seconds and waited for in-flight requests to finish.

| Window and metric | SQL | SQL polygon | ES REST | ES REST polygon | Summary | History |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Before p50 / p95 / p99 ms | 599.6 / 1059.4 / 1225.2 | 406.5 / 838.5 / 1083.0 | 80.6 / 102.3 / 115.4 | 82.4 / 103.2 / 122.6 | 5503.3 / 6547.4 / 6781.1 | 1609.0 / 2165.5 / 2351.2 |
| After candidate batching p50 / p95 / p99 ms | 114.5 / 201.5 / 245.0 | 103.0 / 161.0 / 203.4 | 61.6 / 79.8 / 95.5 | 61.4 / 79.6 / 101.1 | 156.6 / 229.3 / 268.5 | 1085.7 / 1805.1 / 2070.6 |

Before: 302.95 seconds including drain, 4,405 responses, all 200, 14.54/s;
735 ordinary SQL samples and 734 for each other operation. After: 300.61 seconds,
21,976 responses, all 200, 73.11/s; 3,663 samples for each search variant and
3,662 each for summary/history. Peak sampled API RSS was 110.5/121.5 MiB before
and 117.4/128.8 MiB after. The configured ES REST path and sampled RSS met their
numeric targets in both windows; however, the initial harness did not count
degraded responses, so ES-backed performance is not verified for every sample.
A spot check showed `engine=elasticsearch` and `degraded=false`; the improved
harness records both for every search response. SQL passed only in the second;
history failed in both. Summary
also exceeded the shared 300 ms target in the first window.

**The read throughput comparison is confounded by planner statistics.** The
cloned baseline database lacked fresh PostgreSQL statistics; its summary
source-count plan performed 9,002 repeated bitmap scans and took 1,721.6 ms
with 135,366 shared buffer hits. The independently seeded after database used
a hash join taking 6.6 ms and 1,279 shared hits. This difference cannot be
attributed to the code change. Both databases were subsequently ANALYZEd; a
new controlled pair is needed. Single `EXPLAIN (ANALYZE, BUFFERS)` executions
are not loaded request percentiles: the unoptimized history SQL took 413–424
ms, included several window sorts and spilled 8,928 kB to disk, while loaded
HTTP p95 was 1.8–2.2 seconds. The difference includes contention and request,
connection and application overhead; it does not isolate their individual
contributions.

The two no-match ingests examined roughly 2,500 candidates apiece. Baseline
used 2,517/2,518 statements in 6.94/7.28 seconds; batching used 42/43 statements
in 0.54/0.23 seconds. These are two in-load observations, not a throughput
estimate. Tests separately compare original and batched decisions at 1, 10,
100 and 101 candidates, including early and last matches and no match. A
barrier test during each window paused an old ES bulk, raced two identical
lower-price relists, drained work, and checked one logical price-drop alert and
the final SQL revision against the ES document.

A PostgreSQL-only `percentile_cont` experiment retained the latest-source and
latest-home selection and the SQLite fallback. A single warm history plan fell
from 424.1 to 287.9 ms and removed three median window layers, but retained the
8,928 kB spill. Nineteen focused SQLite/PostgreSQL history and candidate/race
tests passed with no skips. This is preliminary until repeated samples and an
identical analyzed load pair validate it.

## Reproduction and safety

Use dedicated disposable PostgreSQL and Elasticsearch containers, each with a
unique `realtoruch.t25.owner` label, loopback-only published ports and an
unpredictable owner value. Elasticsearch must be empty because this isolated
experiment creates the `rentals-search` alias. Set the variables below to those
owned resources; `T25_DB` must point to a fresh database named `t25_*`. Do not
use a developer or live catalog. The scripts verify container labels and port
mappings before mutating either service.

```sh
PYTHONPATH=backend .venv/bin/python scripts/seed_benchmark.py \
  --t25-seed-only --url "$T25_DB" --t25-container "$T25_PG_CONTAINER" --t25-owner "$T25_OWNER"
PYTHONPATH=backend .venv/bin/python scripts/t25_operations.py index \
  --database "$T25_DB" --elasticsearch "$T25_ES" --pg-container "$T25_PG_CONTAINER" \
  --es-container "$T25_ES_CONTAINER" --owner "$T25_OWNER"
```

For a matched comparison, create two separate copies from the same pristine
seed, run `ANALYZE` on both, use the reviewed base for one API and the candidate
code for the other, and keep all other settings and workload timing equal. Run
separate SQL-backed and ES-backed API processes against each copy and a private
search service against the owned ES. Set `REQUEST_LIMIT_PER_MINUTE=1000000`
for those isolated API and search processes only. Keep the real production
settings unchanged. Then issue, for each window:

```sh
.venv/bin/python scripts/load_check.py --url "$T25_SQL_API" --search-url "$T25_ES_API" \
  --sql-engine postgresql --profile capacity --capacity-limit 1000000 \
  --warmup 10 --duration 300 --requests 1000000 --concurrency 20 \
  --api-pid "$T25_SQL_PID" --api-pid "$T25_ES_PID" --output "$T25_REPORT"
```

Start `scripts/t25_operations.py ingest` with the same service arguments as
`index` 15 seconds after starting the client, and run the targeted real-service
`test_relist_index_and_replay_converge` at 45 seconds. After the windows,
`drain` processes alerts and indexing, checks 4,000 synthetic notifications,
zero pending work and matching revisions; when switching between the two copied
catalogs against the same owned ES cluster, pass `--remove-indexed` for the
first drain to remove only its two synthetic batch documents. `plans` captures
the search, summary and history `EXPLAIN (ANALYZE, BUFFERS)` output. The
service helper refuses an owner or port mismatch. Stop only processes that the
run started; before deleting a container, inspect and compare its owner label.
Never issue a wildcard Docker or Elasticsearch cleanup.

Run artifacts, including commands, per-request latency samples, status counts,
plans, and synthetic helper outputs, are under the ignored
`.local/verification/T25/20261111-t25/` directory. A short six-request smoke
validated the enhanced client's engine and degraded counters; these counters
were not available for the first, preliminary pair above. The owned resources
were started manually for this run, not by an automatic orchestration command.

## Corrected analyzed comparison

Both pristine copies were analyzed before the windows. The baseline ran the
reviewed dependency source; the candidate used batched ingest and PostgreSQL
ordered-set medians. The same workload, seed, isolated quota, warmup, two ingests
and timed race were used. A follow-up `DISTINCT ON` experiment discussed below
was not part of this pair.

| Window and metric | SQL | SQL polygon | ES REST | ES REST polygon | Summary | History |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline p50 / p95 / p99 ms | 115.3 / 205.7 / 257.4 | 102.3 / 166.0 / 196.0 | 61.1 / 78.2 / 90.7 | 61.1 / 78.6 / 93.3 | 158.1 / 235.1 / 275.9 | 1093.7 / 1797.5 / 2099.6 |
| Candidate p50 / p95 / p99 ms | 84.6 / 137.4 / 186.1 | 78.4 / 126.8 / 167.8 | 62.6 / 90.4 / 155.0 | 62.5 / 92.2 / 162.0 | 136.0 / 203.1 / 248.2 | 726.5 / 1243.6 / 1461.7 |

Baseline: 300.60 seconds, 21,830 requests, 72.62/s, all 200; 3,639
ordinary SQL and ES samples, 3,638 for each other operation. Candidate:
300.35 seconds, 29,843 requests, 99.36/s, all 200; 4,974 per search and
summary, 4,973 history. Every SQL response declared PostgreSQL, every ES
response declared Elasticsearch, and every discovery response declared
`degraded=false`. Peak sampled API RSS was below 127 MiB. Both client
commands exited 1 because history p95 exceeded 750 ms; all other measured
latency, RSS and error targets passed. The 20-client response time combines
server work, scheduling, database contention, connection pooling, and network;
the measurement does not apportion the difference among them.

The baseline ingests used 2,517/2,518 SQL statements in 5.92/2.41 seconds;
the candidate used 42/43 in 0.70/0.27 seconds, with identical no-match
canonical decisions. After the windows, each catalog processed two events into
4,000 synthetic notifications and indexed two documents, with zero pending
alert events or outbox rows and matching ES document revisions. The controlled
race also passed against both revisions of the code. No messages were sent.

A further PostgreSQL experiment replaced the two latest-row windows with
`DISTINCT ON`, keeping latest-source selection before active filtering and the
same canonical timestamp/source/observation tie order. SQLite retains its
original window implementation. One warm `EXPLAIN ANALYZE` dropped from
287.9 to 261.5 ms; this was not a 20-client measurement. PostgreSQL and SQLite
reference, timestamp-tie, merge/split and race tests passed, with no relaxed
comparisons. A native arm64 PostgreSQL 16 Bookworm diagnostic used the same
fixture and code against a separate owned container: ten sequential warm
history samples had medians of 338.8 ms for the baseline and 207.7 ms for the
new query, with exactly equal results. The corresponding optimized emulated
median was 206.6 ms on an independently seeded copy. These short sequential
samples are not capacity evidence; native and emulated container images also
use different distributions. A further controlled load run is required before
claiming any target passes with the follow-up change.

A short native-arm64 mixed-load diagnostic of the further `DISTINCT ON`
experiment ran 20 clients for 30 seconds after a ten-second warmup. It returned
3,727 HTTP 200 responses with history p50/p95/p99 531.0/1,119.5/1,345.1 ms;
SQL p95 was 100.4–106.5 ms and ES p95 88.3–89.2 ms. This short diagnostic
also missed the 750 ms history target and does not satisfy the required
five-minute acceptance duration. The native image was the separate official
PostgreSQL 16 Bookworm arm64 image, digest
`sha256:5264710be20f409750ac6dc4e5706dcef929c87e241605463f0f9aefa932a8d9`;
the shared Docker platform settings and existing Alpine tag were not changed.

A subsequent experiment uses PostgreSQL `date_trunc('month', observed_at)`
as the month key and formats only returned aggregate months; SQLite keeps its
existing path. On the native fixture, a single warm plan took 228.4 ms and
still spilled 8,928 kB. The same 23 focused tests passed with zero failures or
skips, including exact reference results and timestamp ties. This is not yet
an accepted loaded-latency measurement.

The current follow-up uses bytewise `C` collation only for the PostgreSQL
source and home grouping/sort keys. The source-ID and observation-ID
**tie-break expressions retain the database's original collation**. Native
`en_US.utf8` grouped the synthetic fixture in a single plan in 107.2 ms,
compared with 228.4 ms for the previous timestamp-key plan, though the sort
still spilled. The measured database uses a deterministic collation and
generated identifiers; exact reference and mixed-case tie tests passed.
PostgreSQL 16 [documents](https://www.postgresql.org/docs/16/sql-createdatabase.html)
that database-default collations are deterministic, and its
[collation documentation](https://www.postgresql.org/docs/16/collation.html)
states that deterministic equality requires identical bytes. The registered
schema uses the default collation for these IDs. An independently modified
schema with nondeterministic per-column ID collations is not covered by this
argument; IDs are not constrained to UUID syntax. A 30-second 20-client native diagnostic
returned 6,234 HTTP 200s with history p50/p95/p99 240.4/481.6/568.7 ms;
this is not a five-minute acceptance measurement.

## Final native PostgreSQL comparison

The final pair used separate fresh, analyzed clones of the identical synthetic
seed and PostgreSQL 16.15 Bookworm **arm64** in its own labelled container. The
host and Docker limits, API/search process placement, warmup, six-way workload,
client count, explicit test quota, timed ingestion and controlled race were the
same as above. These native results do not erase the prior emulated-profile
history failure or establish a production SLA.

| Window and metric | SQL | SQL polygon | ES REST | ES REST polygon | Summary | History |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline p50 / p95 / p99 ms | 98.9 / 181.3 / 222.5 | 88.1 / 150.0 / 186.1 | 63.8 / 82.3 / 93.8 | 62.8 / 81.7 / 94.7 | 135.7 / 211.0 / 251.2 | 960.6 / 1837.4 / 2159.8 |
| Final p50 / p95 / p99 ms | 32.1 / 68.4 / 92.3 | 31.5 / 66.7 / 92.2 | 71.6 / 115.6 / 152.1 | 73.3 / 118.9 / 154.0 | 74.6 / 139.4 / 191.8 | 225.3 / 452.6 / 559.9 |

Baseline elapsed 300.60 seconds including in-flight drain, 23,964 responses,
3,994 per operation, 79.72/s, all HTTP 200; its history target failed. Final
elapsed 300.13 seconds, 64,154 responses, 213.75/s, all HTTP 200; there were
10,693 ordinary SQL and ES samples and 10,692 of each other operation. All
search responses declared the intended PostgreSQL or Elasticsearch engine and
`degraded=false`. Peak sampled API RSS was 118.3/128.2 MiB baseline and
118.4/136.6 MiB final. Final SQL, ES REST, history, RSS and no-unexpected-error
targets all passed on this profile. The two no-match ingests were 2,517/2,518
statements and 3.42/3.07 seconds baseline, 42/43 statements and 0.26/0.24
seconds final. Each real-service barrier race passed. After drain, both catalogs
had 4,000 synthetic notifications, zero pending alerts/outbox and consistent
revisioned documents.

Before/after history and summary results were identical in ten-sample warm
single-client checks. Five SQL filter/source sets were identical, including
strict price, area, private, polygon, agency and known-zero-commission cases;
source-row counts were 10,002 / 1,001 / 1,001 / 3,333 / 6,000 respectively.
A process-cold first HTTP request after restarting each API, with database and
OS caches already warm, measured baseline listing/summary/history at
37.39/29.91/351.31 ms and final at 31.71/30.34/104.22 ms. These are individual
first requests, not storage-cold or percentile measurements. Ten warm sequential
history calls had medians of 339.4 ms baseline and 88.4 ms final. A separate
all-history saturation diagnostic (60 direct calls, 20 threads, default pool
size 5 plus 10 overflow) measured p95 connection acquisition 908 ms,
post-acquisition history call 332 ms, and total 1,058 ms. This diagnostic has a
different request mix from the passing capacity profile; the post-acquisition
measurement includes application overhead, not just server execution.

The empty migrated native database used 8,879,127 bytes; the pristine 10,000
home fixture used 45,734,935 bytes, a measured increase of 36,855,808 bytes.
After two ingests and 4,000 notifications the before/after databases used
49,085,463 and 49,077,271 bytes respectively. On the pristine fixture,
PostgreSQL total relation sizes (data and indexes) were 3,579,904 bytes for
10,000 listings, 10,125,312 bytes for 12,000 sources, 20,799,488 bytes for
100,000 observations, and 540,672 bytes for 2,000 searches. The ES primary
store measured 1,167,677 bytes with 10,002 documents after the final drain.
These are measured local sizes including allocation effects, not cloud prices.

An interruption drill stopped a seed after the migration registry committed;
a direct retry refused the nonempty database. After validating the owner label,
the run dropped and recreated only its own named database, reseeded all expected
rows, and dropped it again. Wrong-owner and nonempty-database seed attempts were
also refused. No cloud, provider, live database, or real email was used.

The final native post-drain plans show history execution at 367.9 ms baseline
and 103.9 ms final in individual warm `EXPLAIN (ANALYZE, BUFFERS)` executions.
The baseline external sort used 8,928 kB; the final external sort used 10,192
kB. Both plans are retained in the ignored run directory; these timings are
not a replacement for the loaded percentiles above. The diagnostic 16 MiB
`work_mem` setting was not adopted.

## Handoff

- Task T25; status **IMPLEMENTED_LOCAL**, pending integrator review and combined
  service regression. Base revision `3bec9db`. Actual local work and tests were
  2026-11-11–12 Europe/Warsaw. No production or public deployment was made.
- `ingest.py` batches candidate evidence without changing transaction/lock
  ordering. `query.py` adds the PostgreSQL history plan described above; SQLite
  remains on its original path. `seed_benchmark.py`, `t25_operations.py` and
  `load_check.py` provide owned synthetic data, operations and measurements.
  `test_query_budgets.py` adds parity, destination guard, degraded-result and
  real-service race coverage. `verify.py` adds that module to the services
  profile, an additive runner change requested by the integrator. No migration,
  public API/DTO change, or applied migration alteration was made. Rollback is
  a code revert; existing data needs no rollback.
- Focused verification: with Python 3.12.9, disposable PostgreSQL 16.15 arm64
  and Elasticsearch 8.19.6, `pytest -o addopts='' -q` over
  `test_query_budgets.py`, `test_market_history.py`, `test_ingestion.py`,
  `test_lifecycle.py`, and `test_rental_journey.py` exited 0: **57 passed,
  0 failed, 0 skipped**, with one existing Starlette deprecation warning.
  The integrator requested that the complete combined `make verify-services`
  run be performed on the integrated branch; it has not been rerun here.
- All three containers created for this run were removed only after checking
  their `realtoruch.t25.owner` labels; run-owned API/search processes were
  stopped. The interrupted-seed database was individually recreated and
  removed after the same owner check. No user database or T07 soak was touched.

| Acceptance | Status on documented local profile | Evidence / test case |
| --- | --- | --- |
| AC01 isolated, reproducible fixture | PASS | TC01 independent catalogs, equal counts/hashes; TC06 interruption and owned cleanup |
| AC02 environment and samples | PASS | TC02 final native windows, per-operation raw samples and status counts in ignored run artifacts |
| AC03 targets | PASS on final native profile; FAIL on measured emulated profile | TC02 full windows and target results above; no extrapolation between profiles |
| AC04 correctness and amplification | PASS locally; independent review required | TC03 1/10/100/101 candidate query counters; TC04 barrier race, drains, filter/history parity |
| AC05 separate quota and capacity | PASS locally | TC05 120 successes then 429 at local default; isolated million/minute capacity profile; live Cloud Armor not tested |
| AC06 storage and plans | PASS locally | TC06 owned interruption/recreate/cleanup, physical size comparison and before/after PostgreSQL plans |

Raw commands and artifacts are in `.local/verification/T25/20261111-t25/` in
this worktree; they contain only synthetic run data. The named service test
fixture has not been claimed as hosted CI evidence. The current code and
performance results require the integrator's independent query-correctness
review, including the grouping-collation assumptions documented above.
