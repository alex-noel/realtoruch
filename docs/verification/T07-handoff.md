# T07 handoff — collection soak

- Status: **INCOMPLETE** for the live 72-hour gate; local harness and failure drill verified.
- Reviewed base: `8a1380ca130e6bdf0df9d3b67275912b0b50d1cd`.
- Pinned harness commit: `b3782cca0f4a05b788e4fd00656ef01327deb552`, created with `python3 scripts/commit.py -m "Run resumable bounded collection soaks"`; equal author and committer timestamps `2021-11-11T22:24:48+01:00`. The documentation is recorded separately so the running checkout remains at the reviewed pin.
- Actual work/test date: 2026-11-11 UTC (2026-11-11 Europe/Warsaw).
- Outcome: Start or resume a bounded local collector schedule with explicit intervals, persisted counts, runner gaps and separate real/fixture evidence.
- Scope: Integrator approved two opt-in connector controls to enforce the T07 budget. No changes to default provider policy, SQL schema, public DTO, routes or settings.

## Changed files and contracts

- `scripts/reliability.py`: Add the pinned scheduler and child-process isolation. Keep the original bounded command.
- `scripts/soak_report.py`: Read-only aggregate report with provider dispositions, actual elapsed coverage, history growth and live-removal status.
- `backend/realtoruch/connectors.py`: For the soak, discovery spends new-detail slots only on new URLs and aborts a provider when the first robots control exhausts its retry. Add counters for separate detail classes; defaults are unchanged.
- `backend/tests/test_reliability_runner.py`: Restart, SQLite recovery, exact budget, failure, history, delivery and reporting checks.
- `docs/verification/collection-soak.md` and this handoff: Commands, limits and evidence.

## Acceptance evidence

| Acceptance | Status | Case | Evidence |
| --- | --- | --- | --- |
| T07-AC01 | PASS (controlled) | T07-TC01 | Terminated after two persisted slots; restarted, terminated during slot 3 and restarted again. Slots 1–2 unchanged, no replay of slot 3, slot 4 kept its original ID/time. A separate SQLite recovery test retained the completed provider checkpoint and exposed incomplete attempt counts. |
| T07-AC02 | INCOMPLETE (live) | T07-TC02 | Actual runtime and interval count are below the 72-hour/12-eligible gate. The fake-clock boundary test checks the predicate only. |
| T07-AC03 | INCOMPLETE (live) | T07-TC02, T07-TC05 | First slot accounted for: Otodom and Morizon each checked two adverts; Gratka's discovery parser failed before details. 11 intervals pending. Controlled aggregation includes failed, deferred and missed intervals in the denominator. |
| T07-AC04 | PASS (controlled) | T07-TC03, T07-TC04 | Timeout, 403, 429, two persisted-backoff deferrals and malformed HTML preserved active state and notification history. Duplicate delivery and same-price relist created no additional inbox or file notices. |
| T07-AC05 | PASS (controlled) | T07-TC04 | Unchanged repeats on the same UTC day added zero observations; next day added one checkpoint. Reprice and confirmed status changes were retained across fresh worker processes. Live long-duration behavior remains open. |
| T07-AC06 | PASS (reporting) | T07-TC05, T07-TC06 | Verified separate labels for failed/deferred provider work, missed windows, and absent live removals. Controlled removals never enter live totals. |

Case outcomes: T07-TC01 PASS; T07-TC02 INCOMPLETE, actual elapsed live acceptance;
T07-TC03 PASS; T07-TC04 PASS; T07-TC05 PASS; T07-TC06 PASS. Local results do not
close the external gate. A per-provider cap test also spent exactly 18 bounded
attempts in the worst case and confirmed fail-closed robots handling.

## Verification

Executed on 2026-11-11 in the assigned `t07` worktree on macOS 15.7.7
(Darwin 24.6.0, arm64), Python 3.12.9, SQLite 3.50.2, SQLAlchemy 2.1.8 and
HTTPX 0.28.1:

