# History and summary baseline (2026-11-11)

History uses the current UTC calendar month and N−1 preceding months: `[first day 00:00 UTC, query time]`. For each source and month, its latest observation determines whether it is active. Of active sources, the latest observation for each canonical home supplies one vote; exact timestamp ties use descending source ID and observation ID. No active observation means no vote, and empty months are omitted. Rent is observed advertised base PLN, excluding fees; it is not a lease price or a census. Per-m² uses the current canonical area, not historical area. Even-sample medians can be fractional. Demo flags indicate any sampled demo home. Historical source observations follow canonical merge/split corrections.

The PostgreSQL and SQLite implementations calculate rankings and medians in SQL, returning monthly aggregates only. Summary uses SQL aggregates and distinct location strings; it does not instantiate the catalog or construct an ID list. The four summary statements do not guarantee a single snapshot during concurrent changes. There is no cache or new schema migration. Reservation 007 remains unused: on this full-city fixture the actual PostgreSQL EXPLAIN chose sequential scans of all 100,000 observations and 10,000 homes, with an external sort of 7,272 kB; it does not justify another index for this workload. Other selective workloads should be measured separately before adding indexes.

## Local measurements

2026-11-11, Apple M4 Pro, 64 GiB RAM, macOS 15.7.7 arm64, Python 3.12.9, PostgreSQL 16 Alpine in Docker and SQLite from Python. Deterministic fixture: 10,000 homes, one source each, 100,000 observations spanning 180 days, one city, 10 districts. Local FastAPI TestClient, no network or deployed service. For each endpoint: one first request, three warmups, 30 measured requests; p95 is nearest-rank `ceil(0.95 * 30)` (29th sorted sample). An independent fresh measurement process records maximum RSS growth across both endpoints (peak high-water mark relative to after TestClient startup), and Python traced allocation peaks per endpoint. The T01 service regression was running concurrently with part of the PostgreSQL run. These are local measurements, not production capacity claims.

| Engine | Endpoint | First ms | Warm p95 ms | SQL statements/request | Python traced peak | Process peak RSS growth |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PostgreSQL | history | 399.7 | 364.0 | 1 | 1.68 MiB | 4.17 MiB across both |
| PostgreSQL | summary | 48.6 | 30.3 | 4 | 0.64 MiB | same |
| SQLite | history | 510.7 | 453.7 | 1 | see raw report | 56.8 MiB across both |
| SQLite | summary | 27.8 | 21.2 | 4 | see raw report | same |

Raw samples and EXPLAIN are in ignored `.local/verification/T11/20261111-local/`. To reproduce, set `PYTHONPATH=backend`, use a **new, empty disposable** database URL, and run `python scripts/seed_benchmark.py --url "$URL"`; then run a fresh process `DATABASE_URL=sqlite:// AUTH_DATABASE_URL=sqlite:// python scripts/seed_benchmark.py --measure-only --url "$URL"`. The first invocation seeds and also measures; the second isolates RSS from seed allocations. The script refuses to seed any database containing tables. Destroy the disposable database after measurement.
