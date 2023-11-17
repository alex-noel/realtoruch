# Q23 Check push capability before requesting permission

Status: **PLANNED** · Priority: **P1** · Active effort: **3–4 hours**

Executor: **economy** · Review: **strong: subscription ownership and logout behavior**

Dependencies: **Q22** · Merge locks: **push-adapters, notification-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/pushClient.web.ts](../../../../apps/mobile/src/pushClient.web.ts): enablePush prompts permission before server configuration lookup; pushEnabled trusts a localStorage ID.
- [apps/mobile/src/pushClient.ts](../../../../apps/mobile/src/pushClient.ts): Native enabled state also relies on a stored marker.

## Change

Check server and platform capability first. Reconcile stored markers with real permission/subscription state where the platform exposes it; represent unavailable, denied, available, pending and subscribed states accurately.

## File scope

- `apps/mobile/src/pushClient.web.ts`
- `apps/mobile/src/pushClient.ts`
- `apps/mobile/src/components/NotificationInbox.tsx (device preference)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q23-AC01:** Disabled server configuration or unsupported browser causes no permission prompt; only an explicit user action requests permission.
- **Q23-AC02:** A stale local marker does not falsely show working alerts; failed registration has a recoverable state without duplicate subscriptions.
- **Q23-AC03:** Disable and logout retain revocation behavior; denied permission explains settings recovery without repeated prompts.

## Verification

- Fake permission/config/subscription adapter tests on both platforms; npm run typecheck.
- Local browser smoke; no external push send is needed or claimed.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
