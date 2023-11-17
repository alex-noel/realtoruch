# Q12 Make listing galleries usable with many photos

Status: **PLANNED** · Priority: **P2** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q11** · Merge locks: **dialogs-detail**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/Dialogs.tsx](../../../../apps/mobile/src/components/Dialogs.tsx): DetailDialog renders a full Photo N chip for every image and a single static image.

## Change

Add previous/next controls, a position count and a bounded thumbnail strip. Reset the selected photo when the listing changes and expose a no-photo state.

## File scope

- `apps/mobile/src/components/Dialogs.tsx (gallery)`
- `apps/mobile/e2e/accessibility.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q12-AC01:** Zero, one and 30-photo fixtures remain usable at 320 px; missing photos have an explicit placeholder, and controls/selected position are labelled.
- **Q12-AC02:** Web keyboard navigation works while gallery controls are focused without stealing keys from other inputs.
- **Q12-AC03:** Only the displayed image and bounded nearby thumbnails load; failed images use Q11 recovery.

## Verification

- npm run typecheck
- Browser one/30-photo, keyboard, source change and failed-photo checks.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No image editor, new gallery library, fullscreen zoom system or remote image transformation.
