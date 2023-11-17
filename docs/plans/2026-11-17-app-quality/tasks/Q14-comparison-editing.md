# Q14 Improve mobile comparison and selection management

Status: **PLANNED** · Priority: **P2** · Active effort: **3–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q11, Q13** · Merge locks: **app-comparison, dialogs-compare**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/Dialogs.tsx](../../../../apps/mobile/src/components/Dialogs.tsx): CompareDialog stacks complete home columns on narrow screens.
- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): Comparison tray exposes count and clear, without named per-home removal; snapshots can age.

## Change

Show named selections with individual removal, and use metric-first comparison on mobile so the same attribute is adjacent across homes. Explicitly label comparison snapshots or refresh them safely when opening.

## File scope

- `apps/mobile/src/App.tsx (comparison)`
- `apps/mobile/src/components/Dialogs.tsx (CompareDialog)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q14-AC01:** One selection can be removed without clearing the others; maximum three remains enforced with visible feedback.
- **Q14-AC02:** Long titles and source names do not misalign desktop rows; mobile can compare a metric across two/three homes without scrolling through whole cards. A no-photo placeholder keeps compared homes identifiable and aligned.
- **Q14-AC03:** Unknown costs and inactive status remain explicit; any refresh failure preserves and labels the last snapshot.

## Verification

- npm run typecheck
- Browser two/three-home selection, individual removal, long values and stale/error scenario.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
