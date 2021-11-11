# Local backup and account-erasure recovery

The T27 drill creates two synthetic accounts and a separate rentals/auth pair, takes a quiesced backup, and restores both databases to new destinations. It checks the restored data through the application, runs the pending workers, and tests which resources recovery can remove. It never connects to a developer catalog or uses real email or provider credentials.

## Run the drill

From the repository root, use the locked Python 3.12 development environment. Choose a fresh run ID each time (lowercase letters, digits, and hyphens; at most 32 characters).

```sh
.venv/bin/python scripts/backup_check.py --help
.venv/bin/python scripts/backup_check.py --isolated sqlite-drill-01
.venv/bin/python scripts/postgres_backup_check.py --help
.venv/bin/python scripts/postgres_backup_check.py --isolated postgres-drill-01
```

SQLite needs no Docker service. PostgreSQL uses the already available `postgres:16-alpine` image with its bundled `pg_dump` and `pg_restore`, a local Docker socket, a fresh labelled container, and an automatically allocated loopback port. The container's data directory is disposable. On Apple Silicon, use a cached native ARM64 image when possible; the report records the actual server architecture. The drill creates a dedicated nonsuperuser database owner and checks the database, migration ledger and table ownership before exercising routes. These local owners do not model the deployed IAM grants.

The application issues access and refresh tokens for `example.test` accounts, and the workers use the actual file delivery mode. Seed verification and opt-in emails go to `seed-mail/`; replay writes a separate `restored-mail/` directory. Standalone drills exercise the real SQL search outbox and indexer with an in-process bulk transport. For a check against real Elasticsearch as well, use the repository service profile (it provides a labelled loopback Elasticsearch and an isolated per-run search index):

```sh
.venv/bin/python scripts/verify.py services --run-id restore-regression-01
```

The older `--catalog` and `--container` checks remain available for explicitly selected inputs. They have different assumptions and evidence; use `--isolated` for this drill. Running either script without a profile fails instead of choosing an existing catalog or container.

## Verify the backup and the restored state

Each private `.local/verification/T27/<run-id>/` directory has an `ownership.json`, a `manifest.json`, two SQLite backups or two custom-format PostgreSQL dumps, and a `report.json` after success. The manifest records the source Git revision and dirty flag, engines, migration versions and checksums, row counts, artifact sizes and SHA-256 digests, source and target identifiers, and UTC quiescence and backup times. PostgreSQL also checks sorted logical table digests. The SQLite checks use its backup API and verify integrity and foreign keys for each artifact and destination. The PostgreSQL check reads both full archives before creating a destination and restores each database in a transaction without replaying source grants. The drill rejects inconsistent metadata, mismatched engine or schema versions, or invalid artifacts.

The restored API must show the same canonical result through the old listing ID, the saved delisted home outside public discovery, changed rents and a monthly history sample, and one unread private conversation for its authorized participant. It must also keep the active account's saved search, seen state and unread rental notification. The deleted account's stale password, access token and refresh token must fail before the queued job runs. The resumed erasure closes a deterministic window in which a request already passed authorization but had not reached its write guard; that write fails against the restored closure fence. The deleted account's private rows and conversation disappear. The retained minimum includes the opaque closure ID, terminal auth job metadata during its short retention window, and scrubbed inactive public listing history for the withdrawn advert. Imported history and the active account's data remain available.

Erasure runs before any restored alerts are delivered. Two passes through the indexer, file mail and erasure workers must finish with one logical rental message, an empty pending index queue, and no second delivery or erasure job. Cleanup endpoint replay is safe. Stable message IDs do not guarantee exactly-once SMTP delivery, particularly after external acceptance and before acknowledgement. A recovery from an older backup can also reintroduce jobs that were already acknowledged after that backup; reconcile with delivery records before enabling a real transport.

## Handle an interrupted run

Stop the active drill before inspecting or cleaning the run. Keep the ownership and backup manifests together. Use the matching command and exact run ID:

```sh
.venv/bin/python scripts/backup_check.py --cleanup sqlite-drill-01
.venv/bin/python scripts/postgres_backup_check.py --cleanup postgres-drill-01
```

Cleanup uses the original run lock and ownership record. SQLite requires the private directory marker, recognized files and recorded file identities. PostgreSQL requires the exact container ID and labels and checks target database names, owner role, comments and recorded OIDs before removal. It checks for unknown databases before disposing of its private container. An occupied target or an ownership mismatch stops cleanup; investigate the resource rather than changing the manifest or forcing a drop. If the process died between creating a resource and recording its identity, it may need reviewed manual disposal. A still-running PostgreSQL restore can prevent cleanup; let it exit and retry. The cleanup command keeps evidence and dumps. Start another drill with a fresh run ID after cleanup.

The automated negatives cover corrupt and truncated artifacts even when their file hashes are recomputed, incompatible metadata, a destination that cannot be written, and interruption after the first database. The harness checks an independent sentinel database on both engines and refuses to delete an unowned collision at an expected restore name.

## Recovery point and access limits

Stop or drain every writer before taking the paired snapshots: API, auth, collectors, alerts, indexers and account jobs. In the drill the final delete request commits, application clients and SQL pools close, and no writes occur during either backup. SQLite's online backup and PostgreSQL's logical snapshot are consistent per database. They are sequential across two databases and supply no atomic cross-database snapshot if a writer remains active. In particular, a mismatched auth/rentals pair can lose a deletion request or revive a private record; never mix runs. This exercise covers a backup taken after auth accepted deletion and before rentals cleanup. A backup from before deletion needs a separately reconciled record of deletions accepted since that recovery point before reconnecting the application.

In this fixture the paired recovery point is the recorded quiescence time; zero committed fixture writes through that point were lost. Every later write would be outside the recovery point. Backup elapsed time includes inventory and dump creation; restore elapsed time includes validation and inventory. Application recovery time also includes the restored API and worker checks. These local timings cover the tiny fixture and do not estimate production RPO or RTO. The drill does not exercise cloud restore, production roles or production cutover.

Measured on 2026-11-11 UTC from clean revision `66a6546`, on macOS 15.7.7 ARM64 with Python 3.12.9. Each run used two accounts, two owned adverts, five source listings, nine observations and one private message. PostgreSQL used the cached x86_64 PostgreSQL 16.15 image; SQLite was 3.50.2.

| Run | Quiescent recovery point (UTC) | Backup | Pair restore | Restore plus application and worker checks |
| --- | --- | ---: | ---: | ---: |
| `t27-final-sqlite` | `22:18:11.204` | 0.004 s | 0.007 s | 0.231 s |
| `t27-final-postgres` | `22:18:15.559` | 1.003 s | 1.617 s | 2.223 s |

Raw SQL backups, manifests, source files and `.eml` previews stay in the ignored run directory. Restrict access to the local operator, use encrypted storage for operational backups, and set and enforce a retention period for copies, logs, and mail previews. The drill uses filesystem permissions; it does not encrypt files. Keep raw files out of Git, shared logs, and ordinary handoffs. Rebuild the derived search projection from restored SQL into a new index before a real cutover; an existing search index can contain revisions newer than the SQL recovery point.
