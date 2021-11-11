# T26 handoff — Operational metrics and runbooks

- Status: VERIFIED locally after the integrator's independent privacy/operations review and combined service verification.
- Base: `fbbd6d95c8f0432200e3a4677eeb53fa113041cb`. Implementation: `cdcc56eeb0db94955c3480552d8be6461f8f5fad`, created with `python3 scripts/commit.py`; author and committer dates both `2021-11-11T22:03:45+01:00`.
- Actual work and verification: 2026-11-11 Europe/Warsaw (CET), including PostgreSQL restore at 22:01 CET. Evidence dates describe actual work, independently of Git timestamps.
- Outcome: Operators can scrape private queue and collection snapshots, check each service's required dependencies, and diagnose six incidents without reading private account or listing content.
- Scope agreed with integrator: service-profile test module registration, three index log redactions and two private worker readiness flags. No Helm, Terraform, grants, or database migration changes.

## Changes and compatibility

| Files | Change |
| --- | --- |
| `backend/realtoruch/metrics.py` | Indexed aggregate snapshots; fixed labels; explicit unknown source success; one in-flight scrape per process; bounded read transaction and sanitized failure metric. Read-only readiness helpers check the required SQL tables and worker dependencies. |
| `backend/realtoruch/api.py`, `backend/realtoruch/auth.py` | Internal key guard on both metrics routes. Each uses its own database. REST readiness remains healthy when the optional search projection is unreachable. Auth readiness checks the auth tables. Liveness still answers without SQL. |
| `backend/realtoruch/worker.py`, `backend/realtoruch/auth_jobs.py`, `backend/realtoruch/indexing.py` | Structured collection, index, delivery and erasure signals omit identifiers and errors. Worker `--check-ready` checks read dependencies without claiming work or sending mail. Existing delivery fencing, backoff and index revision behavior are unchanged. |
| `backend/tests/test_metrics.py`, `scripts/verify.py` | SQLite and PostgreSQL snapshots, PostgreSQL timeout recovery, real ES revision diagnosis, SQL fallback, worker privacy/probes, six runbook SQL diagnostics, and actual Helm render checks. PostgreSQL and ES tests are required in the existing services profile. |
| `docs/operations/runbooks.md` | Metric names, types, units, allowlists, initial thresholds and six local runbooks. |

No migration reservation was needed. Retained the `realtoruch_outbox_pending` gauge as total undelivered depth. Deployment must provide the internal key to scrapers. Existing readiness and health status shapes remain coarse. Roll back the application revision and scraper changes together if needed; no schema rollback.

## Acceptance evidence

| Acceptance | Test case and result | Verification |
| --- | --- | --- |
| T26-AC01 PASS | **TC01 PASS:** correct depth and oldest due age on both owning databases; future scheduled deliveries, active leases, cancelled/failed jobs and held 400/413 index items excluded from ready age; expired delivery leases and due push receipts count as ready. Search outbox creation time is not a scheduling deadline, as corrected in the parent integration review below. Collection lifecycle metrics include success age, failure count, backoff, recent attempt states and lease expiry. | `test_t26_postgres_queue_snapshots_and_runbook_diagnostics`, `test_t26_sqlite_queue_snapshots`. |
| T26-AC02 PASS | **TC02 PASS:** absent and never-successful sources produce a known flag of 0 and no age; private canaries inserted into provider, city, run status, URL, ID, account and error fields were absent from metrics and worker logs. Both unauthorized metrics routes deny before opening SQL. | PostgreSQL and SQLite queue tests, `test_t26_sqlite_private_worker_logs`, and diagnostic failure sanitization test. |
| T26-AC03 PASS | **TC03 PASS:** a separate PostgreSQL connection held `ACCESS EXCLUSIVE` on outbox while the scrape ran. The 250 ms statement timeout produced only `metrics_collection_success 0` within the test bound (0.15–2 s), a normal listing read succeeded while the lock was still held, and the next checkout of the singleton pool had its default timeout. Scrape recovered after lock release. | `test_t26_postgres_timeout_does_not_poison_api`. Existing indexes cover query predicates; no capacity result at production load is claimed. |
| T26-AC04 PASS | **TC04 PASS:** a real refused loopback ES connection made the search service unready, while REST was ready and returned a listing from SQL with `degraded=true`. Separately blocked rental and auth SQL produced sanitized 503s only for the corresponding service, with liveness still 200. Worker check tests verify no claim, no mail, and distinct missing cleanup/config conditions. | `test_t26_postgres_readiness_and_search_fallback`, `test_t26_sqlite_worker_readiness_is_read_only`. |
| T26-AC05 PASS | **TC05 PASS:** executed all six runbook SELECT blocks against migrated synthetic schemas. Detected 403/429 counts, expired lease, held/eligible index work, email states, stalled erasure and both migration histories. Real ES returned an older revision via `?_source=false`; one normal bounded worker pass converged to SQL. Restored both disposable databases with matching logical contents, including pending index work and erasure. | PostgreSQL runbook tests, `test_t26_postgres_and_es_index_runbook`, restore rehearsal. Retrying restored erasure and production recovery are T27 work. |
| T26-AC06 PASS | **TC06 PASS:** actual default and collector-enabled Helm renders show neither diagnostics path in ingress, no catch-all backend, only ClusterIP services without external IP/NodePort, namespace default deny and restricted network-policy ingress. Separately checked direct unauthorized HTTP access is 403. | Two `test_t26_helm_diagnostics_boundary` cases and the route tests. This verifies configuration and application guards, with no live ingress deployment. |

## Verification

