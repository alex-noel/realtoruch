# T16 — Message read cursors and inbox pagination

- Status: **VERIFIED** locally against SQLite and disposable PostgreSQL.
- Reviewed base: `87cfd3438b7dec064f2a7759fe8f585047d88ff9`.
- Implementation: `00e5615e0b8931fc0faf3504f4eefe2e36ec6ea7`, created with `python3 scripts/commit.py`. Its author and committer dates are both `2021-11-11T22:08:28+01:00`. This verification report is a separate documentation commit.
- Actual work and verification: **2026-11-11, Europe/Warsaw (CET)**. The initial service run was 22:06:15–22:07:19 CET; the final service run was 22:08:50–22:10:01 CET. The targeted reruns took place at approximately 22:08–22:09 CET.
- Outcome: The inbox can load more conversations without duplicates in a static dataset, and a client can acknowledge a displayed message without clearing an incoming message that arrives afterward.
- Approved scope expansion: Register the new test module in the existing T01 service profile.

## Changes and contract

- `backend/realtoruch/marketplace.py`: Adds inbox keyset pagination (default/max 50, descending update time and ID), keeps message-ID history cursors and chronological display order, accepts a precise read body and a legacy empty body, and returns 409 on conflicting reuse of a sender’s client message ID. An acknowledgement validates the message in the authorized thread and updates only a greater tuple. Each new send assigns a timestamp later than the previous message or existing read boundary, even when the wall clock ties or regresses. Sends leave both participants’ read state alone. PostgreSQL uses conversation row locks; SQLite reserves the writer before reading state. Starting a thread acquires the T10 shared identity gate before locking the advert.
- `backend/realtoruch/models.py`, `backend/realtoruch/migrations.py`, `infra/sql/010_message_read_cursors.sql`, `infra/sql/migrations.json`: Rentals 010 adds two nullable message ID columns and indexes for the inbox and history ordering. It preserves both original timestamps and all other data; a non-null legacy timestamp with a null ID still covers its entire timestamp. Previous PostgreSQL SQL files and SQLite callback bodies are unchanged. Auth schema is unchanged.
- `backend/tests/test_message_cursors.py`, `scripts/verify.py`: Exercises authenticated API behavior and migration upgrades in each dialect. The service profile runs both dialects, alongside the existing T01/T13 suites.
- [Message API contract](../contracts/messages.md): Records the exact v1 routes, response fields, cursor encoding, examples and errors for T17. Existing clients can omit query parameters or the read body; the inbox now returns a first page of up to 50 with a continuation cursor, and an empty body still acknowledges through the latest message. No frontend code changed.

## Acceptance evidence

All cases below passed against both SQLite and PostgreSQL in the final targeted run.

| AC | Status | Required case | Evidence |
| --- | --- | --- | --- |
| T16-AC01 | PASS | T16-TC01 | Fetch M1/M2, send M3 at the same wall clock, send an own reply after moving the fake clock backward, then acknowledge M2. M3 remains unread and the own reply does not clear incoming state. Legacy empty acknowledgement works independently for the renter. |
| T16-AC02 | PASS | T16-TC02 | Three messages share one timestamp; acknowledging M2 leaves M3 unread, acknowledging M1 or M2 leaves the watermark unchanged. A separate two-request barrier test pauses the M2 update after acquiring its write lock and runs M1 into the lock before releasing M2. Both return 200 and M2 remains the watermark. |
| T16-AC03 | PASS | T16-TC03 | Missing, malformed, same-account foreign-thread and other-account message IDs return 422; calls to a thread outside the actor’s account return 404. Persisted cursor and unread count remain unchanged. |
| T16-AC04 | PASS | T16-TC04 | 120 visible threads plus one unrelated thread; 130 messages plus an unrelated message. Large timestamp tie groups span page boundaries. Inbox pages contain 50/50/20 and history pages contain 50/50/30, in exact expected order with no duplicates or gaps. Invalid tokens, foreign history boundaries and limits outside 1–50 return 422. A well-formed cursor from another account does not authorize its rows. |
| T16-AC05 | PASS | T16-TC05, T16-TC06 | Both start and reply replay the original for the same normalized body; a different body returns 409 and leaves one thread and the original two messages. Unverified actors cannot send, outsiders receive 404, a new reply to a blocked thread returns 403 and only the blocking user can unblock. A separate test verifies the 20-per-minute limit across threads and that an identical replay is free. |
| T16-AC06 | PASS | T16-TC06 | Engine query event counter records exactly **2 rental SELECTs** at both page sizes **1 and 50**, and **1** for an empty inbox. Title is projected in the page query, unread counts are grouped in the second query, and there is no per-thread profile lookup. The counter excludes authentication queries in the separate identity database. |

Fresh fixtures use the PostgreSQL registry and SQLite metadata plus local hooks. Both tracked upgrade tests seed an old blocked conversation with an existing read timestamp and tied message, apply 010 twice, verify unchanged existing values and prior checksums, and prove that the old inclusive read boundary remains in effect.

## Verification

