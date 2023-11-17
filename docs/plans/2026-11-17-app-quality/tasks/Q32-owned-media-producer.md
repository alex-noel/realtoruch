# Q32 Implement bounded owned image upload and storage

Status: **PLANNED** · Priority: **P1** · Active effort: **6–9 hours**

Executor: **experienced** · Review: **strong: upload processing, auth, resource bounds and migrations**

Dependencies: **None** · Merge locks: **media-schema, media-api, backend-dependencies**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [docs/plans/2026-11-12-two-week-sprint/tasks/T23-owned-media-storage.md](../../2026-11-12-two-week-sprint/tasks/T23-owned-media-storage.md): T23 remains unimplemented; current adverts store external HTTPS links.
- [backend/realtoruch/marketplace.py](../../../../backend/realtoruch/marketplace.py): Images are currently HTTPS URLs, maximum 30.

## Change

Publish the media DTO/state/error/idempotency contract first. Implement verified-owner upload/status/delete and a run-owned local storage adapter; define a fakeable remote adapter interface. Keep the feature disabled until Q33 lifecycle and Q34 UI integration are reviewed. Carry forward T23 limits: JPEG/PNG/WebP, 10 MiB streamed, 20 MP decoded, orientation normalization, metadata stripping, thumbnail and display rendition up to 2048 px. Before applying migration 011, review the complete Q33 attachment/cleanup relations and freeze them in this contract. Pin visibility: draft previews owner-only; validated published derivatives follow listing visibility; withdrawn/saved-delisted reads follow the existing detail authorization; hidden and erased assets deny public retrieval. Never expose originals. Any later schema addition uses an integrator-assigned forward migration and SQLite hook.

## File scope

- `backend/realtoruch/media.py (new)`
- `backend/realtoruch/media_storage.py (new)`
- `backend/realtoruch/models.py (MediaAsset)`
- `backend/realtoruch/settings.py (media config)`
- `backend/realtoruch/api.py (upload route/body limit)`
- `backend/realtoruch/migrations.py (new hook)`
- `infra/sql/011_media_assets.sql (new)`
- `infra/sql/migrations.json`
- `backend/pyproject.toml`
- `backend/requirements-runtime.lock`
- `backend/requirements-dev.lock`
- `backend/tests/test_media.py (new)`
- `docs/contracts/media.md (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q32-AC01:** Reject spoofed types, animations, SVG, oversized/chunked bodies and decompression bombs before readiness; originals never become public.
- **Q32-AC02:** Opaque IDs and idempotency isolate owners; upload/delete/status enforce closure/ownership, and paths/errors reveal no filesystem or private metadata.
- **Q32-AC03:** Migration 011 supports fresh/upgrade SQLite and PostgreSQL without changing applied checksums; local fixtures demonstrate bounded processing and clean failure.

## Verification

- New media validation/ownership/idempotency tests using generated images; migration registry validation.
- make verify-services for actual roles/migrations when routes are integrated; report missing prerequisites explicitly.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No bucket/CDN provisioning, arbitrary-URL proxying, portal-photo copying or public media rollout. Q33 owns attachment, retrieval visibility and lifecycle cleanup.