Working directory for all commands: `/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t26`. Runtime: macOS 15.7.7 arm64, Python 3.12.9, Node 24.6.0, Docker server 29.8.0, PostgreSQL 16.15 and Elasticsearch 8.19.6. Helm v3.16.4 arm64 was downloaded into the ignored T26 tools directory and verified against the [published SHA-256](https://github.com/helm/helm/releases/tag/v3.16.4#installation-and-upgrading). Raw logs, rendered YAML, reports and dumps are under ignored `.local/verification/T26/`.

| Command | Result |
| --- | --- |
| `PATH="/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH" make verify-services ARGS='--run-id t26-metrics-b'` | Exit 0; 86 passed, 0 failed, 0 skipped; 6 SQLite/Helm cases deselected by the profile. 22:03:53–22:05:14 CET; clean implementation revision; disposable PostgreSQL/ES containers removed by the runner. `services-b/report.json`. |
| `PYTHONPATH="$PWD/backend" HELM_BINARY="$PWD/.local/verification/T26/tools/darwin-arm64/helm" TMPDIR="$PWD/.local/verification/T26/final-check" .venv/bin/python -m pytest backend/tests/test_metrics.py backend/tests/test_portals.py backend/tests/test_collection_health.py backend/tests/test_indexing.py backend/tests/test_email_alerts.py backend/tests/test_push.py backend/tests/test_accounts.py -k 'not postgres' --basetemp="$PWD/.local/verification/T26/final-check/tmp"` | Exit 0; 113 passed, 0 failed, 0 skipped, 4 real-service cases deselected; `final-check/result.log`. Tests rendered `helm template t26 infra/helm/realtoruch` and the same command with `--set collector.enabled=true`. |
| `bash .local/verification/T26/restore-a/rehearse.sh` | Exit 0; wrapper started a labelled local PostgreSQL container, ran the registered migrations and seeded one listing/outbox and one closed account/pending erasure. Ran `make postgres-backup-check ARGS="--container realtoruch-t26-restore-a --user rentals --databases rentals auth"`; both databases matched counts and content digests. Private log/dumps: `restore-a/`. |
| `.venv/bin/python -m ruff check backend/realtoruch/metrics.py backend/tests/test_metrics.py`; `.venv/bin/python -m ruff format --check backend/realtoruch/metrics.py backend/tests/test_metrics.py`; `.venv/bin/python -m ruff check --select E9,F63,F7,F82 backend scripts`; `git diff --check` | Exit 0 each. |

Earlier verification caught two fixture mistakes: an omitted required notification title (first SQLite attempt, 3 passed/1 failed/3 deselected) and a synthetic status exceeding PostgreSQL's 20-character limit (`t26-metrics-a`: make exit 2, 84 passed/1 failed/0 skipped). The status-width issue reproduced in the focused PostgreSQL run (2 passed/1 failed/5 deselected). After shortening the canary, `bash .local/verification/T26/pg-focused/rehearse.sh` used a disposable PostgreSQL container, running `.venv/bin/python -m pytest backend/tests/test_metrics.py -k 'postgres and not and_es' --tb=short`: exit 0, 3 passed/0 failed/0 skipped/6 deselected (`pg-focused/result-b.log`). These fixture fixes did not weaken production behavior or privacy assertions. A supplemental pytest collect-only check initially used the root editable import by omitting `PYTHONPATH`; rerunning with `PYTHONPATH="$PWD/backend"` collected 86 selected cases, exit 0 (`services-b/collection.log`).

## Limits and next action

- The 250 ms PostgreSQL statement budget starts after acquiring a connection; network and pool acquisition use the existing connection policy. One concurrent scrape per process bounds metrics contention, and replicas sample the same SQL rather than publishing restart-sensitive counters. Confirm scraper interval and loading at scale in T25/T28.
- Collection SQL history covers the local scheduler. The existing cloud collector does not populate that history. Worker probes check SQL reads, local mail configuration and, for erasure, rental API readiness. They do not prove external provider acceptance, database writes or cleanup credential validity. Those boundaries need T28 role/probe/scraper configuration and separate external acceptance.
- Tune the provisional thresholds with T07/T25. This work does not close T08's separate reference hardware benchmark gap or prove hosted CI, cloud recovery, delivered mail, or production latency.
- No cloud resources, live provider requests, real mail, external incident messages, deployment or push were used.

## Parent review

Private diagnostics, bounded labels, transaction limits, lock cleanup and ingress boundaries were independently reviewed. `integrated-t26-review` passed 105 real-service tests with zero skips on the combined T04/T10/T11/T13 base. A separate local run passed all six SQLite/Helm tests (four PostgreSQL tests intentionally deselected). The whole offline suite exposed an obsolete assertion that anonymous `/metrics` remained public; it was updated to require the intended 403, while the dedicated metrics suite verifies authorized content and denial before SQL access. Rental email currently remains claimable when configured disabled and fails at the sender; metrics reflect that existing behavior, unlike auth mail which is excluded from claims. This task did not silently change transport behavior.

## Parent integration correction

The T12 combined service check exposed an eligibility mismatch in the original
index diagnostics. The indexer does not defer an outbox row whose creation time
is in the future, but metrics and the runbook did. Parent commit `b4ae272` removes
that diagnostic restriction, retains held 400/413 behavior and clamps negative
ages to zero. The real PostgreSQL/Elasticsearch runbook case now deliberately
sets a pending row one hour ahead, proves it is reported ready with zero age,
and proves the normal indexer drains it. Both-engine queue fixtures include the
same distinction from future scheduled email/push jobs. Four focused SQLite
cases passed; the final `integrated-t12-final` profile passed 188 tests without
failures or skips on 2026-11-11. This closes the intermittent runbook failure
without claiming its precise clock cause or altering worker eligibility.
