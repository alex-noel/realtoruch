# Local operational metrics and incident runbooks

Scrape `GET /metrics` on the REST and auth services over a private connection. Both require `X-Internal-Key` from the approved secret store; keep the header out of shell history, verbose HTTP output, dashboards and incident notes. REST reads the rentals database, and auth reads the auth database. The public ingress serves only the listed public paths; it has no rule for `/metrics` or `/internal/*`. Public `/healthz` and REST `/readyz` return coarse status only. Private diagnostic access requires both the private route and the key; keep any future scraper off public ingress.

`/healthz` indicates process responsiveness. REST `/readyz` checks that it can query the required SQL discovery tables, even if Elasticsearch is unreachable and search falls back to SQL. Auth `/readyz` queries its identity tables; the auth HTTP service can queue work while a transport is down. The internal worker checks are:

```sh
PYTHONPATH=backend .venv/bin/python -m realtoruch.worker alerts --check-ready
PYTHONPATH=backend .venv/bin/python -m realtoruch.auth_jobs --check-ready
```

Run them in the corresponding worker environment. Exit 0 means required SQL reads and local mail configuration passed; the auth worker also checks the rental cleanup service's readiness. Exit 1 logs only `database`, `cleanup_api` or `mail_config`. These probes make no state changes, do not contact an SMTP server, and do not prove provider acceptance, database write privileges or cleanup credentials. Use queue ages and outcomes to detect failures that a read-only probe cannot see. Auth erasure does not depend on mail being enabled. T28 owns probe and scraper configuration; do not deploy these settings from this task.

## Metric contract

All names have the `realtoruch_` prefix. All series are gauges sampled from durable SQL, not cumulative counters or counts to sum across replicas. Deduplicate replicas of the same database (for example, use the maximum among successful scrapes). Values are current at scrape time and can decrease when work finishes or is retained out. Only these application labels are emitted:

| Name suffix | Unit | Labels | Meaning |
| --- | --- | --- | --- |
| `metrics_collection_success` | 0/1 | None | 0 means the snapshot failed or a scrape was already in progress. HTTP 200 still carries this gauge; queue and source samples are omitted on failure. |
| `queue_depth` | Rows | `queue`, `state` | Rows by operational state. Completed work is excluded. |
| `queue_oldest_eligible_age_seconds` | Seconds | `queue` | Time since the earliest ready row became due at its current attempt, or 0 when none is ready. Use ready depth to distinguish empty from just due. |
| `queue_last_error_depth` | Rows | `queue` | Unfinished/terminal rows with a recorded last-attempt failure marker. No error text or status value is returned. |
| `outbox_pending` | Rows | None | Compatible total of all undelivered search outbox rows, including held and future rows. |
| `auth_mail_enabled` | 0/1 | None | Auth mail is configured to run. The auth service and worker must use the same mail-mode setting. |
| `collection_success_known` | 0/1 | `provider` | 0 means no successful SQL collection is recorded, including a source without a state row. |
| `collection_last_success_age_seconds` | Seconds | `provider` | Time since the last recorded success; omitted if unknown. |
| `collection_consecutive_failures` | Attempts | `provider` | Current consecutive failures in source poll state. |
| `collection_backoff_seconds` | Seconds | `provider` | Time remaining on the persisted retry delay (0 when due). |
| `collection_lease_expired` | 0/1 | `provider` | A persisted lease token has an expiry in the past. It can be reclaimed by the normal fenced scheduler. |
| `collection_runs_24h` | Attempts | `provider`, `state` | Runs started in the past 24 hours by stored state. An abandoned run can still be recorded as running; check the separate lease signal. |

Allowed queues: REST `search_outbox`, `rental_email` (confirmation and rental notification), `push` (including receipt reconciliation); auth `auth_mail` (verification/reset), `account_erasure`. Queue states are `ready`, `leased`, `deferred`, `failed`, `cancelled`. A terminal row is never ready; an active lease takes precedence over scheduling. An expired delivery lease is claimable if its current due time has arrived. A worker can still cancel a queue-eligible row after validating current listing/account state. Search outbox has no scheduling deadline: all pending rows except held 400/413 items are ready, even if clock skew gives them a future creation timestamp. Creation time controls ordering and age; negative ages clamp to zero. Held 400/413 rows report as `failed`. Auth mail is deferred while disabled. Erasure age is current overdue age; retries change the next due time, so inspect retry/error depth too.