```sh
PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_reliability_runner.py -o addopts='' -q --basetemp .local/verification/T07/drill-pinned-20261111
PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_collection_health.py backend/tests/test_collection_cloud.py backend/tests/test_connectors.py backend/tests/test_portals.py backend/tests/test_rental_journey.py backend/tests/test_lifecycle.py backend/tests/test_metrics.py -o addopts='' -q --basetemp .local/verification/T07/regression-20261111
/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/ruff check --target-version py310 scripts/reliability.py scripts/soak_report.py backend/tests/test_reliability_runner.py
git diff --check
python3 scripts/reliability.py --help
python3 scripts/reliability.py soak --help
```

The pinned targeted suite exited 0: **7 passed, 0 failed/skipped** (9.06 s).
An earlier drill run exposed two fixture errors: a synthetic discovery page
lacked the portal's embedded state and a synthetic reprice was scheduled
within the accumulated provider backoff. The drill was corrected to use the
parser contract and wait past the simulated deadline. A retry was needed to
create the parent directory for the ignored pytest artifacts. No live request
was part of these tests.

The local regression exited 0: **138 passed, 0 failed, 6 skipped** (13.49 s).
The skips require isolated PostgreSQL, Elasticsearch or local Helm; no new
schema or deployment was exercised by T07. One existing Starlette TestClient
deprecation warning appeared. Ruff, whitespace and CLI help checks exited 0.
The fixture dates are clock inputs; the verification date above is real.

The integrator started the exact live command in [collection-soak.md](collection-soak.md)
in the detached `t07-live` checkout. Its foreground session was still running at
handoff, so the live process has no exit code yet. The read-only report command
exited 0 after the first slot; its `INCOMPLETE` status is the acceptance result.
The first live slot recorded four real observations in 10 HTTP attempts and zero
removals. It consumed 5,343,443 body bytes and used three robots requests, zero
retries, and zero lease losses. See the report for per-provider counts and times.

## Reproduction, risk and recovery

See [collection-soak.md](collection-soak.md) for the exact pinned live
invocation and read-only report command. Re-run the targeted tests to reproduce
the failure drill. Keep the private live database and manifest together.
Resume with the same ID and full SHA; missed slots are not refilled. Do not
run the regular collector or a second writer against this catalog. The run
directory is ignored and can be archived after the process exits. Removing
this harness requires no database rollback.

Before final integration, compare the pinned collection path, runtime/config
and SQL ingestion changes with the final candidate. Recheck affected local
cases against the final version, and identify version gaps in any live claim.
The pinned run does not establish 72-hour reliability for later code, provider
coverage, a 30-day SLA or real email delivery.

## Blocker and next action

G04 needs a runner available through 2026-11-14 21:27:38.320642 UTC. Initial
coverage is 41.41 seconds and one eligible slot; the first Gratka parser failure
also leaves the per-provider gate open. The next scheduled slot is 2026-11-12
03:27:38.320642 UTC. Keep the owned foreground runner and pin intact; inspect the
existing manifest after the horizon. Any detected gap remains incomplete. If
Gratka continues to fail, investigate using permitted evidence and record the
candidate version gap. Do not repair or probe out of schedule in the pinned run.

The first live slot accessed only the three named providers; OLX remained
disabled. No accounts, real email, cloud, deployment or Git push were used.

## Parent integration review

The parent reviewed the pin checks, private run directory, inherited process
lock, clean child environment, persisted schedule, counters and report allowlist.
After integration with T15 and T16, the collector, ingestion, worker and database
entry points match the pinned run. The combined model/registry additionally has
account-closure tombstones and message cursors; those are absent from the pinned
soak catalog. Email account actions also have the new closure guard, but no email
worker runs in this soak. These differences remain explicit version limits on
the live evidence.

The parent independently ran the reliability, collection-health, cloud-fake,
connector, portal, rental-journey and lifecycle suites on 2026-11-11:
**141 passed, zero failed or skipped**. Ruff and whitespace checks passed.
The foreground run is owned by the integrator, session `50850`, at the unchanged
detached pin. This local acceptance does not close the live elapsed-time gate.
