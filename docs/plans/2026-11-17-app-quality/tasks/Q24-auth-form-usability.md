# Q24 Finish sign in and password form interactions

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q02, Q03** · Merge locks: **dialogs-auth, account-dialog**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/Dialogs.tsx](../../../../apps/mobile/src/components/Dialogs.tsx): AuthDialog uses generic fields and a 12-character disabled rule without inline explanation.
- [apps/mobile/src/components/AccountDialog.tsx](../../../../apps/mobile/src/components/AccountDialog.tsx): Reset and deletion password inputs use the same minimal Field.

## Change

Apply Q02 field semantics, keyboard submit and accessible password reveal. Explain validation near inputs, with appropriate current/new-password hints. Keep authentication and account-enumeration behavior unchanged.

## File scope

- `apps/mobile/src/components/Dialogs.tsx (AuthDialog)`
- `apps/mobile/src/components/AccountDialog.tsx (password fields)`
- `apps/mobile/src/components/UI.tsx (password reveal if needed)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q24-AC01:** Password managers can distinguish sign-in, registration, reset and current-password confirmation; email uses the right keyboard/autofill.
- **Q24-AC02:** Users understand why submission is unavailable; invalid fields are announced and focus moves sensibly after an unsuccessful submit.
- **Q24-AC03:** Reveal does not log or persist passwords; register/reset/sign-in transitions clear irrelevant messages and keep existing link handling working.

## Verification

- npm run typecheck
- Existing linking/session browser cases plus keyboard submit, reveal and validation checks.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
