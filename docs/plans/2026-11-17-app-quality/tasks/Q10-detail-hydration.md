# Q10 Show detail loading and recover locally from failures

Status: **PLANNED** · Priority: **P1** · Active effort: **2–4 hours**

Executor: **economy** · Review: **strong: detail visibility and account race preservation**

Dependencies: **Q03, Q04** · Merge locks: **app-detail, dialogs-detail**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): openHome displays card data, hydrates detail asynchronously and reports failure only through the global toast.

## Change

Model summary/loading/loaded/failed/unavailable detail states. Keep the summary visible while history and contact data load, and offer retry inside the dialog. Retain detailRequest and account-generation fencing.

## File scope

- `apps/mobile/src/App.tsx (openHome/detail state)`
- `apps/mobile/src/components/Dialogs.tsx (DetailDialog)`
- `apps/mobile/e2e/boundaries.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q10-AC01:** Transport failure shows local retry without pretending missing history/contact data is an empty successful result.
- **Q10-AC02:** 404/hidden/unavailable detail has truthful copy and does not leave stale contact actions active.
- **Q10-AC03:** Open A, then B, and resolve A late: B remains open; close/unmount/account switch prevents stale completion.

## Verification

- Deterministic delayed/failing detail-response tests; npm run typecheck.
- Browser opens detail offline, retries, switches homes and verifies modal feedback.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
