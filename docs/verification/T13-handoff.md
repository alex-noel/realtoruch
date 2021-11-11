# T13 delivery fencing handoff

## Identity and outcome

- Task: T13; status: IMPLEMENTED_LOCAL, pending mandatory independent concurrency/security review and integrated acceptance.
- Reviewed dependency base: `a74ca26adc20e955527f007fee272a616d2ceaae`; implementation commit: `5d744ee` (created with `python3 scripts/commit.py`). This handoff is committed separately with the same helper.
- Actual verification: 2026-11-11, Europe/Warsaw (UTC+01:00); report timestamps are real, not Git dates.
- Per-attempt leases fence stale workers, invalidation cancels unsent work durably, retries are bounded for mail and unbounded for erasure, and accepted Expo tickets retain receipt tracking.
- Integrator approved narrow expansion to `api.py`, `ingest.py`, the two existing registry-count assertions in `test_service_integration.py`, and `scripts/verify.py` to execute T13 service tests.

## Changed files and contracts

- `delivery_claims.py` implements atomic due-row UPDATE/RETURNING claims, unique tokens, 60-second leases, ownership-locked completion and scoped cancellation. PostgreSQL uses `FOR UPDATE SKIP LOCKED`; SQLite uses an atomic conditional write. Related eligibility is checked in the claim transaction before I/O and rechecked at completion. Completion locks the delivery via a conditional write; related reads deliberately do not acquire row locks, avoiding delivery-versus-listing/favorite lock inversion. Cancellation updates take email then push delivery locks; T08's later search-revision/outbox locks require integrated lock-order review.
- `email_alerts.py`, `push.py`, and `auth_jobs.py` use fenced claim/completion, handle missing or invalidated records, limit mail/push sends to eight attempts, preserve ticket receipt reconciliation, and emit only bounded status/attempt diagnostics. SMTP/push timeout is 10 seconds, erasure HTTP timeout 20 seconds, and retries back off exponentially up to one hour. Disabled identity mail is excluded from claim selection so erasure can run.
- `api.py` cancels unsent work when notifications are read, favorites removed, or push subscriptions deactivated/reassigned. `ingest.py` cancels only when the canonical home transitions from active to nonactive, not merely when one active source disappears. Email unsubscribe/disable cancels pending/leased email. Accepted Expo receipt rows remain eligible for receipt reconciliation after invalidation.
- `models.py` and `auth.py` add only nullable `claim_token` fields. `008_delivery_leases.sql` and `005_delivery_leases_auth.sql` are additive, registered within their separate namespaces. `migrations.py` appends SQLite 008/005 hooks without modifying the immutable 001 callback. Existing values and checksums are retained. No external API or DTO changes.
- `test_delivery_races.py` provides controlled independent-session SQLite and real PostgreSQL races, invalidation/reversal, retry, receipt, diagnostics and migration checks. `test_service_integration.py` derives two expected migration counts from the registry. `scripts/verify.py` adds the race module to required service verification, which rejects skips.

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| T13-AC01 / TC01 | PASS | `test_simultaneous_workers_send_once`: synchronized starts, one sender held by an event while the other returns; one send and one attempt for email, push and auth on both SQLite and PostgreSQL. |
| T13-AC02 / TC02 | PASS | `test_stale_completion_cannot_change_replacement`: A enters transport, lease is expired, B enters transport, then A returns success or error; B's token, lease and status are unchanged for each worker/backend. `test_cancel_during_transport_is_not_replayed` covers cancellation. |
| T13-AC03 / TC03–TC04 | PASS for exercised cases | `test_delivery_removed_during_transport`, `test_auth_user_removed_during_transport`, `test_related_state_invalidated_during_transport`, and `test_pending_push_is_cancelled_for_each_policy` cover removal, account state, read, delist and unlike. `test_reversed_invalidation_does_not_reactivate_leased_job` and `test_unsubscribe_is_durable_even_if_reenabled_during_transport` cover reversal before callback. `test_postgres_listing_writer_and_completion_do_not_deadlock` controls the conflicting lock order. Account closure serialization with new writes is T15. |
| T13-AC04 / TC05–TC06 | PASS | `test_disabled_mail_does_not_block_erasure`, `test_erasure_retries_without_attempt_limit`, and `test_bounded_mail_and_stable_identity_after_uncertain_acceptance` cover selection, attempt exhaustion, erasure beyond attempt eight, and stable message IDs. |
| T13-AC05 / TC06 | PASS with transport caveat | Existing unique notification/delivery constraints survive migrations; the uncertain-acceptance test repeats the same logical delivery and Message-ID through eight attempts. SMTP acceptance before a crash or lost acknowledgement can produce duplicate physical email; no exactly-once physical delivery is claimed. A push accepted before a crash or cancellation prevents ticket persistence has the same unavoidable uncertainty. |
| T13-AC06 / TC04, TC07 | PASS | Existing confirmation/unsubscribe and push suites pass. `test_receipt_error_never_resends_accepted_ticket` and `test_accepted_receipt_survives_read_cancellation` verify receipt state, no resend, and reconciliation; `test_diagnostics_exclude_transport_details` checks status/attempt logging and redaction. |

