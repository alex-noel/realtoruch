# Q22 Show truthful email preference loading and recovery

Status: **PLANNED** · Priority: **P1** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **Q18** · Merge locks: **notification-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/NotificationInbox.tsx](../../../../apps/mobile/src/components/NotificationInbox.tsx): Preference lookup errors are swallowed; defaults look like a confirmed disabled preference and can retain another user state.

## Change

Represent unknown/loading/failed/disabled/confirmation-pending/enabled states explicitly. Show channel-specific retry and keep toggles unavailable until authoritative preferences load.

## File scope

- `apps/mobile/src/components/NotificationInbox.tsx (email preference)`
- `apps/mobile/tests/notificationPreferences.test.tsx (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q22-AC01:** A failed lookup never claims email alerts are off; retry loads the true state.
- **Q22-AC02:** Failed updates retain the last confirmed value and explain recovery; confirmation pending remains distinct from enabled.
- **Q22-AC03:** Switching account clears old email/preferences immediately; late load or mutation responses cannot update the new account.

## Verification

- New delayed/error/account-switch preference tests; npm run typecheck.
- Journey browser confirmation/resend/disable flow using file mail only.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
