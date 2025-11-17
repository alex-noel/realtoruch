# Q21 — Stable notification pagination

Status: IMPLEMENTED_LOCAL; strong cursor/ownership and private-state review pending. Base: 9c636cd0234ba7369759dec81f4a3f493fd86d19; branch codex/q21-inbox.

The endpoint adds an opaque keyset continuation and authoritative end indicator while retaining offset callers. The inbox preserves its loaded tail on head refresh, prevents duplicate page/read requests, retains data for retry, and fences asynchronous completions at account reset. A successful read changes only its own row. See `docs/contracts/notifications.md` for ordering and compatibility. No schema migration, new dependencies, notification creation or delivery changes.

| Criterion | Evidence |
| --- | --- |
| Q21-AC01 | SQLite and real PostgreSQL cursor fixture inserts newer and equal-timestamp rows between pages, verifies ID tie ordering, continuation, final page and owner isolation; client tests check head/tail merge, an exhausted inbox followed by a 40-item burst, sorted gap recovery, and a stale page response racing the restarted cursor. |
| Q21-AC02 | Controlled-response tests cover double load, failure preserving cursor and rows, retry and end-of-list. Desktop/mobile browser fault fixture verifies visible retry and retained rows. |
| Q21-AC03 | Controlled tests cover failed read, duplicate read, stale head response after a successful read, and delayed page/read across reset; backend tests reject another account's read and scope cursor requests. Browser test shows failed read remains actionable. |

Actual evidence date: 2026-11-17 15:40 CET. Python 3.12.9, Node 24.6.0; synthetic isolated fixtures only.

| Command | Result |
| --- | --- |
| `PYTHONPATH="$PWD/backend" .venv/bin/python -m pytest backend/tests/test_notification_cursors.py backend/tests/test_rental_journey.py -q` | 15 passed; exit 0. |
| `npm --prefix apps/mobile run test:unit -- tests/accountCollections.test.ts tests/session.test.ts` | 55 passed; exit 0. |
| `npm --prefix apps/mobile run typecheck` | exit 0. |
| `PYTHONPATH="$PWD/backend" make verify-services ARGS='--run-id q21-services-20261117'` | 241 passed, 0 failed or skipped; exit 0. The new cursor test ran on a disposable PostgreSQL schema. Sanitized report: ignored `.local/verification/T01/q21-services-20261117/report.json`. |
| `VERIFY_RUN_ID=q21-gap-20261117 npm --prefix apps/mobile run test:e2e -- notification-cursors.spec.ts` | 2 passed (desktop/mobile); exit 0. Synthetic screenshots and raw runner artifacts remain ignored under `.local/verification/T18/q21-gap-20261117`. |
| `git diff --check` | exit 0. |

Node 24 was placed first on PATH. Python commands used the shared read-only Python environment with `PYTHONPATH` set to this checkout's backend. The first focused browser invocation lacked the activated environment and failed before starting; the recorded successful run activated it. The backend service profile preceded the client-only burst-gap correction; the focused tests, typecheck and browser scenario were rerun afterward. The mobile screenshot was visually inspected. Required independent review remains outstanding; no external provider/device verification claimed.
