# Q27 Extract rental desk components for safe delegation

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **marketplace-shell**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): AdvertDesk, AdvertEditor and ReviewDesk share one large file, creating conflicts for parallel quality work.

## Change

Move the three existing components to focused modules with small typed props and an explicit parent-close/dirty-state extension point. Preserve behavior and lazy marketplace loading; publish the component interfaces for following tasks.

## File scope

- `apps/mobile/src/components/MarketplaceDialog.tsx`
- `apps/mobile/src/components/AdvertDesk.tsx (new)`
- `apps/mobile/src/components/AdvertEditor.tsx (new)`
- `apps/mobile/src/components/ReviewDesk.tsx (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q27-AC01:** Existing owner and moderation behavior is unchanged; no API or state-machine rewrite.
- **Q27-AC02:** Editor, dashboard and review workers can modify separate files; shared shell ownership and props are documented.
- **Q27-AC03:** The marketplace stays lazy-loaded and existing owner/messages browser cases pass.

## Verification

- npm run typecheck; existing owner.spec.ts and messages unit tests.
- Review a move-oriented diff; no new tests are needed solely to mirror extraction.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No styling overhaul, unrelated App.tsx extraction or new router.
