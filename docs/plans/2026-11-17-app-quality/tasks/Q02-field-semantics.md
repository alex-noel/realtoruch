# Q02 Complete shared field semantics and inline errors

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **shared-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/UI.tsx](../../../../apps/mobile/src/components/UI.tsx): Field only offers secure/numeric flags; email, password autocomplete, helper text and per-field errors are not modeled.

## Change

Add explicit input-purpose, autocomplete, submit, helper and error props with web/native mappings. Preserve existing call sites. Keep parsing separate from the visual field component.

## File scope

- `apps/mobile/src/components/UI.tsx`
- `apps/mobile/tests/fields.test.tsx (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q02-AC01:** Email, current-password and new-password modes expose the correct platform hints; labels remain programmatically associated.
- **Q02-AC02:** Only invalid fields announce errors, using stable IDs; helper text remains available without marking valid fields invalid.
- **Q02-AC03:** Keyboard submission and multiline behavior are distinct, and existing numeric inputs remain compatible.

## Verification

- npm run typecheck
- New focused field semantics tests; verify web DOM and native prop mapping.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
