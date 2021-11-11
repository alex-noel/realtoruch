# T15 account-data lifecycle handoff

## Identity and outcome

- Task: T15. Status: IMPLEMENTED_LOCAL; independent privacy/concurrency review and combined T16 integration remain pending.
- Base: `49d4bcf77114675d62fa9578aee559bdee4b4bff`. Result: the commit containing this report, created with `python3 scripts/commit.py`; obtain its ID with `git log -1`.
- Actual work and verification: 2026-11-11, Europe/Warsaw (CET); the service run below was 22:12:40–22:13:54 CET. Git timestamps are intentionally different per repository policy.
- Outcome: closure fences stale rental writes; a password-reauthenticated user can obtain a bounded, private own-data export.
- Integrator approved the narrow `security.py` CORS header change and `identity_review.py` moderator guard. Conversation hooks must be merged with T16's cursor implementation at its four write sites, not replace it.

## Changes and contract

- `account_data.py`, `models.py`, rentals migration `009_account_closure.sql`, registry and additive SQLite hook: opaque user-ID tombstone and transaction-scoped per-user serialization. PostgreSQL uses a transaction advisory lock; SQLite takes/upgrades a writer reservation. Previously applied migrations/hooks are unchanged.
- `api.py`, `marketplace.py`, `email_alerts.py`, `identity_review.py`: guard account writes after any required identity gate and before owned row locks. Cleanup takes exclusive identity gate, account guard, sorted conversation locks, then deletes owned rows; own published source content is withdrawn and scrubbed. Email token actions re-read after acquiring the guard. Delivery completion retains T13's delivery-first/nonlocking-read order.
- `auth.py`, `security.py`: purpose/audience-separated five-minute JWT bound to user and login session, current password checked, dedicated CORS-allowed header. Normal authenticated access is independently validated on download. All export/reauth responses are private/no-store.
- `docs/privacy-data-map.md`: v1 export/error/retention/recovery contract. Export reads a PostgreSQL repeatable-read snapshot while the guard is held; SQLite uses the guarded transaction. It preflights variable-length fields in SQL and encodes incrementally with a 10 MiB cap; legacy invalid nested objects fail closed with 422. It uses explicit field allowlists and excludes received messages and all stored token/hash fields. 413 `export_too_large` is a complete error, not a partial export.
- `test_account_data.py` and `scripts/verify.py`: focused lifecycle tests and service profile inclusion. Registry integration must retain T11 007 and T16 010, plus any other independently integrated entries.

## Acceptance evidence

| Criterion | Status | Test cases and evidence |
| --- | --- | --- |
| T15-AC01 | PASS locally | TC01: `test_stale_authorization_cannot_write_after_cleanup`, `test_real_write_routes_reject_prior_authorization`, `test_guarded_write_finishes_before_cleanup`; SQLite and PostgreSQL in final service run. Favorite, profile and message routes receive previously authorized identities. Combined T16 lock interaction still needs integration review. |
| T15-AC02 | PASS locally | TC02: `test_rollback_and_retry_pending_erasure` injects failure after prior deletes, observes rollback, retries and repeats cleanup in SQLite and PostgreSQL. `test_cleanup_scrubs_own_advert_and_conversation` exercises actual published source/conversation cleanup in SQLite. |
| T15-AC03 | PASS locally | TC03: `test_deleted_email_re_registers_with_new_id` proves new ID/empty profile and old access rejection; tombstone also checked in both databases. |
| T15-AC04 | PASS locally | TC04/TC07: `test_export_auth_scope_and_size`, `test_sent_message_export_excludes_received_and_unknown_fields`; two accounts, actual exchanged messages and private canaries, correct/wrong password, purpose token and field allowlists. |
| T15-AC05 | PASS locally | TC04/TC05/TC07: anonymous, wrong user/session, expired, ordinary-token and true >10 MiB rejection; `test_export_consistent_snapshot_during_external_write` uses a barrier and an independent PostgreSQL writer, with SQLite writer-reservation equivalent. |
| T15-AC06 | PASS locally | TC06: `test_restored_backup_resumes_pending_deletion` creates a SQLite backup, restores it to another isolated file, resumes the pending worker, and checks an unrelated active home remains. Retention boundaries documented. Full multi-service PostgreSQL restore rehearsal belongs to T27. |

