# Q15 Recover from map loading and tile failures

Status: **PLANNED** · Priority: **P1** · Active effort: **3–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **maps, app-discovery**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/DeferredPropertyMap.web.tsx](../../../../apps/mobile/src/components/DeferredPropertyMap.web.tsx): Suspense handles loading but not rejected map imports.
- [apps/mobile/src/components/PropertyMap.web.tsx](../../../../apps/mobile/src/components/PropertyMap.web.tsx): Leaflet import and tile layer have no visible failure recovery.

## Change

Add a scoped map error boundary and observable map/tile failure states with retry and list fallback. Keep coordinate entry available in the owner editor when the basemap is unavailable.

## File scope

- `apps/mobile/src/components/DeferredPropertyMap.web.tsx`
- `apps/mobile/src/components/PropertyMap.web.tsx`
- `apps/mobile/src/components/PropertyMap.tsx`
- `apps/mobile/src/components/MapDrawing.tsx (fallback integration only)`
- `apps/mobile/src/App.tsx (map fallback view callback only)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q15-AC01:** Rejected chunk import and repeated tile failures show distinct actionable messages, not a blank map or zero-result claim.
- **Q15-AC02:** Retry cleans up old map/listener instances; filters and drawn area survive; no repeated automatic network loop.
- **Q15-AC03:** Discovery remains usable through list view, and owner pin coordinates can still be edited; attribution remains present when tiles render.

## Verification

- npm run typecheck
- Local browser import/tile fault injection plus existing keyboard polygon regression; native adapter error smoke where supported.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
