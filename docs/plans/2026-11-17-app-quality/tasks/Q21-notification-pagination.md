# Q21 Make notification pagination and read actions reliable

Status: **PLANNED** · Priority: **P1** · Active effort: **4–6 hours**

Executor: **economy** · Review: **strong: cursor contract, ownership and ordering**

Dependencies: **Q03, Q18** · Merge locks: **notification-api, app-private-state, notification-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [backend/realtoruch/api.py](../../../../backend/realtoruch/api.py): Notification listing uses offset pagination.
- [apps/mobile/src/components/NotificationInbox.tsx](../../../../apps/mobile/src/components/NotificationInbox.tsx): Older notifications is inferred from item counts, with no request guard; read actions have no per-item pending state.

## Change

Publish an additive stable cursor/has-more contract based on existing ordered fields, retaining compatibility for current page callers. Consume it with guarded load-more and per-item read state. Do not change notification creation or delivery.

## File scope

- `backend/realtoruch/api.py (notification list only)`
- `backend/realtoruch/schemas.py (notification DTO only)`
- `apps/mobile/src/api.ts (notification method)`
- `apps/mobile/src/types.ts`
- `apps/mobile/src/App.tsx (notification handlers)`
- `apps/mobile/src/components/NotificationInbox.tsx`
- `docs/contracts/notifications.md (new)`
- `apps/mobile/src/hooks/useAccountCollections.ts (from Q18)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q21-AC01:** Insert new notifications between pages, including equal timestamps: stable ID tie-breaking keeps every older matching ID reachable once. Refreshing the head preserves the loaded older tail and continuation cursor; end-of-list is authoritative.
- **Q21-AC02:** Double-click load more issues one request; failure retains loaded rows and cursor, and retry recovers.
- **Q21-AC03:** Mark-read failure leaves unread state intact; refresh and pagination never mark other rows read or leak another account.

## Verification

- Add focused API pagination tests with interleaved insertion and ownership cases.
- npm run typecheck; focused inbox state/browser tests; run relevant real-service profile for the new query.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No new notification categories, mark-all-read behavior or delivery/alert-rule rewrite.
