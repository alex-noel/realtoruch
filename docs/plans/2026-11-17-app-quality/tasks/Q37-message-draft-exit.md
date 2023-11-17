# Q37 Protect message drafts and describe their lifetime honestly

Status: **PLANNED** · Priority: **P1** · Active effort: **2–4 hours**

Executor: **economy** · Review: **strong: private drafts and retry identity**

Dependencies: **Q27, Q29** · Merge locks: **messages-state, marketplace-shell**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/messagesState.ts](../../../../apps/mobile/src/components/messagesState.ts): Drafts are an in-memory Map; some error text says they are saved.
- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): A new InboxModel is created on each dialog mount, so close/reopen loses drafts.

## Change

Keep the current in-dialog thread-switch draft behavior and add a deliberate discard/keep-editing exit guard. State that drafts are kept while this rental desk stays open. Cover parent close/Escape/native back without adding plaintext persistence. Extend the Q27/Q29 shared dirty-state and exit contract; do not introduce a competing nested close guard.

## File scope

- `apps/mobile/src/components/messagesState.ts`
- `apps/mobile/src/components/MarketplaceDialog.tsx (message exit only)`
- `apps/mobile/src/components/MessagesPanel.tsx (draft copy)`
- `apps/mobile/tests/messages.test.tsx`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q37-AC01:** Closing with any unsent draft requires an explicit discard or returns to editing; confirming discard closes cleanly.
- **Q37-AC02:** Sign-out/account switch clears drafts and cannot show another account private text; this reset overrides the ordinary exit guard.
- **Q37-AC03:** Unchanged-text retries preserve their client message IDs; failed-send text remains editable and the UI makes no durable-save promise.

## Verification

- Existing messages unit tests plus close/discard/account-switch cases; npm run typecheck.
- Browser draft→thread switch→close cancel→close discard and native back adapter test.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No localStorage/AsyncStorage message-body persistence or new server draft entity.
