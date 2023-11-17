# Q08 Replace sort cycling with an explicit choice

Status: **PLANNED** · Priority: **P2** · Active effort: **1–2 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **app-discovery**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): Change sort order advances through a hidden array of choices rather than presenting a selection.

## Change

Offer the existing four named sort options in an accessible selector or small panel. Keep the current sort visible and preserve the existing search lifecycle.

## File scope

- `apps/mobile/src/App.tsx (sort control)`
- `apps/mobile/e2e/boundaries.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q08-AC01:** Keyboard and touch can choose any option directly; current choice is announced.
- **Q08-AC02:** Cancel makes no request; choosing a different sort resets page to one and retains filters.
- **Q08-AC03:** Rapid changes cannot display a stale sort result; the UI works at 320 px.

## Verification

- npm run typecheck
- Focused browser sort selection/cancel and latest-request checks.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
