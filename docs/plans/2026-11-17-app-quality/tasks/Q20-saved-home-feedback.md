# Q20 Make saved homes and favorite mutations predictable

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q04, Q18, Q13** · Merge locks: **app-favorites, listing-card, dialogs-detail**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): favoriteBusy is a ref not surfaced by cards; saved view has little separation of active and unavailable homes.

## Change

Expose per-home pending state on save actions in card/detail, with inline recovery. Add a small All/Available/Unavailable saved-home filter and useful loaded-empty guidance.

## File scope

- `apps/mobile/src/App.tsx (favorites)`
- `apps/mobile/src/components/ListingCard.tsx (save control)`
- `apps/mobile/src/components/Dialogs.tsx (DetailDialog save props/control only)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q20-AC01:** Repeated save taps issue one operation; failed save keeps the last confirmed state and offers retry.
- **Q20-AC02:** Removing a home from Saved updates only after success; zero matching availability results differ from an empty saved collection.
- **Q20-AC03:** Delisted favorites remain accessible; moderation-hidden visibility rules and account-switch fencing are unchanged.

## Verification

- npm run typecheck
- Browser slow/failed favorite action and active/delisted saved-home fixtures; existing visibility backend tests if API behavior changes.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
