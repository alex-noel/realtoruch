# Q13 Clarify listing costs and bring primary actions forward

Status: **PLANNED** · Priority: **P2** · Active effort: **3–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q01, Q10** · Merge locks: **listing-card, dialogs-detail**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/ListingCard.tsx](../../../../apps/mobile/src/components/ListingCard.tsx): Cards mix several small badges, price and secondary actions.
- [apps/mobile/src/components/Dialogs.tsx](../../../../apps/mobile/src/components/Dialogs.tsx): Contact/save/report actions follow long source and history content.

## Change

Create a clear title, availability, base-rent and known-cost hierarchy. Place save and the appropriate contact/source action near the top; group detailed sources, risk explanations and observations below.

## File scope

- `apps/mobile/src/components/ListingCard.tsx (layout)`
- `apps/mobile/src/components/Dialogs.tsx (DetailDialog layout)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q13-AC01:** Unknown fees remain unknown, zero remains zero, and no partial total is labelled a complete monthly cost.
- **Q13-AC02:** Imported adverts link to the provider; only eligible first-party adverts offer private messaging; unavailable states remain explicit.
- **Q13-AC03:** Primary actions are reachable before long descriptions/history at 390 px, remain visible at 200% text and do not overlap content.

## Verification

- npm run typecheck
- Review fixtures with zero/unknown fees, long text, multiple sources and delisted favorites; owner and accessibility browser specs.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No new pricing calculation, risk score, ownership-verification claim or sticky overlay that hides content.
