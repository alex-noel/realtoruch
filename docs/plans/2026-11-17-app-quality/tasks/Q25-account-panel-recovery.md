# Q25 Make account and device management recoverable

Status: **PLANNED** · Priority: **P1** · Active effort: **2–4 hours**

Executor: **economy** · Review: **strong: preserve device/session and deletion boundaries**

Dependencies: **Q03, Q24** · Merge locks: **account-dialog**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/AccountDialog.tsx](../../../../apps/mobile/src/components/AccountDialog.tsx): Account and sessions are fetched together; failure leaves no explicit loading or section retry.

## Change

Load identity and device sessions independently with section-specific retry. Separate account, security and destructive actions visually. Refresh verification status after returning from a verification link and keep device revocation feedback local.

## File scope

- `apps/mobile/src/components/AccountDialog.tsx (account/session sections)`
- `apps/mobile/e2e/boundaries.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q25-AC01:** A failed devices request does not hide account identity; a failed identity request cannot imply an empty verified account.
- **Q25-AC02:** Current device is labelled; revocation disables only its operation and failure leaves the device available for retry.
- **Q25-AC03:** Verification refresh and sign-out retry are reachable; loading/error states do not overlap navigation or deletion controls at 320 px.

## Verification

- npm run typecheck
- Browser independent load failures, verification refresh, revoke failure and sign-out retry.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
