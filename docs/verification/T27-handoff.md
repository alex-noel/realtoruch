# T27 handoff — paired backup restore and erasure recovery

## Identity and outcome

- Task: T27, core.
- Status: VERIFIED locally after independent integration review; final combined-candidate rerun remains in T32.
- Base revision: `994b928a3e2376bdcb477cd3c4fe6b3806808061` (reviewed T11/T15/T16 state).
- Implementation: `66a654665a7eed5972312b4d356b849d3c5af934`; author and committer dates both `2021-11-11T23:17:57+01:00`, set by `python3 scripts/commit.py`. This handoff and measured timings are in a separate evidence commit.
- Work and verification: 2026-11-11 Europe/Warsaw (CET, UTC+01:00); timestamps below are UTC.
- Outcome: Both database engines restore an isolated synthetic rental and auth pair, preserve the public and private API state, and resume an accepted erasure without resurrecting the account's data.
- Approved scope extension: add the new restore test module to the existing `scripts/verify.py services` selection. Keep T28's independent `test_infra_contract.py` selection on integration.

## Changed files and contracts

- `scripts/backup_check.py`, `scripts/postgres_backup_check.py`: require an explicit profile. `--isolated RUN_ID` runs the synthetic drill, and `--cleanup RUN_ID` cleans a verified owned destination. Explicit legacy `--catalog` and `--container` checks remain available.
- `scripts/restore_manifest.py`: paired backup and restore, private atomic JSON records, validated SHA-256 and version ledgers, SQLite integrity and PostgreSQL logical content verification, collision refusal and ownership-checked cleanup.
- `backend/tests/test_restore_contract.py`: two-engine route/worker and failure drill. The service profile adds real Elasticsearch; standalone uses the SQL indexer with an in-process bulk transport.
- `scripts/verify.py`: add the focused restore module to real-service regression coverage.
- `docs/operations/backup-restore.md`: safe commands, measured local recovery, retained records, access and retention limits, and interruption handling.
- No migration, registry, API, DTO, existing app setting or cloud policy change. SQLite ledgers: rentals `001,005,006,008,009,010`; auth `005`. PostgreSQL ledgers: rentals `001,002,003,004,005,006,008,009,010`; auth `001,004,005`. Version `007` remains unused. PostgreSQL dump clients match PostgreSQL 16.15; the drill restores under its own nonsuperuser owner and verifies table ownership and checksums before touching routes.

## Acceptance evidence

| AC ID | Result | Test cases | Command/run | Evidence |
| --- | --- | --- | --- | --- |
| T27-AC01 | PASS | TC01, TC02 | `t27-final-sqlite`, `t27-final-postgres` | Each validated a manifest against two source/target namespaces and both migration ledgers before app checks. SQLite passed integrity/FK checks; PostgreSQL matched the logical contents and owner. |
| T27-AC02 | PASS | TC01, TC02 | Both final drills | Old listing route and canonical detail agree; observed monthly price sample and listing changes match; the delisted favorite is saved and excluded from discovery; active account receives the unread thread and sees only its own state. |
| T27-AC03 | PASS | TC03 | Both final drills | Auth rejects old password, access token and refresh token. Restored pending deletion completes. A barrier releases a previously authorized write only after cleanup; the actual favorite route returns 401. Private records disappear; the active account and opaque closure/tombstone remain. |
| T27-AC04 | PASS | TC03, TC04 | Both final drills and `t27-service-regression` | Five pending index entries acknowledge once, one logical file-only rental alert, one finished erasure, and zero on repeated drains. The cleanup endpoint also succeeds on explicit replay. |
| T27-AC05 | PASS | TC05, TC06 | Both final drills | Nine distinct failure/preservation scenarios per engine; corrupted archives with recomputed digests and a deliberate stop after the first restore return failure. Both independent database sentinels and unowned target collisions remain intact. |
| T27-AC06 | PASS | TC06 | Both final drills | Checked timing and quiescence fields and rehearsed ownership cleanup; runbook reports exact local timings, snapshot limits, retention and safe commands. |

| Test case | Result | Specific check |
| --- | --- | --- |
| T27-TC01 | PASS | SQLite restores separately named rentals/auth files and runs the actual API against them without repair migrations at startup. |
| T27-TC02 | PASS | Real PostgreSQL 16.15 uses `pg_dump`/`pg_restore`, actual registry/checksums, `t27_app` owner and restored API sessions. |
| T27-TC03 | PASS | The seeded delete returns 202 before backup, restores as pending with zero attempts, finishes exactly once, and rejects the paused writer after its fence. |
| T27-TC04 | PASS | Stable delivery ID and file digest after two drains, the exact same one unread notification, five index acks then zero; no SMTP. |
| T27-TC05 | PASS | Wrong digest, format, engine version and schema; corrupt and truncated archives; blocked destination. Each fails and leaves the independent sentinel intact. |
| T27-TC06 | PASS | Interrupted after the rentals restore, refused an unowned collision, reopened the original ownership record, cleaned only its target and repeated the restore. Local elapsed times and UTC snapshot limits recorded. |

## Verification

