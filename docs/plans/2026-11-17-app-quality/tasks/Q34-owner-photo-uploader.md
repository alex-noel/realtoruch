# Q34 Finish photo picking upload ordering and retry

Status: **PLANNED** · Priority: **P1** · Active effort: **5–7 hours**

Executor: **economy** · Review: **strong: media contract, cancellation and account lifecycle**

Dependencies: **Q11, Q29, Q30, Q31, Q33** · Merge locks: **owner-editor, media-client, native-dependencies**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): Current editor only accepts newline-separated photo URLs.
- [docs/plans/2026-11-12-two-week-sprint/tasks/T24-owner-photo-uploader.md](../../2026-11-12-two-week-sprint/tasks/T24-owner-photo-uploader.md): The prior uploader scope remains unfinished.

## Change

Consume the reviewed Q32/Q33 contract with web/native picker adapters, per-photo queued/uploading/ready/failed states, retry/cancel and accessible reorder/remove. Limit active uploads to three. Show the first ready ordered image as the cover while retaining legacy links visibly.

## File scope

- `apps/mobile/src/components/AdvertEditor.tsx (from Q27)`
- `apps/mobile/src/components/AdvertPreview.tsx (from Q31)`
- `apps/mobile/src/components/PhotoUploader.tsx (new)`
- `apps/mobile/src/mediaClient.ts (new)`
- `apps/mobile/src/marketplaceApi.ts (media DTO)`
- `apps/mobile/package.json`
- `apps/mobile/package-lock.json`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q34-AC01:** Only ready owned IDs attach in selected order; unresolved uploads prevent publication with clear next actions.
- **Q34-AC02:** Permission denial, invalid files, timeout, cancel and conflict preserve other photos/text; retries reuse identity and late canceled responses cannot attach.
- **Q34-AC03:** Keyboard reorder/remove works at 320 px; previews/listeners/temp files are cleaned on exit and account change.

## Verification

- New uploader state/adapter tests and complete local owner upload→order→save→publish browser flow.
- npm run typecheck and native JS exports; installed photo-picker/permission checks remain explicitly separate.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
