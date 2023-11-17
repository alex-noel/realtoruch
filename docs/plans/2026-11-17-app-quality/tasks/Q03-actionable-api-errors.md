# Q03 Preserve safe actionable API errors

Status: **PLANNED** · Priority: **P1** · Active effort: **3–4 hours**

Executor: **economy** · Review: **strong: error disclosure and session boundary**

Dependencies: **None** · Merge locks: **api-client**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/api.ts](../../../../apps/mobile/src/api.ts): validationMessage recognizes only a few login strings and email/password/name fields.
- [backend/realtoruch/marketplace.py](../../../../backend/realtoruch/marketplace.py): Version conflicts, verification requirements and cooldowns already have distinct server failures.

## Change

Define a bounded route/status/known-error mapping for version conflict, verification required, rate limits, saved-search limits and validation fields. Expose structured recoverable categories to UI consumers without displaying arbitrary server text. Preserve the existing refresh and sign-out paths.

## File scope

- `apps/mobile/src/api.ts`
- `apps/mobile/src/marketplaceApi.ts`
- `apps/mobile/tests/session.test.ts`
- `docs/contracts/client-errors.md (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q03-AC01:** Known failures lead to useful recovery text and typed categories; unknown errors retain a safe generic fallback.
- **Q03-AC02:** Server input echoes, HTML, credentials and private identifiers never enter displayed error text.
- **Q03-AC03:** 401 refresh/replay, cancellation and account-switch regression tests remain green; a 409 does not log out the user.

## Verification

- npm run test:unit -- tests/session.test.ts
- Add response-fixture cases for each mapped error and malicious unknown text; npm run typecheck.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
