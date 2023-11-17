# Q17 Improve rent history and insights on small screens

Status: **PLANNED** · Priority: **P2** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **insights, dialogs-history**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/Insights.tsx](../../../../apps/mobile/src/components/Insights.tsx): A fixed 800×290 chart labels every month; text rows already exist.
- [apps/mobile/src/components/Dialogs.tsx](../../../../apps/mobile/src/components/Dialogs.tsx): Listing history silently slices to the latest eight observations.

## Change

Use readable bounded date ticks, a concise chart summary and clear sample/period labels. Retain the existing textual data and methodology. Label the eight-observation detail limit and optionally reveal more already-loaded rows.

## File scope

- `apps/mobile/src/components/Insights.tsx`
- `apps/mobile/src/components/Dialogs.tsx (history only)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q17-AC01:** Zero, one, many and flat-value series render without misleading percentage changes or unreadable phone labels.
- **Q17-AC02:** Small samples and illustrative data remain prominent; period change is described as observed sample medians, not appreciation of the same homes.
- **Q17-AC03:** History truncation is explicit; dates and PLN values are consistently readable; switching city resets an invalid district selection.

## Verification

- npm run typecheck
- Deterministic zero/one/24-month/long-history fixtures at 320 and 1440 px.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No historical aggregation changes, new chart package or market-wide claim.
