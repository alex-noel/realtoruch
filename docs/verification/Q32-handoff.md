# Q32 — Bounded owned media producer

Status: IMPLEMENTED_LOCAL; independent upload/auth/resource and migration review pending. Base 4f73b5de565626fe71913e63cdc3bb0904520fdc; branch codex/q32-media-quality. Reuses backend/storage and lock changes from main-root commits b3aa478 and a7d550c, not their frontend changes. The 011 SQL bytes are unchanged from that source. Media defaults to disabled in all environments. Q33 attachment, public retrieval, cleanup, erasure and role grants are not yet active in this commit.

The contract freezes the complete media-assets schema and Q33 relations: ordered IDs remain in the existing advert draft JSON, guarded by the per-account fence, with no new association table or changes to 011. Uploads stream at most 10 MiB, validate declared format and image dimensions/animation, normalize orientation, discard metadata, and generate only bounded JPEG derivatives. Opaque owner-scoped idempotency keys, account closure checks, private previews and deletion fences are retained from the source implementation. No originals or storage paths are exposed. Public rollout remains disabled pending Q33/Q34 and review.

| Criterion | Evidence |
| --- | --- |
| Q32-AC01 | Generated JPEG/PNG/WebP, GPS/orientation, MIME mismatch, SVG, animation, streamed oversize, decoded dimensions, and concurrent-processor tests in `test_media.py`. |
| Q32-AC02 | Controlled status/preview/delete ownership, unverified and closed accounts, same-key retry/conflict, cancellation and local storage path tests; server errors are bounded. |
| Q32-AC03 | Registry validation, repeatable SQLite upgrade retaining rows, and real PostgreSQL migration upgrade in the service profile. Existing applied SQL and hook checksums remain unchanged. |

Actual evidence date: 2026-11-17 CET. Python 3.12.9, Node 24.6.0. Commands used the shared read-only environment with `PYTHONPATH` set to this checkout. All test accounts and data are synthetic.

| Command | Result |
| --- | --- |
| `PYTHONPATH="$PWD/backend" .venv/bin/python -m pytest -o addopts='' backend/tests/test_media.py backend/tests/test_migration_registry.py -q` | 16 passed, 11 PostgreSQL cases skipped without the isolated service URL. |
| `PYTHONPATH="$PWD/backend" .venv/bin/python -m realtoruch.migrations validate` | Registry valid. |
| `PATH=<node24> PYTHONPATH="$PWD/backend" make verify-services ARGS='--run-id q32-media-20261117b'` | 264 passed, 0 failed or skipped; exit 0. Sanitized report: `.local/verification/T01/q32-media-20261117b/report.json`. |
| `git diff --check` | clean. |

The first service run (`q32-media-20261117`) had 263 passes and one pre-existing 010-only SQLite upgrade assertion failure; it was updated to require both 010 and 011 while retaining all earlier checksum and retained-row assertions. The second profile passed. The additional closed-account test was run in the focused SQLite suite after the service profile collected tests. The verification runner change adds the media suite and private run-owned storage; no provider deployment or credentials were used. Production cleanup, restricted-role lifecycle and the final visibility contract are Q33 obligations. A matching database and object-storage backup is required for recovery after media is enabled; never roll back applied 011 destructively.
