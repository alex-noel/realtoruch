# Q31 Add a clear review step before publishing changes

Status: **PLANNED** · Priority: **P2** · Active effort: **3–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q13, Q28, Q29, Q30** · Merge locks: **owner-editor, owner-dashboard**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): Original owner flow saves forms and publishes from a card without a listing review preview.

## Change

Provide a read-only preview from the current draft before publishing or applying edits to a published advert. Summarize photos, location disclosure, base rent and known/unknown charges, and keep saving a draft separate from publication.

## File scope

- `apps/mobile/src/components/AdvertEditor.tsx (from Q27)`
- `apps/mobile/src/components/AdvertDesk.tsx (from Q27)`
- `apps/mobile/src/components/AdvertPreview.tsx (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q31-AC01:** Preview matches the values actually submitted; returning to edit preserves content; preview does not call publish.
- **Q31-AC02:** Unverified accounts receive a verification path that preserves the draft; no misleading verified-owner badge appears.
- **Q31-AC03:** Publishing remains one explicit action with progress and local result feedback; conflict or failure keeps the preview/draft recoverable.

## Verification

- npm run typecheck
- Owner browser draft→preview→edit→publish, unknown fees and unverified-account cases.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No new backend advert states or payment flow. Q34 wires new upload states into this preview later.
