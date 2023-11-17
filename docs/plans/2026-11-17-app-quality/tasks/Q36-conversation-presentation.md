# Q36 Improve conversation overview and reading context

Status: **PLANNED** · Priority: **P2** · Active effort: **3–4 hours**

Executor: **economy** · Review: **strong: displayed-message/read-cursor regression**

Dependencies: **Q01, Q04** · Merge locks: **messages-presentation**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MessagesPanel.tsx](../../../../apps/mobile/src/components/MessagesPanel.tsx): Conversation rows omit existing updated_at/blocked fields and the composer follows the full history.
- [apps/mobile/src/marketplaceApi.ts](../../../../apps/mobile/src/marketplaceApi.ts): Conversation already includes activity time, unread count and block state.

## Change

Use existing metadata for readable last-activity, unread and blocked states. Keep selected property context and a reachable composer/new-message action on narrow screens. Preserve the measured message viewport rather than replacing the read-state model.

## File scope

- `apps/mobile/src/components/MessagesPanel.tsx`
- `apps/mobile/tests/messages.test.tsx`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q36-AC01:** Overview shows meaningful status without needing a new last-message-preview API; long titles and empty inbox remain usable.
- **Q36-AC02:** New arrivals never force scrolling away from history; offscreen arrivals stay unread until displayed.
- **Q36-AC03:** Keyboard/composer layout and history paging preserve visible-message acknowledgements, retry IDs and foreground polling behavior.

## Verification

- npm run test:unit -- tests/messages.test.tsx; npm run typecheck.
- Owner/messages browser journey with long thread, offscreen arrival and narrow keyboard layout.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
