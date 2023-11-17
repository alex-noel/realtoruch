# Q18 Load saved homes searches and inbox independently

Status: **PLANNED** · Priority: **P1** · Active effort: **3–5 hours**

Executor: **economy** · Review: **strong: private state and session-generation races**

Dependencies: **None** · Merge locks: **app-private-state**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): refreshAccount uses one Promise.all, preventing all three updates if any endpoint fails.

## Change

Extract independent loading/data/error/retry state for favorites, searches and notifications. Keep the account-generation boundary and preserve loaded pages according to explicit merge rules.

## File scope

- `apps/mobile/src/App.tsx (refreshAccount and private views)`
- `apps/mobile/src/hooks/useAccountCollections.ts (new)`
- `apps/mobile/tests/accountCollections.test.ts (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q18-AC01:** Failure of each endpoint leaves the other two usable; successful empty and initial loading are distinguishable.
- **Q18-AC02:** Retry preserves last successful data; stale data is labelled when a refresh fails, without silently clearing collections.
- **Q18-AC03:** Account switch/sign-out clears old private data immediately; delayed old-account responses cannot populate the new account.

## Verification

- New controlled-response lifecycle tests; npm run typecheck.
- Existing session, journey and account-switch browser regressions.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
