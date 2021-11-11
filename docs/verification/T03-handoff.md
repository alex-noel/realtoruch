# T03 collector leases handoff

## Identity and outcome

- Task: T03; status: IMPLEMENTED_LOCAL, pending mandatory independent concurrency review.
- Base: `a74ca26adc20e955527f007fee272a616d2ceaae`; result is the commit containing this report (created with `python3 scripts/commit.py`).
- Actual verification: 2026-11-11, Europe/Warsaw (CET), independently of commit dates.
- Local SQL collector renews and fences provider ownership during empty, slow and interrupted runs; stale completion cannot change replacement health.
- Scope expansion: none. Cloud coordination remains unchanged and is not covered by the SQL guarantee.

## Changed files and contracts

`collection_health.py` adds one 60-second scheduler per local run, conditional renewal, transaction-scoped fencing and guarded completion. `worker.py` integrates it into collection only. `connectors.py` checks at every request boundary and starts each run with a pacing interval. Tests cover the state machine and PostgreSQL races; `source-connectors.md` describes transitions and restart. No schema, public API, migration or configuration changes. Existing run IDs are fencing tokens. The lease row is held through ingestion to serialize takeover with the observation commit. Lease database failures fail closed with a bounded exception-class diagnostic. Restart after expiry/backoff using `make collect ARGS="--city Kraków"`.

## Acceptance evidence

| AC | Status | Test case and evidence |
| --- | --- | --- |
| T03-AC01 | PASS | TC01: simultaneous PostgreSQL separate-session claims released at a barrier; exactly one succeeds, other reports already_running; service run `t03-leases-2`. |
| T03-AC02 | PASS | TC02: fake clock and scheduler renew an empty run through 31 one-minute callbacks, beyond the 30-minute lease; targeted suite. TC06 additionally injects a renewal failure. |
| T03-AC03 | PASS | TC03: PostgreSQL response barrier places takeover before stale transaction/finish; zero receipts. SQLite worker test yields an in-flight response after takeover and verifies no receipt or second request. |
| T03-AC04 | PASS | TC03: PostgreSQL and SQLite verify replacement token, deadline, retry, failures and success timestamp survive stale finish. |
| T03-AC05 | PASS, with limitation below | TC04: separate city health reports old interrupted and replacement running; synthetic two-city connector pacing test checks configured interval across consecutive runs. |
| T03-AC06 | PASS | TC05: PostgreSQL crash/replay checks receipt, observation, source and alert counts unchanged. TC06: injected heartbeat database failure prevents next request; transport failure does not emit a removal. |

TC01–TC06 all ran and passed as described. The configured request rate is preserved across sequential SQL runs by waiting a full configured interval at each start. A robots-derived crawl delay larger than the configured interval is not persisted across independent processes: there is no durable last-request/robots-delay field in the existing schema. Strict cross-process continuity of that extra delay requires a separately reviewed durable pacing contract/schema. An already in-flight HTTP request can overlap a takeover and cannot be unsent; its result is fenced. No claim of network-level atomicity is made.

## Verification

Working directory: assigned T03 worktree. Machine: macOS 15.7.7 arm64, Python 3.12.9, Node 24.6.0. PostgreSQL 16 Alpine and Elasticsearch 8.19.6 were disposable local Docker containers, created and removed by the isolated runner; synthetic fixture data only. Base was dirty with these intended changes during both service runs. The reused root `.venv` was read-only; tests set the T03 backend path explicitly, and the service runner sets it itself.

- `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_collection_health.py backend/tests/test_collection_cloud.py -q`: exit 0, 9 passed, 0 failed, 0 skipped (final run).
- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t03-leases-1'`: exit 0, 11 passed, 0 failed, 0 skipped. Initial service check; subsequently adjusted completion reporting.
- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t03-leases-2'`: exit 0, 11 passed, 0 failed, 0 skipped. Sanitized machine report: `.local/verification/T01/t03-leases-2/report.json` (ignored, local to this worktree).
- `git diff --check`: exit 0.

PostgreSQL race ordering uses two thread workers with independent sessions and barriers: concurrent claim, then an in-flight-response barrier; expire the old lease, claim replacement, set replacement health, release stale response, test guard and completion. No arbitrary sleep coordinates either race. The replay test commits one record under the old token, expires it, claims a new token and replays the same synthetic record.

## Reproduction and review

The old behavior renews only on yielded records and allows a stale finisher to mutate state after a read/check race. Exercise tests in `test_collection_health.py` and `test_service_integration.py` to reproduce the fixed boundaries. Review transaction isolation and the provider-row lock order with later collector changes. A stuck process or database connectivity failure may delay cleanup; lease expiry allows a replacement. Restore previous code only after stopping local collectors and allowing leases to expire; no migration rollback is necessary. T04 must integrate its fetch state without bypassing request and transaction guards; T08 owns `index_once`, untouched here.

## Blockers and next action

Mandatory independent concurrency review remains. Integrator has been notified of the cross-process robots-delay limitation for scope decision. No cloud resources, real emails, live portal requests, push or deployment were used.
