# Q33 — Media attachment, privacy and erasure

Status: IMPLEMENTED_LOCAL; strong attachment, visibility, erasure and least-privilege review pending. Base Q32 commit 6ee65d1 (Q32 separately reviewed/integrated as b0ceb5e). Reuses the media lifecycle backend from main-root commits b3aa478 and a7d550c, adapted to the Q32 producer and this branch's API; frontend was not copied. No changes to migration 011: its blob is identical to the source (`2c071d2fe0efe6269ea9bcc35bde2b367a2c8f94`). Media remains disabled by default.

Ready owned IDs attach transactionally alongside HTTPS images within the combined 30-image cap. Private drafts remain owner-only. Unlike the original T23 implementation, withdrawn and saved-delisted homes preserve existing detail visibility and their previously published derivatives. Public media requires both a non-hidden canonical projection and the owning advert's own published source projection; a new private draft image or a URL injected by another source cannot become public. Cleanup and deletion retain a previously published image as long as its projection is retained, including while the withdrawn draft changes. Hidden, deleted and erased media deny retrieval. Existing per-account fencing serializes attach, deletion, closure and cleanup; durable tombstones fence delayed remote writes. Export adds bounded owner-only media metadata (not original bytes, digests, idempotency or storage keys). An optional disabled-by-default Helm cleanup job uses the existing API role; grants grant no other role media-table access.

| Criterion | Evidence |
| --- | --- |
| Q33-AC01 | Fixture tests reject foreign, pending and deleted attachments without changing version/draft; cover ready ordered attachment, combined cap, owner-only drafts, injected URL and public projection. |
| Q33-AC02 | Controlled source tests cover cancellation/closure while processing, storage failure retry, delayed remote put generation fences, repeated cleanup and referenced-media retention. |
| Q33-AC03 | Synthetic public, draft, withdrawn, saved-delisted, hidden and erased cases; owner-scoped metadata export; restricted PostgreSQL API-role upload/attach/publish/erase and non-API role denial in service profile. |

Actual evidence date: 17 November 2026 CET. Python 3.12.9, Node 24.6.0. All accounts and objects are synthetic, with private run-owned storage.

| Command | Result |
| --- | --- |
| `PYTHONPATH="$PWD/backend" .venv/bin/python -m pytest -o addopts='' backend/tests/test_media.py backend/tests/test_account_data.py backend/tests/test_marketplace.py -q` | 46 passed, 30 PostgreSQL cases skipped without the isolated service URL. |
| `PYTHONPATH="$PWD/backend" .venv/bin/python -m realtoruch.migrations validate` | Registry valid. |
| `PATH=<node24> PYTHONPATH="$PWD/backend" make verify-services ARGS='--run-id q33-final-20261117'` | 283 passed, 0 failed or skipped; exit 0. Sanitized report: `.local/verification/T01/q33-final-20261117/report.json`. The prior `q33-media-20261117` run passed 283 with no skips before the additional published-source anti-injection check. |
| `helm lint infra/helm/realtoruch` and `helm template q33 infra/helm/realtoruch --set mediaCleanup.enabled=true` | Lint passed and rendered the optional cleanup CronJob; local Helm binary from the existing T26 tooling cache. |
| `git diff --check` | clean. |

The service runner uses disposable PostgreSQL/Elasticsearch and the API's restricted role with local synthetic image bytes. `Q32` introduced 011 and the preserved runtime locks; Q33 changes only the narrow API-role grant and no schema. Restore the database and matching private object storage together, retain GCS deletion markers, and run cleanup after recovery; do not roll back 011. No real bucket, IAM, push, mail delivery or installed-device behavior was exercised. Original image bytes are intentionally excluded from the bounded JSON export; a separate binary-export design is needed if that product requirement is added. Strong independent review remains outstanding.