Commands ran in `/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t27`. `T27_PYTHON=/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python` below denotes the exact shared Python 3.12.9 interpreter used. Host: macOS 15.7.7 ARM64, Docker 29.8.0, SQLite 3.50.2, cached PostgreSQL 16.15 running as x86_64 and Elasticsearch 8.19.6 on ARM64. Node 24.6.0 supplied the service runner's version gate.

| Invocation | Exit | Pass / fail / skip | Evidence |
| --- | ---: | --- | --- |
| `$T27_PYTHON scripts/backup_check.py --help` and `$T27_PYTHON scripts/postgres_backup_check.py --help` | 0 each | n/a | Both advertise explicit isolated and cleanup profiles. |
| `$T27_PYTHON scripts/backup_check.py --isolated t27-final-sqlite` | 0 | 1 / 0 / 0 | `.local/verification/T27/t27-final-sqlite/report.json` |
| `$T27_PYTHON scripts/postgres_backup_check.py --isolated t27-final-postgres` | 0 | 1 / 0 / 0 | `.local/verification/T27/t27-final-postgres/report.json` |
| `$T27_PYTHON scripts/backup_check.py --cleanup t27-final-sqlite` and `$T27_PYTHON scripts/postgres_backup_check.py --cleanup t27-final-postgres` | 0 each | n/a | Repeated cleanup was a no-op after both verified targets had already been removed. |
| `env -u DOCKER_DEFAULT_PLATFORM PATH="/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH" "$T27_PYTHON" scripts/verify.py services --run-id t27-service-regression` | 0 | 190 / 0 / 0 | `.local/verification/T01/t27-service-regression/report.json`; 2026-11-11 `22:18:10.290`–`22:19:57.799` UTC |
| `/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/ruff check --target-version py310 scripts/restore_manifest.py backend/tests/test_restore_contract.py`; `$T27_PYTHON -m compileall -q scripts/restore_manifest.py scripts/backup_check.py scripts/postgres_backup_check.py backend/tests/test_restore_contract.py`; `git diff --check` | 0 each | n/a | Lint, compile and diff checks passed. |

`sqlite-development-01` initially failed 0/1/0 because the synthetic advert omitted required coordinates and had a short description. The fixture was corrected; `sqlite-development-02`, `sqlite-development-03`, and `pg-development-01` then passed 1/0/0 each before the clean implementation commit. The standalone selected engine has one test; the other engine parameter is deselected. The service profile exercises both engines and the existing real PostgreSQL account lifecycle tests. Its two private T27 reports (`test-d17fef590d484bcc`, `test-b182a98c81684320`) explicitly record `real-loopback-elasticsearch`.

Each manifest recorded two users, two owned adverts, five listing rows (including the merged tombstone), one canonical alias, five source rows, nine observations, two seen rows, two favorites, two saved searches, one unread thread/message, one rental notification, five pending index jobs, three mail rows (two terminal confirmations, one pending rental alert), and one pending deletion among three auth job rows. The concurrency check used explicit `Event` barriers; the interruption check stopped at the first validated database, reopened `ownership.json`, and cleaned before retrying. Both repeated worker passes returned zero new work. There were zero committed fixture writes lost at each quiescent recovery point.

| Local run | Quiesced UTC | Backup elapsed | Pair restore elapsed | Restore plus application checks | Verified UTC |
| --- | --- | ---: | ---: | ---: | --- |
| SQLite | `22:18:11.204` | 0.004 s | 0.007 s | 0.231 s | `22:18:11.476` |
| PostgreSQL | `22:18:15.559` | 1.003 s | 1.617 s | 2.223 s | `22:18:25.078` |

## Reproduction and review

Use the isolated commands above with new run IDs. The runbook explains how to use the matching cleanup command, which leaves private dump evidence in place. PostgreSQL cleanup checks the exact owner-labelled container and matching database OIDs/comments; SQLite cleanup checks the run directory, marker and file identities. Leave unrecognized destinations untouched. Nothing applies startup DDL to a restored database, so the API test cannot hide a bad restore by repairing it.

The paired backup is coherent only because every writer is stopped through both sequential backups. A backup from before deletion acceptance requires separate deletion reconciliation; the drill does not make a production RPO/RTO guarantee. A production search projection should be rebuilt into a new index. This drill does not model actual host power loss, external mail acceptance, cloud restore, deployed IAM grants or cutover. For rollback, revert the harness changes; no application schema or settings need rollback. Independent review should focus on ownership checks, restore failure boundaries and the accepted-deletion snapshot order.

## Blockers and next action

No external blocker for T27. Only disposable loopback services, synthetic `.test` accounts and the local file sink were used. No live databases, cloud resources, real emails, portal/provider requests, push, deploy, or publication. Raw dumps, mail previews, credentials and manifest identifiers remain ignored and private.

## Integrator review

The parent independently reviewed the quiescent snapshot order, schema/content checks, immutable container and database identity checks, SQLite file identities, refusal before unrelated cleanup, and resumed erasure/application assertions. Integration retains both the T28 permission test and T27 restore test in the service profile. No application behavior or migration changed during integration. The worker's clean-revision standalone runs and 190-test service run supply the execution evidence above; the parent deliberately deferred another combined run until T32 while T25's timed capacity comparison was active. This avoids treating a repeated test under competing load as a performance measurement.
