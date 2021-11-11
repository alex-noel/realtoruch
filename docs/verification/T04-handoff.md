# T04 handoff — conditional detail checks and bounded provider retries

- Task: T04. Status: VERIFIED locally; independent integration review pending.
- Base: `4e6f00be92a058251db5dc72e870174e773f70c0` (reviewed T03, T08, and T13). Implementation: `326a77bcae122e8b2ca8463c602de575c6af0f11` on `codex/core-t04-latest`, made using `python3 scripts/commit.py`. Author and committer timestamps both `2021-11-11T21:52:24+01:00`; actual commit time `2026-11-11T21:52:24+01:00`, Europe/Warsaw.
- Actual verification date: 2026-11-11, Europe/Warsaw. Worktree: `/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t04-latest`. The pre-port WIP patch is untracked in the original `t04/.local/verification/T04/port/t04-wip.patch`.
- Outcome: an unchanged supported SQL-collected listing transfers no detail body once validated, while freshness, price, daily history, alerts, and provider pacing keep their distinct semantics.
- Integrator-approved additions: lease-fenced cross-city/process robots pacing, checked-only ingest helper using T08 search revisions, and unconditional cloud checks until there is a canonical SQL fence for cloud 304s.

## Changed files and contracts

- `backend/realtoruch/connectors.py` and `fetch_state.py`: body cap, request counters, conditional request and fallback rules, bounded header handling, and validation of source/URL/request variant/payload. Conditional scope is public portal and JSON-LD detail. Feed/discovery/robots do not have an eligible listing representation.
- `backend/realtoruch/collection_health.py` and the collector sections of `worker.py`: reserve provider-wide request time in short SQL transactions using the T03 token, persist provider Retry-After before finishing, and validate the current source row and metadata before any checked-only update. Pacing sleeps and HTTP are outside SQL transactions. Bigtable timing uses the existing single CronJob assumption. It adds no cloud lease or SQL privilege.
- `backend/realtoruch/ingest.py`: reuse one history rule and add a checked-only path that advances source/canonical freshness and the public search revision without recomputing displayed fields or generating alerts. `worker.index_once` and the public DTO are unchanged.
- `backend/realtoruch/models.py`, `migrations.py`, `infra/sql/005_collection_fetch_state.sql`, `infra/sql/migrations.json`: private rentals migration 005 and SQLite hook. Existing source and provider state retain their values; added timing is nullable and validator rows start empty. PostgreSQL rentals 001–004 and auth baseline files are byte-identical to the T03 base; SQLite baseline hook source is unchanged. Existing 006/008 and auth 005 registry entries remain.
- `backend/tests/test_connectors.py`, `test_collection_cloud.py`, `test_service_integration.py`: fake HTTP, clock, and cloud clients; real PostgreSQL migration, timing, and observation fences. `docs/source-connectors.md` documents behavior and report fields.
- Bigtable state payloads still read the old normalized flat shape; newer state rows may include private `_fetch`. Archive and Pub/Sub payloads and recheck queue rows are unchanged. A Pub/Sub acknowledgment does not prove SQL ingested the 200, so cloud requests stay unconditional and never publish a reused 304 as a new observation. No source enablement, infrastructure, or grants changed.

## Acceptance evidence

| AC | Status | Cases | Result |
| --- | --- | --- | --- |
| T04-AC01 | PASS | TC01 | Valid 200 then 304 with both validator headers. Two HTTP attempts in each run including robots; consumed detail body fell from 415 bytes to 0, and total consumed decoded body from 448 to 33 bytes. The 304 fixture fails if read. |
| T04-AC02 | PASS | TC02 | Unknown, missing, mismatched, drifted, deleted, and inactive payloads never refresh/invent a home. The real PostgreSQL barriers reject a concurrent replacement and reject a stale lease after takeover. |
| T04-AC03 | PASS | TC01, TC03 | Same UTC day: no extra observation or notification. Next UTC day: one unchanged checkpoint across repeated 304s. Portal-shaped crosspost fixture preserves displayed rent and alert count while search revision advances. |
| T04-AC04 | PASS | TC04, TC05 | 429 and 503 each accept delta and date forms; before stored deadline the new run sends nothing, at deadline it becomes eligible. 403 stops after one detail attempt. Real PostgreSQL checks token-fenced persistence. |
| T04-AC05 | PASS | TC05, TC06 | Timeouts, 502, and orphan fallback share a two-attempt limit. Effective 11-second robots rate, jitter on retry, and 31-second provider deadline across city runs. All attempts counted. |
| T04-AC06 | PASS | TC06, TC07 | Redirect target never contacted, oversize stream stops, neither produces a listing/validator. Legacy SQL and fake Bigtable state remain readable and recheck unconditionally. HTTP public detail and cloud events exclude private metadata. |

