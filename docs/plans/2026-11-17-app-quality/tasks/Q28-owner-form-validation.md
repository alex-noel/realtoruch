# Q28 Organize owner fields and match server validation

Status: **PLANNED** · Priority: **P1** · Active effort: **4–5 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q02, Q03, Q06, Q27** · Merge locks: **owner-editor**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): Original AdvertEditor coerces numbers on each keystroke and accepts world coordinate bounds.
- [backend/realtoruch/marketplace.py](../../../../backend/realtoruch/marketplace.py): AdvertBody requires Poland coordinates, bounded numeric fields and specific text constraints.

## Change

Group fields into Basics, Location, Costs and Photos without a new wizard framework. Preserve raw number strings and validate against current AdvertBody rules. Reuse Q06 parsing where semantics match. Replace comma-separated known amenities with labelled selections while retaining unknown stored values.

## File scope

- `apps/mobile/src/components/AdvertEditor.tsx (from Q27)`
- `apps/mobile/src/ownerValidation.ts (new)`
- `apps/mobile/src/components/coordinates.ts`
- `apps/mobile/tests/ownerValidation.test.ts (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q28-AC01:** Validate required text, integer rent/rooms, decimal area, optional blank vs zero, negative floor bounds and server maxima; do not loosen the server.
- **Q28-AC02:** Out-of-Poland coordinates fail inline even when globally valid; valid numeric edits remain possible without cursor/value jumps.
- **Q28-AC03:** First invalid field is reachable from a summary; changing sections preserves text; existing unknown amenities are visible and not silently dropped.

## Verification

- New table-driven validation cases; npm run typecheck.
- Owner browser valid/invalid save at 320 px, including 50,5 area and zero fees.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
