# T10 identity correctness handoff

## Identity and outcome

- Task: T10, status IMPLEMENTED_LOCAL; independent identity/concurrency review remains mandatory.
- Base: `4e6f00be92a058251db5dc72e870174e773f70c0`; result is the commit containing this report, created using `python3 scripts/commit.py`.
- Work and test date: 2026-11-11, Europe/Warsaw (CET, UTC+01:00).
- Corrects unsafe missing-floor building matches, serializes identity corrections with writers and short index phases, and retains correction state and genuine pending events.
- Integrator authorized narrow lock-order changes in `worker.py`, `indexing.py`, `alerts.py`, and `api.py`, and stronger same-unit fixtures in three existing ingestion lifecycle tests.

## Changed files and contracts

`dedupe.py` requires matching known floors, address, phone, image and close location for building/street-only reposts; explicit unit plus corroboration and supported syndication remain possible. `ingest.py` provides `lock_identity`, suppresses correction-only events/cancellation and sorts affected homes. `identity_review.py` serializes and re-resolves before correction, rejects stale same-home corrections with 409, preserves existing pending events, queues both revisions and audits in the transaction. `marketplace.py`, `worker.py`, `alerts.py`, `api.py`, and `indexing.py` place gates before the corresponding row locks. Tests cover the matcher, existing lifecycle semantics, corrections and selected PostgreSQL interleavings. `dedupe-after.md` records unchanged corpus and results.

PostgreSQL lock order: acquire the exclusive transaction-scoped advisory identity gate before city, advert, canonical, source, report, delivery or revision locks. Preference/search/report writes and alert evaluation acquire the shared gate before resolving canonical IDs or locking their rows. Index snapshots and acknowledgements acquire the shared gate, then revision rows in sorted ID order; the gate is released at transaction end before Elasticsearch network I/O. The existing delivery cancellation takes delivery locks before revision queueing; final delivery eligibility reads stay nonlocking. The global exclusive gate deliberately serializes canonical writes across cities and can reduce throughput. No blind retry is introduced. Integrate T04 refresh under the exclusive identity gate before city/source locks. T15 account-closure integration must agree one global order for the identity and account locks; it is not yet verified here. Public GETs do not take this gate.

No schema, migration, external service or configuration changes. A rollback can restore the prior code, but does not undo committed moderation decisions; restore from tested database backup or use an audited forward correction rather than silently discarding historical data.

## Acceptance and test evidence

| Criterion | Status | Evidence and limits |
| --- | --- | --- |
| T10-AC01 | PASS on frozen synthetic corpus | TC01: 0/100 known negatives and 0/40 ambiguous pairs auto-merged. |
| T10-AC02 | PASS on frozen synthetic corpus | TC01: 80/80 known positives, 100% recall; fixture is not representative market data. |
| T10-AC03 | PARTIAL | TC02 opposite merges and TC03 published edit versus merge exercised on PostgreSQL with bounded timeouts; reverse batch writer versus snapshot and preference versus merge also exercised. Split versus edit and exhaustive transaction combinations have not been proved. |
| T10-AC04 | PARTIAL | TC04/TC05 local tests retain favorite, floor, seen, old link and both split shortlists; future split-source update tested. Further concurrent preference and split combinations need independent review. |
| T10-AC05 | PARTIAL | TC04 genuine pending price drop survives merge and no identity-only notification; TC05 split leaves baselines and emits no immediate alert. More complex multiple pending events/delivery histories require review. |
| T10-AC06 | PARTIAL | TC06 real PostgreSQL injected pre-commit failure confirms aliases, source/observation ownership, favorites, revisions and audit roll back; retry succeeds. Hidden state is covered locally, not all concurrency combinations. |

| Test case | Result |
| --- | --- |
| T10-TC01 | PASS: development and final one-time holdout results, production sequence and diagnostic injections in `dedupe-after.md`. |
| T10-TC02 | PASS: concurrent opposite merges yield one success and one 409, one alias and both sources on survivor. |
| T10-TC03 | PARTIAL: concurrent published edit versus merge passed with lock timeout; split versus edit not separately exercised. |
| T10-TC04 | PASS for tested case: overlapping searches, seen/favorite, pending price drop, old-link resolution; exactly one price-drop notification. |
| T10-TC05 | PASS for tested case: mistaken manual merge then split keeps both favorites and seen state; later updates to both sources remain separate, with no new-match notification. |
| T10-TC06 | PASS for merge rollback/retry: injected failure after flush before commit with PostgreSQL; revisions, aliases, sources, observations, favorite and audit all checked. Split rollback not separately tested. |

## Verification

All commands run from this worktree with Python 3.12.9, Node 24.6.0, macOS 15.7.7 arm64. PostgreSQL 16 and Elasticsearch 8.19.6 ran as disposable local Docker containers; no cloud, live portal, deployment, push or real mail used.

- `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_ingestion.py backend/tests/test_identity_review.py -q`: exit 0; 18 passed, 0 failed, 0 skipped.
- Final frozen evaluation: direct `scripts.evaluate_dedupe.read_dataset`, `evaluate` once per partition, then production `sequence_evaluation` and forced/reject diagnostic calls. Run data `.local/verification/T10/final-20261111/evaluation.json`; results in `dedupe-after.md`.
- `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/evaluate_dedupe.py --help`: exit 0.
- `/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m ruff check --config backend/pyproject.toml --select F821,F822,F823 backend/realtoruch/{api,alerts,dedupe,identity_review,indexing,ingest,marketplace,worker}.py backend/tests/{test_identity_review,test_ingestion,test_service_integration}.py`: exit 0. An initial unrestricted Ruff invocation failed with 113 existing and new style findings; no broad formatting was performed.
- Earlier service profile `t10-identity-20261111` failed 1 of 84 when the stricter initial matcher broke the rental journey. After matcher revision, `t10-identity-final-20261111` passed 85, failed 0, skipped 0. The subsequent `t10-races-20261111` run failed the new edit race due to mismatched fixture city/dataset; fixture corrected. The final full service profile and its counts are recorded below.

- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/verify.py services --run-id t10-complete-20261111`: exit 0; 87 passed, 0 failed, 0 skipped. Sanitized report `.local/verification/T01/t10-complete-20261111/report.json`. This invokes the same services profile as `make verify-services`; the repository root virtual environment was used without adding a worktree environment link. The selected new races use deterministic events/barriers and PostgreSQL `lock_timeout` of 5 seconds. A separate run against a temporary PostgreSQL 16 container, `TEST_POSTGRES_URL=<disposable local URL> PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_service_integration.py -k 't10_' -q`, passed all five targeted races; the container was removed.

## Risks and review

This implementation is conservative but not a proof of real-world home identity: distinct same-floor units can share contact and photos. The global writer gate adds contention. The synthetic holdout is finite and does not cover all real layouts. Alert events lack source attribution, so correction preserves pre-existing pending events but cannot always attribute a pre-split event to the separated source. Concurrent merges/splits, pending deliveries, account closure, retention, profile changes, index acknowledgements and future writers require independent integration review. T04's validator shortcut must join the exclusive gate; T15 must coordinate account-lock order. The T08 reference hardware performance benchmark remains unverified.
