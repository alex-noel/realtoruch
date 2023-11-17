# Q06 Fix decimal and range input in filters

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q02** · Merge locks: **dialogs-filter**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/Dialogs.tsx](../../../../apps/mobile/src/components/Dialogs.tsx): FilterDialog.numeric strips commas, so 50,5 becomes 505; apply permits equal min/max rent despite an exclusive ceiling.

## Change

Keep raw editable text until validation. Parse documented comma or dot decimals without silent digit stripping; validate fields before applying. Keep integer PLN rent and decimal area rules consistent with the API.

## File scope

- `apps/mobile/src/components/Dialogs.tsx (FilterDialog)`
- `apps/mobile/src/filterNumbers.ts (new)`
- `apps/mobile/tests/filterNumbers.test.ts (new)`
- `apps/mobile/e2e/boundaries.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q06-AC01:** Area 50,5 and 50.5 both mean 50.5; malformed, negative, nonfinite and partial inputs do not become another valid number.
- **Q06-AC02:** Equal rent bounds are invalid because max rent is exclusive; equal area bounds remain valid because area bounds are inclusive.
- **Q06-AC03:** Blank remains unset, errors identify the field, and correcting input clears errors without losing other draft values.

## Verification

- New pure numeric parsing cases; npm run typecheck.
- boundaries.spec.ts includes comma input and exclusive/inclusive equal-bound cases.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

Do not change backend rent semantics or implement locale selection.
