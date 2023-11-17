# Q29 Protect unsaved advert and profile changes

Status: **PLANNED** · Priority: **P1** · Active effort: **3–4 hours**

Executor: **economy** · Review: **strong: account reset must override draft preservation**

Dependencies: **Q27, Q28** · Merge locks: **owner-editor, owner-dashboard, marketplace-shell**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): Back, mode switch and dialog close unmount editor/profile state without a dirty-state guard.

## Change

Use one dirty-state contract for advert and profile edits. Intercept Back, mode changes, dialog close/Escape and native back. Offer Keep editing and Discard; offer Save only for a valid complete draft.

## File scope

- `apps/mobile/src/components/AdvertEditor.tsx (from Q27)`
- `apps/mobile/src/components/AdvertDesk.tsx (from Q27)`
- `apps/mobile/src/components/MarketplaceDialog.tsx`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q29-AC01:** All deliberate exit paths protect changed content; pristine or successfully saved content exits normally.
- **Q29-AC02:** Failed save retains all fields and dirty state; canceling discard restores focus to the editor.
- **Q29-AC03:** No partial-draft autosave or publication is implied; sign-out/account change clears private state instead of preserving it for another account.

## Verification

- npm run typecheck
- Owner browser close/Escape/tab/back/cancel-discard tests plus native back adapter check.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