## Verification

All commands ran from the T13 worktree on macOS 15.7.7 arm64, Python 3.12.9, Node 24.6.0, PostgreSQL 16.15 and local Elasticsearch 8.19.6. Fixtures and addresses are synthetic. Controlled race tests use events/barriers and explicit lease expiry, not arbitrary sleeps. `PYTHONPATH` points to this worktree; `.venv` was a temporary symlink to the existing environment.

- `TEST_POSTGRES_URL='postgresql+psycopg://rentals:synthetic@127.0.0.1:59560/t13' PYTHONPATH="$PWD/backend" .venv/bin/pytest backend/tests/test_delivery_races.py backend/tests/test_email_alerts.py backend/tests/test_push.py backend/tests/test_accounts.py -q -ra -o addopts=''` — exit 0; **93 passed, 0 failed, 0 skipped**, 16.70 seconds. Raw sanitized console: `.local/verification/T13/t13-20261111/targeted-final.txt`. The PostgreSQL URL was an isolated local throwaway container, not a persistent developer database.
- `PYTHONPATH="$PWD/backend" .venv/bin/pytest backend/tests/test_rental_journey.py backend/tests/test_migrations.py backend/tests/test_migration_registry.py -q -ra -o addopts=''` — exit 0; **16 passed, 0 failed, 0 skipped**, 0.86 seconds. Raw sanitized console: `.local/verification/T13/t13-20261111/regression-final.txt`. This was run after the implementation change and before adding two further fresh-PostgreSQL and two account-deletion test variants; those additions did not change application behavior.
- `PATH="/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH" make verify-services ARGS='--run-id t13-services-committed-20261111'` — exit 0; **77 passed, 0 failed, 0 skipped**. Real isolated PostgreSQL and Elasticsearch containers; report `.local/verification/T01/t13-services-committed-20261111/report.json` records `5d744ee`, clean tracked source, start/end and container cleanup. This includes the SQLite and PostgreSQL race tests and fresh/repeated and retained-row PostgreSQL upgrades for both namespaces.
- Earlier service run `t13-services-20261111` failed **7 passed, 2 failed, 0 skipped** because baseline service tests hard-coded four rentals migrations. The integrator authorized replacing only those two numeric assertions with the registry length; subsequent runs passed. Reports are retained under `.local/verification/T01/`.
- `git diff --check` exited 0. Existing tests exercised one synthetic local SMTP socket; no message went to a real recipient or external provider. No cloud resources, live portals, push sends, deployment, or push were used.

## Reproduction, recovery and review

- Race reproduction: run the targeted command with an isolated PostgreSQL URL; the tests explicitly hold sender A, force its lease past due, start B, then release A and inspect B's token and lease. For the writer race, completion holds its delivery row, the writer locks the listing, and both are released in controlled order; both complete and the delivery is cancelled.
- SQLite upgrade tests retain retry status/attempt counts in pre-column email and auth rows, run both hooks twice, and check the new column is null. PostgreSQL tests separately create fresh and tracked-baseline schemas for both namespaces, apply the registry twice, and preserve retained rows. Applied baseline SQL and the SQLite 001 callback are unchanged.
- Recovery: back up before deployment. Prefer restoring a verified backup or a forward corrective migration; automatic destructive down-migration is not provided. Do not apply the partially integrated branch registry to a persistent shared catalog. Integration must merge T08 rentals 006 and T13 rentals 008 in numeric order and rerun the full baseline-to-integrated upgrade suite.
- A lease cannot retract bytes already accepted by a provider. If a provider accepts a push ticket but the worker dies or loses its claim before persisting that ticket, the ticket cannot be reconciled from local state; an already persisted ticket is never resent while its receipt is pending. Likewise, a cancellation after transport starts cannot retract a physical send.
- Independent concurrency/security review is mandatory before acceptance, especially cross-service lock ordering with T08's revision/outbox changes and T15 account closure. T15 owns serialization of closure with new account writes. These are integration/review actions, not claims of completed review.

## Blockers and next action

No external credentials or provider access were needed. Integrator should review the changes, combine reserved migration entries and SQLite hooks with T08/T15, rerun the combined real-service and retained-row upgrade checks, and record the final integration evidence. No push, deployment or publication was performed.

## Integrator acceptance

Parent reviewed claim/completion predicates, related-state reads, cancellation writers and combined revision/delivery lock order. After combining rentals006/008 and auth005 with T03, independently executed 82 real-service/race tests (0 failures/skips) and 41 targeted account/email/push/journey/migration regressions (0 failures/skips) on2026-11-11. The raw sanitized service report is `.local/verification/T01/integrated-t13-review/report.json`. T15 still owns account-closure fencing against already-authenticated writes. No external transport or deployment was used.