Provider labels are `gratka`, `morizon`, `olx`, `otodom`. New provider names require review before adding a series. Collection run states are `running`, `succeeded`, `partial`, `failed`, `interrupted`, `other`. Worker logs use `other` for unrecognized sources and include counts for 403/429, but omit URL/hash, city, tokens, listing/job/account IDs, transport errors and reports. SQL collection metrics describe the local SQL scheduler; the cloud collector path does not populate this lease history.

The query returns aggregates only, uses existing due/state and collection time indexes where the planner selects them, and runs in a separate transaction with a 250 ms PostgreSQL statement timeout. SQLite diagnostics set a temporary busy timeout and query deadline. This budget bounds the query, excluding connection acquisition and network transit. Start with a 60 s private scrape interval and one scrape per service instance at a time. Investigate repeated collection failure before interpreting absent series.

Initial investigation thresholds: ready indexing age >300 s, ready email age >900 s (when enabled), ready erasure age >3,600 s. Also investigate a held index row, repeated database scrape failures, an expired collection lease across two scheduled checks, or no recorded source success after two expected enabled runs. A healthy empty queue may be normal. Calibrate these starting thresholds with T07 source timing and T25 load results; they do not state an SLA.

## Diagnose without private payloads

Run commands against the named database using a trusted, read-only `psql` connection (service file or preconfigured environment, never inline credentials). Use `psql -X -v ON_ERROR_STOP=1`; start each diagnostic with `BEGIN READ ONLY; SET LOCAL statement_timeout = '2s';` and end with `ROLLBACK;`. PostgreSQL timestamps below are compared in UTC. The following queries return states, counts and times; do not inspect full rows, capture URLs, tokens or recipient addresses.

### 1. Source returns 403 or 429

On rentals SQL:

```sql
SELECT r.source, err->>'http_status' AS code, count(*) AS failures
FROM collection_runs AS r
CROSS JOIN LATERAL json_array_elements(r.report->'errors') AS e(err)
WHERE r.source IN ('gratka','morizon','olx','otodom')
  AND r.started_at >= timezone('UTC', now()) - interval '24 hours'
  AND err->>'http_status' IN ('403','429')
GROUP BY r.source, err->>'http_status'
ORDER BY r.source, code;
```

Compare `collection_backoff_seconds`, `collection_success_known`, and structured `collection_report` counts. A 403 means the source refused access; verify the approved source configuration before permitting another scheduled attempt. A 429 means slow down: honor any provider retry window and the persisted backoff; reduce pages and concurrency before the next scheduled attempt. Neither response proves removal. Leave listing state alone. Escalate to the source owner if 403 persists, 429 returns after an approved backoff, or a challenge replaces the expected response. Do not bypass access controls or force a replay.

### 2. Collection lease expired

On rentals SQL:

```sql
SELECT source, lease_until, retry_after, failures
FROM source_poll_state
WHERE source IN ('gratka','morizon','olx','otodom')
  AND lease_id IS NOT NULL AND lease_until < timezone('UTC', now())
ORDER BY lease_until;
```

A row here and `collection_lease_expired=1` mean the lease has passed its deadline. Check that SQL is ready and the worker's last lifecycle outcome was interrupted or stopped. Wait for the later of lease expiry and `retry_after`, then let the ordinary scheduler reclaim the source. Never clear a token manually or allow an old worker to acknowledge. Escalate if the next permitted scheduled run cannot claim or if renewal repeatedly fails; check worker SQL connectivity and clock drift.

### 3. Index revision does not converge

On rentals SQL:

```sql
SELECT CASE WHEN o.last_index_status IN (400,413) THEN 'held' ELSE 'eligible' END AS state,
       count(*) AS rows, min(o.created_at) AS oldest,
       max(s.revision) AS highest_waiting_revision
FROM outbox AS o
JOIN search_revisions AS s ON s.listing_id = o.listing_id
WHERE o.delivered_at IS NULL
GROUP BY 1 ORDER BY 1;
```

