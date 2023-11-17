# Q07 Expose active filters and predictable reset actions

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q06** · Merge locks: **app-discovery, dialogs-filter**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): Advanced values are mostly hidden behind a partial count; empty-state reset uses DEFAULT_FILTERS and changes the city.

## Change

Show compact removable summaries of all applied constraints, including the default apartment property type. Define the badge as the number of deviations from DEFAULT_FILTERS, not the number of visible summaries. Label the reset action Reset filters: restore documented defaults while preserving the selected city and clearing text/polygon. Reuse one summary/count helper for discovery and saved searches.

## File scope

- `apps/mobile/src/App.tsx (filter summary/empty state)`
- `apps/mobile/src/components/Dialogs.tsx (FilterDialog)`
- `apps/mobile/src/filterSummary.ts (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q07-AC01:** Every applied constraint is represented truthfully, including the default apartment type, direct, zero commission and risk; the badge counts deviations from defaults and labels base rent accurately.
- **Q07-AC02:** Removing one constraint preserves the others and resets pagination. Reset filters restores defaults, clears query/polygon and retains the city; the apartment summary remains visible and the deviation badge becomes zero.
- **Q07-AC03:** No-results recovery resets constraints in the current city instead of jumping to Kraków; the UI explains that the default property type remains apartments.

## Verification

- New filter-summary helper cases; npm run typecheck.
- Browser: apply several filters, remove one, reset filters, and recover an empty Warszawa result.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
