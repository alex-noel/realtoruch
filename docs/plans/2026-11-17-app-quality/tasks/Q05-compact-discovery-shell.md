# Q05 Reduce discovery chrome and clarify mobile navigation

Status: **PLANNED** · Priority: **P2** · Active effort: **3–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q01** · Merge locks: **app-shell, source-status**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): Large marketing header, search, provider status and navigation precede results; narrow navigation is icon-heavy.
- [apps/mobile/src/components/SourceStatus.tsx](../../../../apps/mobile/src/components/SourceStatus.tsx): Provider explanations are always expanded above the results.

## Change

Use a compact mobile heading, concise navigation labels and a collapsible provider-details section. Keep search and result context prominent. Preserve the existing desktop identity, source-health semantics and discovery controls.

## File scope

- `apps/mobile/src/App.tsx (header/navigation only)`
- `apps/mobile/src/components/SourceStatus.tsx`
- `apps/mobile/tests/sourceStatus.test.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q05-AC01:** At 390×844 the search controls and result heading are reachable without scrolling through expanded provider explanations; 320 px and 200% text may grow naturally without overlap.
- **Q05-AC02:** Every navigation item has a visible understandable label and announced selected state; current counts remain legible.
- **Q05-AC03:** Unavailable/stale source warnings remain visible in the summary; expanding exposes exact timestamps and retry without implying complete coverage.

## Verification

- npm run test:unit -- tests/sourceStatus.test.ts
- source-status.spec.ts and accessibility.spec.ts; capture 320/390/768/1440 px views.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
