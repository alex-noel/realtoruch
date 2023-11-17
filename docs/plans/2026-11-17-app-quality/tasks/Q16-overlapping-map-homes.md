# Q16 Expose every home when map markers overlap

Status: **PLANNED** · Priority: **P2** · Active effort: **4–6 hours**

Executor: **economy** · Review: **strong: shared map behavior and accessibility**

Dependencies: **Q09, Q15** · Merge locks: **maps**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/PropertyMap.web.tsx](../../../../apps/mobile/src/components/PropertyMap.web.tsx): One price marker is created per home with no collision handling.
- [apps/mobile/src/components/PropertyMap.tsx](../../../../apps/mobile/src/components/PropertyMap.tsx): Native markers also overlap for shared coordinates.

## Change

Use a small shared grouping strategy for coincident/nearby markers and a selectable home list for each group. Keep grouping limited to the current page and preserve approximate-location wording.

## File scope

- `apps/mobile/src/components/PropertyMap.web.tsx`
- `apps/mobile/src/components/PropertyMap.tsx`
- `apps/mobile/src/components/mapGroups.ts (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q16-AC01:** A fixture with five homes at one point exposes all five by touch and through a keyboard-accessible web equivalent.
- **Q16-AC02:** Selected home and page changes update groups correctly; drawing mode suppresses marker interactions as before.
- **Q16-AC03:** No extra all-catalog fetch or coordinate jitter presents a fabricated precise address; group totals equal renderable active homes.

## Verification

- New pure grouping tests and browser group selection check; npm run typecheck.
- Native adapter tests and JS export; installed-device interaction remains a separate gate.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
