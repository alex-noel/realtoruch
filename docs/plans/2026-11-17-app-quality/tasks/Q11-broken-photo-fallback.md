# Q11 Handle broken listing photos across all screens

Status: **PLANNED** · Priority: **P1** · Active effort: **1–2 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **listing-photo**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/ListingCard.tsx](../../../../apps/mobile/src/components/ListingCard.tsx): ListingPhoto has no web onError or native onError handling; detail and comparison reuse it.

## Change

Render a neutral accessible placeholder for failed URLs while preserving image dimensions and lazy loading. Reset failure state when the photo source changes.

## File scope

- `apps/mobile/src/components/ListingCard.tsx (ListingPhoto)`
- `apps/mobile/tests/listingPhoto.test.tsx (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q11-AC01:** 404, rejected and undecodable URLs produce a stable placeholder wherever ListingPhoto is rendered in cards, detail and compare; missing-photo call sites are completed in Q12/Q14.
- **Q11-AC02:** Changing from a broken to a working URL recovers; the fallback cannot trigger an endless retry loop.
- **Q11-AC03:** Aspect ratio, alt text, lazy loading and native rendering remain intact without layout jumps.

## Verification

- New photo failure/source-change cases; npm run typecheck.
- Browser screenshot with synthetic failed image URLs.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