Check private search readiness and `index_cycle` acknowledgements. In an isolated ES fixture, query the active alias with a known synthetic ID and `?_source=false`; compare the returned `_version` to that fixture's SQL `search_revisions.revision`. An older ES revision with an eligible SQL row is normal during catch-up. Let the normal worker resume bounded batches after ES is healthy. For a held mapping or oversized document (400/413), correct the producer/mapping before reviewing a bounded reindex or the T08 alias rebuild procedure. A newer ES revision must never be overwritten by an older one. Escalate if eligible age keeps rising after healthy search returns, any held work persists, or an acknowledged row leaves a stale revision. Keep REST SQL fallback available and do not reset version counters or delete the active alias.

### 4. Rental email has not arrived

On rentals SQL:

```sql
SELECT status, count(*) AS rows, min(next_attempt_at) AS earliest_due,
       count(*) FILTER (WHERE lease_until >= timezone('UTC', now())) AS leased,
       count(*) FILTER (WHERE last_error IS NOT NULL) AS recorded_errors
FROM email_deliveries
WHERE status IN ('pending','retry','failed','cancelled')
GROUP BY status ORDER BY status;
```

Check delivery readiness, then compare ready age, leases and terminal outcomes. A cancelled item may have become invalid because the listing changed, the recipient opted out, or the alert was already read. Do not reopen it. A retry with a future due time is waiting for backoff. Let the fenced worker retry eligible work once transport is ready; confirm behavior using the synthetic file transport. Check only the existence/count of preview files in that private fixture directory, not their contents. A successful SMTP handoff followed by lost acknowledgement can produce a duplicate physical delivery despite the stable Message-ID. Escalate rising eligible age after recovery, terminal failures, or an ambiguous handoff. Do not bulk-reset status or trigger test messages to real recipients.

### 5. Account erasure is stalled

On auth SQL:

```sql
SELECT j.status, count(*) AS rows, min(j.next_attempt_at) AS earliest_due,
       count(*) FILTER (WHERE j.lease_until >= timezone('UTC', now())) AS leased,
       count(*) FILTER (WHERE j.last_error IS NOT NULL) AS recorded_errors,
       count(*) FILTER (WHERE u.deleted_at IS NOT NULL) AS closed_accounts
FROM auth_jobs AS j LEFT JOIN users AS u ON u.id = j.user_id
WHERE j.kind = 'delete' AND j.status IN ('pending','retry','failed','cancelled')
GROUP BY j.status ORDER BY j.status;
```

Check auth-worker readiness, rental API reachability, and authorized cleanup routing. Compare ready age and retry/error depth with logs for `queue=account_erasure`. Erasure retries even with mail disabled. Wait for backoff and any valid lease to pass; resume the regular bounded worker after both databases and the private cleanup path are healthy. Never recreate an account or clear a fence to retry. Escalate if retries persist after the cleanup path recovers, if the account is unexpectedly active, or if erasure is marked done but protected data is still reachable in a synthetic verification.

### 6. Verify a restore before resuming workers

Use a disposable PostgreSQL container labelled `realtoruch.verification=true`, with both schemas initialized and seeded only with synthetic data. Keep writers paused and transports disabled or pointed at a private local file directory. On each database, check the migration versions recorded for that database:

```sql
SELECT version FROM realtoruch_migrations ORDER BY version;
```

Rehearse the logical dump and restore into fresh databases:

```sh
make postgres-backup-check ARGS="--container ${OWNED_CONTAINER:?set the owned test container} --user rentals --databases rentals auth"
```

The verifier compares row counts and logical content digests; keep the dumps and detailed inventory private. Check the restored pending erasure and index queues with the queries above. Verify migration compatibility, role permissions, and recovery-point limitations before allowing an isolated worker to resume; repeat cleanup only for known synthetic pending jobs, with mail still disabled or in file mode. Keep production writers and external transports disconnected throughout the rehearsal. Stop and escalate version mismatches, incomplete/corrupt dumps, digest mismatches, cross-database snapshot inconsistencies, or any restored account that was previously erased. T27 owns the full recovery rehearsal, including restored erasure fences.
