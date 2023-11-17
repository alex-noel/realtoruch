# Q35 Clarify advert status and appeal progress

Status: **PLANNED** · Priority: **P1** · Active effort: **3–5 hours**

Executor: **economy** · Review: **strong: owner-only appeal projection and visibility**

Dependencies: **Q03, Q25, Q27, Q31** · Merge locks: **owner-dashboard, marketplace-backend**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): Original cards show minimal state, allow predictably rejected actions and hide appeal submission progress.
- [backend/realtoruch/marketplace.py](../../../../backend/realtoruch/marketplace.py): Own-advert responses omit pending appeal status although duplicate appeals return 409.

## Change

Add independent profile/adverts loading and retry, last-saved time, meaningful draft/published/withdrawn/hidden actions and named withdrawal confirmation. Project a minimal own-advert appeal state from existing records; show submitted/pending/resolved feedback without exposing review contents.

## File scope

- `apps/mobile/src/components/AdvertDesk.tsx (from Q27)`
- `apps/mobile/src/marketplaceApi.ts (own-advert DTO)`
- `backend/realtoruch/marketplace.py (own-advert projection only)`
- `backend/tests/test_marketplace.py`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q35-AC01:** Loading is not shown as an empty dashboard; a failed profile request does not discard a successfully loaded advert list.
- **Q35-AC02:** Hidden adverts offer the appropriate appeal path rather than a publish action that must fail; pending appeals cannot be resubmitted after refresh.
- **Q35-AC03:** Withdrawal cancellation changes nothing; successful actions announce the affected advert; appeal state is visible only to its owner.

## Verification

- Focused own-advert/appeal authorization backend tests; npm run typecheck.
- Owner browser independent load errors, states, withdraw cancel and appeal refresh.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No advert lifecycle, moderation-decision or billing changes beyond the minimal owner-only appeal projection; preserve existing authorization and hide/restore rules.