All seven mapped test cases above ran; no external/live gate is claimed.

## Verification

Working directory was this T15 worktree, macOS 15.7.7 arm64, Python 3.12.9, Node 24.6.0. All fixture users, data and services were synthetic/disposable.

- `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t15-lifecycle-final'`: exit 0; 121 passed, 0 failed, 0 skipped. Disposable Docker PostgreSQL 16 and Elasticsearch 8.19.6, isolated database and schemas, removed by runner. Sanitized report: `.local/verification/T01/t15-lifecycle-final/report.json`. This collected the module before the later addition of the SQLite advert-scrubbing test and same-user/wrong-session assertion; the command below includes both.
- `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/pytest backend/tests/test_account_data.py backend/tests/test_accounts.py backend/tests/test_marketplace.py backend/tests/test_identity_review.py -q -o addopts=''`: exit 0; 35 passed, 0 failed, 10 skipped, 2 warnings. Skips are PostgreSQL variants, exercised without skips by the preceding service run. The warnings are Starlette httpx deprecation and an existing Pydantic serialization warning.
- Prior service runs `t15-lifecycle-01` (101 passed) and `t15-lifecycle-02` (114 passed) also exited 0 with no skips; additional tests were added between runs. The first targeted regression initially failed three tests because the shared SQLite test session had an existing writer transaction; the guard was corrected to reuse/upgrade that transaction and subsequent runs passed.
- The service profile includes T01's PostgreSQL fresh/upgrade/checksum tests; `test_sqlite_upgrade_preserves_existing_rows` verifies SQLite hook 009 idempotence and preservation. The initial and final run reports are local ignored artifacts, not shipped personal data.

Race ordering: stale request pauses after simulated authorization until cleanup commits, then attempts a real write route; a second test commits a guarded writer before cleanup completes. Snapshot test pauses after its first query, commits a deliberately independent PostgreSQL email-preference update, and verifies the earlier snapshot; SQLite instead verifies the writer reservation blocks that update. Failures use deterministic hooks/events, not timing sleeps.

## Reproduction, risks and recovery

Run the two verification commands above with the documented runtimes. Re-run after integrating T16, particularly both participants' cleanup/reply ordering, and retain T13 delivery-fencing and T10 identity tests. Independent privacy/data and transaction-lock review is mandatory. The size limit has no pagination/job fallback yet; oversized accounts receive the explicit 413. Old malformed allowlisted advert/search data returns 422 for operator remediation rather than an unsafe or silently truncated export. Real browser CORS and production multi-service backup/restore are not claimed.

Recovery: restore backups only into isolation, keep traffic and notification dispatch stopped, resume pending deletion jobs against restored auth and rentals stores, verify completion and then reopen traffic. Tombstones must survive future backups/migrations; re-registration must allocate a new ID. Rollback of application code must not discard tombstones or re-enable pre-fence writers. Imported market observations and limited audits remain as documented; no legal certification is implied.

No cloud deployment, push, provider account creation, real mail or live provider action occurred. No execution ledger was edited.

## Parent security and integration review

Accepted after reviewing purpose/audience/session token binding, all account write guards, privacy allowlists and identity/account/conversation lock order. T16 read/start/reply/block retain their tuple semantics and take the account guard before thread locks. The combined registry preserves 005/006/008/009/010 and prior hook checksums.

The parent bounded export input materialization further: SQL checks aggregate UTF-8 byte lengths, rows stream individually, and encoded output still has the 10 MiB cap. A multibyte legacy JSON regression rejects the payload before Python memory growth reaches 4 MiB on either engine. Cleanup locks conversation IDs in bounded batches and uses deletion subqueries instead of an unbounded Python ID list. The earlier combined run exposed a test barrier that did not recognize the new account advisory lock and a PostgreSQL fixture exceeding a VARCHAR limit; those tests were corrected without weakening production locks or size checks.

Independent final real-service profile `integrated-t15-final` passed **152 tests with zero failures or skips**. The earlier targeted local profile passed 45 tests with 20 explicit PostgreSQL skips; those variants are included in the final service profile. Export uses a second PostgreSQL connection for its repeatable-read snapshot while the first holds the per-account guard; pool capacity remains an operational constraint. No cloud deployment, actual provider message, real email or push occurred.