Commands ran from `/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t16` with the repository’s Python 3.12.9 virtual environment and `PYTHONPATH=backend` for direct runs. A temporary `.venv` symlink exposed the existing environment for the exact Make invocation and was removed at handoff. SQLite was 3.50.2, PostgreSQL was 16.15 from `postgres:16-alpine`, Elasticsearch was 8.19.6, and the T01 runner used Node 24.6.0 on macOS arm64.

| Command | Exit / results | Evidence |
| --- | --- | --- |
| `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_marketplace.py -q` | 0; 5 passed, 0 failed, 0 skipped. | Initial marketplace regression check before adding the new test module. |
| `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_message_cursors.py backend/tests/test_marketplace.py -q -ra` | 0; 14 passed, 0 failed, 9 PostgreSQL skips because no service URL was set. | `.local/verification/T16/t16-20261111/targeted-sqlite.txt` |
| `PYTHONPATH=backend .venv/bin/pytest backend/tests/test_message_cursors.py backend/tests/test_marketplace.py -q -ra -o addopts=''` | 0; 14 passed, 0 failed, 9 PostgreSQL skips because no service URL was set. | `.local/verification/T16/t16-20261111/targeted-sqlite-final.txt` |
| `TEST_POSTGRES_URL="postgresql+psycopg://rentals:synthetic@127.0.0.1:$pg_port/t16" PYTHONPATH=backend .venv/bin/pytest backend/tests/test_message_cursors.py backend/tests/test_marketplace.py -q -ra -o addopts=''` | 0; **23 passed, 0 failed, 0 skipped**, 7.10 seconds. Both the SQLite and PostgreSQL parameter sets ran. | `.local/verification/T16/t16-20261111/targeted-postgres-final.txt`; the synthetic URL points to the loopback port returned by `docker port realtoruch-t16-targeted-20261111 5432/tcp` for the owned disposable container. |
| `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/verify.py services --run-id t16-service-first-20261111` | 0; 108 passed, 0 failed, 0 skipped. Ran before the final helper extraction and test cleanup. | `.local/verification/T01/t16-service-first-20261111/report.json` |
| `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t16-service-final-20261111'` | 0; **108 passed, 0 failed, 0 skipped**. This used committed implementation `00e5615` with no tracked changes. | `.local/verification/T01/t16-service-final-20261111/report.json` |
| `PYTHONPATH=backend .venv/bin/python -m realtoruch.migrations validate`; `.venv/bin/python -m ruff check --select E9,F63,F7,F82 backend/realtoruch/marketplace.py backend/realtoruch/models.py backend/realtoruch/migrations.py backend/tests/test_message_cursors.py scripts/verify.py`; `git diff --check` and `git diff --cached --check` | All exit 0. | Registry, Python error checks and whitespace checks. |

Targeted pytest emitted one existing Starlette TestClient deprecation warning. No test failed or needed a corrective retry. The overlapping acknowledgement test uses named events and PostgreSQL `lock_timeout=5000`; it does not use timing sleeps to order the requests. The arrival test uses two explicitly controlled wall clock values.

## Reproduction, recovery and integration

Fetch a thread as one participant, send a new message as the other participant, then acknowledge the last displayed incoming ID from the fetch. The new incoming message remains unread. Resend the same client ID with the original text to get the original message; changing the text returns 409.

Apply migrations through T01 with the complete reviewed registry before starting the new backend. Back up and verify the database beforehand. Keep the additive columns and migration history intact on an application rollback; the older backend restores the old timestamp semantics. Avoid running old and new message writer versions together, since the older version does not maintain paired cursor fields or assign monotonically ordered message timestamps. Use a verified backup or reviewed forward fix for failed migrations. Worktree verification databases are disposable and are not upgrade bases for another task’s partial registry.

T17 can use the documented precise body and pagination immediately. Inbox activity can move a conversation ahead of an existing page cursor; refresh to see it. For T15, insert `account_data.guard_account_write(session, user_id)` in `start_conversation` after `lock_identity(session, shared=True)` and before `_begin_conversation_write` and the advert query. In `reply`, `read_conversation` and `block_conversation`, insert it before `conversation_for(..., write=True)`. Preserve the sender rate lock after the conversation row lock. T15 and the integrator will run their combined account-closure checks after merging the guard. Integrate other tasks’ reserved migration entries in sorted order, and preserve their service test registrations.

No external blocker for T16. Only synthetic accounts and local resources were used. No cloud resources, live provider traffic, real email, frontend publication or Git push.

## Parent integration acceptance

The parent reviewed cursor canonicalization, participant filters, monotonic read tuples, idempotent retries and conversation lock ordering. The combined migration registry retains rentals005/006/008/010 and immutable older hooks. Independent profile `integrated-t16-review` passed123tests withzero skips; whole offline profile `integrated-midpoint-offline-3` passed297tests with79 explicit optional-service skips, plus TypeScript and18 frontend unit tests. Six SQLite/Helm cases also passed separately during T26 review. T15 must add its account guard before the four conversation write sites; that integration remains pending.
