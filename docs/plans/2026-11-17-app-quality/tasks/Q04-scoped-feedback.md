# Q04 Make success and failure feedback visible and accessible

Status: **PLANNED** · Priority: **P2** · Active effort: **2–4 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q01** · Merge locks: **app-feedback, shared-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/App.tsx](../../../../apps/mobile/src/App.tsx): One absolute toast handles both successes and errors; it can sit outside an active dialog and near the comparison tray.

## Change

Introduce scoped feedback with polite success announcements, persistent actionable errors and an explicit dismiss control. Use an overlay-safe placement and an inline variant for dialogs. Migrate the root toast; later tasks own their individual pending operations.

## File scope

- `apps/mobile/src/App.tsx (feedback only)`
- `apps/mobile/src/components/UI.tsx`
- `apps/mobile/e2e/accessibility.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q04-AC01:** Success is announced once without interrupting typing; errors remain until dismissed or resolved.
- **Q04-AC02:** Feedback stays readable with comparison open, keyboard visible and 200% text; it does not cover essential controls.
- **Q04-AC03:** Dialog-owned errors render inside the active dialog; dismissal has a named keyboard-accessible target.

## Verification

- npm run typecheck
- Focused responsive/keyboard browser checks for toast, comparison and open-dialog combinations.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