| Test case | Status | Executed evidence |
| --- | --- | --- |
| T04-TC01 | PASS | `test_t04_304_uses_validated_payload_and_keeps_daily_history`; `test_t04_portal_recheck_preserves_crosspost_price_and_advances_search_revision`. |
| T04-TC02 | PASS | `test_t04_orphan_304_cannot_invent_or_restore_listing` (6 cases); mismatched-tag fallback, shared retry budget, and `test_t04_postgres_conditional_response_checks_representation_and_lease_at_commit` (3 cases). |
| T04-TC03 | PASS | `test_t04_304_uses_validated_payload_and_keeps_daily_history` rechecks on both sides of UTC midnight and again on day two. |
| T04-TC04 | PASS | `test_t04_retry_after_survives_restart` (4 cases); fake Bigtable restart and `test_t04_postgres_request_reservations_and_defer_are_provider_wide_and_token_fenced`. |
| T04-TC05 | PASS | `test_t04_attempt_limits_include_robots_and_keep_provider_pacing` (3 cases); `test_t04_orphan_and_timeout_share_one_retry_budget` (2 cases); fake-clock cross-city robots test and real PostgreSQL reservations. |
| T04-TC06 | PASS | `test_t04_redirect_and_oversize_do_not_persist_partial_or_forward_auth` (2 cases). One credentialed request to the allowed host only; decoded stream stops at its first byte over 5,000,000. |
| T04-TC07 | PASS | `test_t04_legacy_sql_fetch_is_unconditional_and_public_listing_has_no_private_fields`; fake Bigtable legacy/current reads, safe validators, and publish-ack order cases. |

## Verification

All commands below ran in the worktree named above. macOS 15.7.7 arm64; Python 3.12.9; Node 24.6.0; Docker 29.8.0; native `postgres:16-alpine` and Elasticsearch 8.19.6. The worktree temporarily linked the existing Python environment to `.venv`; the link is not part of the change.

- `PYTHONPATH="$PWD/backend" .venv/bin/pytest backend/tests/test_connectors.py backend/tests/test_collection_cloud.py backend/tests/test_lifecycle.py -q -o addopts=''`: exit 0; 43 passed, 0 failed, 0 skipped (12.13 s).
- `PYTHONPATH="$PWD/backend" .venv/bin/pytest backend/tests/test_connectors.py backend/tests/test_collection_cloud.py backend/tests/test_lifecycle.py backend/tests/test_portals.py backend/tests/test_collection_health.py backend/tests/test_migrations.py backend/tests/test_migration_registry.py -o addopts='' -q`: exit 0; 123 passed, 0 failed, 0 skipped (12.79 s). One existing Starlette TestClient deprecation warning. The previous 121-case run passed before the two combined timeout/orphan cases were added. An earlier 30/1 run exposed a crosspost fixture with no building number; the synthetic pair was given a matching unit address to establish the intended identity before rerunning.
- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t04-fetch-1'`: exit 0; 87 passed, 0 failed, 0 skipped. Worktree changes before commit, including the five new PostgreSQL cases. Runner-owned containers were cleaned up.
- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t04-fetch-2'`: exit 0; 87 passed, 0 failed, 0 skipped. Clean implementation revision; 21:52:34 to 21:53:39 Europe/Warsaw. Machine report: `.local/verification/T01/t04-fetch-2/report.json`, with sanitized copy at `.local/verification/T04/t04-fetch-2/report.json`. Runner exercises actual PostgreSQL and Elasticsearch; provider HTTP and cloud clients are fakes.
- `git diff --cached --check` before the implementation commit: exit 0. `git diff ef7788d..326a77b -- infra/sql/001_rentals.sql infra/sql/002_alerts.sql infra/sql/003_email_alerts.sql infra/sql/004_marketplace_rentals.sql infra/sql/001_auth.sql infra/sql/004_accounts_auth.sql`: empty diff.

The PostgreSQL migration test applies 001–004 to an isolated tracked schema with an existing lease, backoff, last success, and failure count, then applies and repeats the full registry; every old value and checksum survives. The fresh service fixtures use the full registry. The SQLite test starts from an existing provider row and the original registered baseline hook, then runs the additive hook twice.

The race tests pause the second detail response at a two-party barrier. Another transaction acquires provider/source locks using NOWAIT during HTTP, then changes the payload or expires the owner and installs replacement metadata. Releasing the old response cannot move freshness, add history, or delete the replacement state. The timing test separately proves another PostgreSQL connection can acquire the provider lock between reservations, and stale reserve, pacing extension, and defer mutations all fail against a new token.

## Review and recovery

- Retain additive schema when rolling application behavior back. Recreate only disposable branch test schemas; never apply a partial branch registry to a persistent catalog or reorder applied versions. The supported production-style upgrade starts from the tracked 001–004 rental baseline to the full selected registry. Use a backup or forward fix for a persistent catalog. Private validator metadata can be rebuilt from successful unconditional 200s.
- An HTTP request already handed to the transport may complete after lease loss. SQL cannot unsend it; its effects are fenced. The pacing reservation is written before starting HTTP, and a robots rule becomes durable once parsed. Bigtable timing relies on the existing single CronJob coordination and has no claim against concurrent cloud writers.
- T10 integration must acquire its `lock_identity(session)` before the city/source lock in `worker.verify_reuse`, inside the provider-fenced checked-only transaction. This lock is absent from the reviewed T04 dependency base. Coordinate the insertion with the T10 integrator before combined acceptance. T08 revision behavior was verified; indexing and delivery implementations were not changed.
- No external gate is required for T04's local scope. No portal was contacted; no GCP resources, real email, push, or deployment were used. Cloud envelope and timing behavior are fake-client evidence only.

Parent integration: added T10's exclusive identity gate before the checked-only city/source locks and preserved all T10/T13 tests while resolving the append-only service-test conflict. The combined service profile `integrated-t04-review` passed with zero skips. Expanded portal/collector/migration/identity tests initially exposed an existing T10 street-only matcher regression (122 passed, 1 failed); the parent tightened the building-evidence rule in a separate correction and then repeated the expanded tests: 142 passed, zero skips. No live-source or deployed-cloud claim follows from these checks.
