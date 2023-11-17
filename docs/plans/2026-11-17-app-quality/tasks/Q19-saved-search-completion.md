# Q19 Resume saving after sign in and clarify saved searches

Status: **PLANNED** · Priority: **P1** · Active effort: **3–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q07, Q18** · Merge locks: **app-saved-searches**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): Guest Save search opens auth without a pending intent; the default name is hardcoded to Kraków and cards show little constraint detail.

## Change

Capture the requested search when sign-in is required, then reopen its naming dialog after authentication. Derive a useful editable name from city/constraints, show the shared filter summary and add named deletion confirmation with per-row busy/error state.

## File scope

- `apps/mobile/src/App.tsx (save-search intent/cards)`
- `apps/mobile/src/filterSummary.ts (from Q07)`
- `apps/mobile/e2e/journey.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q19-AC01:** A guest saving a Warszawa polygon search returns to that exact draft after login; cancellation makes no saved search.
- **Q19-AC02:** Saving produces one record and preserves the silent existing-match baseline; displayed constraints equal persisted filters.
- **Q19-AC03:** Cancel deletion preserves the search; confirmed deletion affects only the selected row and failures are retryable in place.

## Verification

- npm run typecheck
- Browser guest/auth continuation, save baseline and deletion cancel/failure cases.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No rename/pause API, duplicate-search merging or alert-baseline changes.
