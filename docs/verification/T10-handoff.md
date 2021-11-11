# T10 identity correctness handoff

## Identity and outcome

- Task: T10, current status VERIFIED for the specified local cases after independent T32 review and correction regressions; see the final acceptance update below.
- Base: `4e6f00be92a058251db5dc72e870174e773f70c0`; result is the commit containing this report, created using `python3 scripts/commit.py`.
- Actual work and test date: 2026-11-11, Europe/Warsaw (CET, UTC+01:00). Git dates are intentionally different under repository policy.
- Corrects unsafe missing-floor building matches, serializes identity corrections with writers and short index phases, and retains correction state and genuine pending events.
- Integrator authorized narrow lock-order changes in `worker.py`, `indexing.py`, `alerts.py`, and `api.py`, and stronger same-unit fixtures in three existing ingestion lifecycle tests.

## Changed files and contracts

`dedupe.py` requires matching known floors, address, phone, image and close location for building/street-only reposts; explicit unit plus corroboration and supported syndication remain possible. `ingest.py` provides `lock_identity`, suppresses correction-only events/cancellation and sorts affected homes. `identity_review.py` serializes and re-resolves before correction, rejects stale same-home corrections with 409, preserves existing pending events, queues both revisions and audits in the transaction. A split returns HTTP 409 with detail `Pending alert state prevents this split; retry after it is resolved` while any unprocessed event, unread notification, or nonterminal delivery exists for the combined home; rejection leaves state untouched. After event processing, inbox read and delivery completion, retry succeeds. Historical terminal/read notifications remain immutable records of the pre-correction combined card on the retained canonical ID, with ambiguous source provenance; they do not assert which separated source caused an older event. `marketplace.py`, `worker.py`, `alerts.py`, `api.py`, and `indexing.py` place gates before the corresponding row locks. Tests cover the matcher, existing lifecycle semantics, corrections and selected PostgreSQL interleavings. `dedupe-after.md` records unchanged corpus and results.

PostgreSQL lock order: acquire the exclusive transaction-scoped advisory identity gate before city, advert, canonical, source, report, delivery or revision locks. Preference/search/report writes and alert evaluation acquire the shared gate before resolving canonical IDs or locking their rows. Index snapshots and acknowledgements acquire the shared gate, then revision rows in sorted ID order; the gate is released at transaction end before Elasticsearch network I/O. The existing delivery cancellation takes delivery locks before revision queueing; final delivery eligibility reads stay nonlocking. The global exclusive gate deliberately serializes canonical writes across cities and can reduce throughput. No blind retry is introduced. Integrate T04 refresh under the exclusive identity gate before city/source locks. T15 account-closure integration must agree one global order for the identity and account locks; it is not yet verified here. Public GETs do not take this gate.

No schema, migration, external service or configuration changes. A rollback can restore the prior code, but does not undo committed moderation decisions; restore from tested database backup or use an audited forward correction rather than silently discarding historical data.

## Acceptance and test evidence

| Criterion | Status | Evidence and limits |
| --- | --- | --- |
| T10-AC01 | PASS on frozen synthetic corpus | TC01: 0/100 known negatives and 0/40 ambiguous pairs auto-merged. |
| T10-AC02 | PASS on frozen synthetic corpus | TC01: 80/80 known positives, 100% recall; fixture is not representative market data. |
| T10-AC03 | PASS for specified controlled cases | TC02 opposite merges and TC03 published edit versus merge and split exercised on PostgreSQL with bounded timeouts; reverse batch writer versus snapshot and preference versus merge also exercised. This does not prove all possible interleavings. |
| T10-AC04 | PASS for specified cases | TC04/TC05 retain favorite, floor, seen, old link and both split shortlists; later updates to both sources remain separate. |
| T10-AC05 | PASS for specified cases | TC04 genuine pending price drop survives merge; split rejects pending events, unread notifications and nonterminal deliveries without changing them, succeeds after drain, preserves historical notification and emits no correction-only alert. |
| T10-AC06 | PASS for specified cases | TC06 real PostgreSQL injected pre-commit failure confirms merge and split rollback and successful retry. Hidden state and revisions are checked. |

| Test case | Result |
| --- | --- |
| T10-TC01 | PASS: development and final one-time holdout results, production sequence and diagnostic injections in `dedupe-after.md`. |
| T10-TC02 | PASS: concurrent opposite merges yield one success and one 409, one alias and both sources on survivor. |
| T10-TC03 | PASS: published edit versus merge and versus split each run on PostgreSQL with controlled gate ordering and a 5-second lock timeout; source/advert ownership and revisions verified. |
| T10-TC04 | PASS for tested case: overlapping searches, seen/favorite, pending price drop, old-link resolution; exactly one price-drop notification. |
| T10-TC05 | PASS for tested case: mistaken manual merge then split keeps both favorites and seen state; later updates to both sources remain separate, with no new-match notification. |
| T10-TC06 | PASS: merge and split each inject failure after flush before commit with PostgreSQL; revisions, source/observation ownership, favorite and audit checked after rollback; retry succeeds. |

