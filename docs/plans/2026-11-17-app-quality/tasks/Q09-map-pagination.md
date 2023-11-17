# Q09 Make pagination work in list split and map views

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **app-discovery**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): The pager is nested under showList, so map-only users cannot browse past the first 24 results.

## Change

Extract one shared results pager outside the list-only branch. Preserve search snapshot rules and move focus/scroll to the result context after a deliberate page change.

## File scope

- `apps/mobile/src/App.tsx (results/pager)`
- `apps/mobile/e2e/boundaries.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q09-AC01:** A fixture with at least 49 homes can reach pages 1–3 in map, list and split views; marker and card IDs match the same page.
- **Q09-AC02:** No pager operates on an obsolete result snapshot; loading and end pages disable the correct controls.
- **Q09-AC03:** Switching view retains page and filters; closing a listing restores the previous browsing position.

## Verification

- npm run typecheck
- Browser regression exercises next/previous in map-only mode and closing details on page two.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
