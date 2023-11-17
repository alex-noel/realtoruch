# Q30 Recover safely from concurrent advert edits

Status: **PLANNED** · Priority: **P1** · Active effort: **3–5 hours**

Executor: **economy** · Review: **strong: optimistic concurrency and moderation state**

Dependencies: **Q03, Q29** · Merge locks: **owner-editor, owner-dashboard**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [backend/realtoruch/marketplace.py](../../../../backend/realtoruch/marketplace.py): Version checks already reject stale edits with 409.
- [apps/mobile/src/marketplaceApi.ts](../../../../apps/mobile/src/marketplaceApi.ts): Client submits versions but has no conflict-reconciliation flow.

## Change

On conflict, retain a snapshot of the local draft, fetch the latest permitted advert and show changed-field context. Let the user reload after confirming discard or explicitly select values to submit against the latest version.

## File scope

- `apps/mobile/src/components/AdvertEditor.tsx (from Q27)`
- `apps/mobile/src/components/AdvertDesk.tsx (from Q27)`
- `apps/mobile/src/marketplaceApi.ts (fetch latest advert only if needed)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q30-AC01:** Two-session edit test proves no automatic overwrite; latest server content is unchanged until an explicit reconciled save.
- **Q30-AC02:** Local text and photos remain available during conflict recovery; a failed latest-version fetch is retryable.
- **Q30-AC03:** A second concurrent update causes another recoverable conflict; withdrawn/hidden/deleted state is explained without bypassing server rules.

## Verification

- npm run typecheck
- Real local API two-session owner browser scenario; existing optimistic-version backend regression.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