## Verification

All commands run from this worktree with Python 3.12.9, Node 24.6.0, macOS 15.7.7 arm64. PostgreSQL 16 and Elasticsearch 8.19.6 ran as disposable local Docker containers; no cloud, live portal, deployment, push or real mail used.

- `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_ingestion.py backend/tests/test_identity_review.py -q`: exit 0; 18 passed, 0 failed, 0 skipped.
- Final frozen evaluation: direct `scripts.evaluate_dedupe.read_dataset`, `evaluate` once per partition, then production `sequence_evaluation` and forced/reject diagnostic calls. Run data `.local/verification/T10/final-20261111/evaluation.json`; results in `dedupe-after.md`.
- `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/evaluate_dedupe.py --help`: exit 0.
- `/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m ruff check --config backend/pyproject.toml --select F821,F822,F823 backend/realtoruch/{api,alerts,dedupe,identity_review,indexing,ingest,marketplace,worker}.py backend/tests/{test_identity_review,test_ingestion,test_service_integration}.py`: exit 0. An initial unrestricted Ruff invocation failed with 113 existing and new style findings; no broad formatting was performed.
- Earlier service profile `t10-identity-20261111` failed 1 of 84 when the stricter initial matcher broke the rental journey. After matcher revision, `t10-identity-final-20261111` passed 85, failed 0, skipped 0. The subsequent `t10-races-20261111` run failed the new edit race due to mismatched fixture city/dataset; fixture corrected. The final full service profile and its counts are recorded below.

- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/verify.py services --run-id t10-complete-20261111`: exit 0; 87 passed, 0 failed, 0 skipped. Sanitized report `.local/verification/T01/t10-complete-20261111/report.json`. This invokes the same services profile as `make verify-services`; the repository root virtual environment was used without adding a worktree environment link. The selected new races use deterministic events/barriers and PostgreSQL `lock_timeout` of 5 seconds. A separate run against a temporary PostgreSQL 16 container, `TEST_POSTGRES_URL=<disposable local URL> PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_service_integration.py -k 't10_' -q`, passed all five targeted races; the container was removed.

- Follow-up reproduction before fix: `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_identity_review.py -k split_blocks_pending -q` failed because split returned 200 while a genuine favorite price-drop event was pending. After the guard, the same test passed and verifies unchanged rows, revisions and preferences across 409s, then successful split after event, inbox, email and push receipt drain.
- Follow-up local regression: `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_ingestion.py backend/tests/test_identity_review.py -q` passed 19, failed 0, skipped 0.
- Follow-up `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/verify.py services --run-id t10-split-20261111`: exit 0; 90 passed, 0 failed, 0 skipped, disposable PostgreSQL 16/Elasticsearch 8.19.6. Report `.local/verification/T01/t10-split-20261111/report.json`. PostgreSQL cases include split versus published edit, split rollback/retry, and pending-event/inbox/email/push guard and retry. The inbox retrieval assertion was added and passed locally immediately afterward; no production code changed after the service run. The frozen holdout was not rerun.

## Risks and review

Parent integration review accepted the conservative matcher and correction guards. Independent verification on the combined integration checkout: 19 targeted tests and 90 real PostgreSQL/Elasticsearch service/race tests passed with zero skips (`.local/verification/T01/integrated-t10-review/report.json`). No holdout tuning or additional holdout evaluation was performed by the parent.

This implementation is conservative but not a proof of real-world home identity: distinct same-floor units can share contact and photos. The global writer gate adds contention. The synthetic holdout is finite and does not cover all real layouts. Legacy alert events and notifications lack source attribution. Outstanding work blocks splitting; terminal/read historical notifications remain unchanged on the retained pre-correction combined card and cannot be attributed to either separated source. Concurrent merges/splits, pending deliveries, account closure, retention, profile changes, index acknowledgements and future writers require independent integration review. T04's validator shortcut must join the exclusive gate; T15 must coordinate account-lock order. The T08 reference hardware performance benchmark remains unverified.

## T32 acceptance update — 12 November 2026

Independent review and the current combined profiles passed on `a17cf16f4e6c3c33d629684fd6a75685eb147b53`. The final [frozen synthetic report](dedupe-final.json) supersedes the earlier matcher metrics; automated determinism tests reuse the corpus, so it is not an untouched statistical holdout. T08 controlled resource-budget convergence passed. Correction-alert fix `d56ae23` evaluates scoped pre-merge genuine work and silently baselines corrected prices/matches for merge and both split homes. Historical floors never rise; backlog/partial-drain rejection rolls back all effects. [Current review, semantics and tests](T32-handoff.md) supersede the original integration-pending statements above.
