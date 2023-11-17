# Q26 Expose the existing account data export

Status: **PLANNED** · Priority: **P1** · Active effort: **4–6 hours**

Executor: **economy** · Review: **strong: private data, token lifecycle and platform file cleanup**

Dependencies: **Q03, Q25** · Merge locks: **account-dialog, api-client, native-dependencies**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [backend/realtoruch/auth.py](../../../../backend/realtoruch/auth.py): /v1/auth/reauthenticate already issues a five-minute session-bound export token.
- [backend/realtoruch/account_data.py](../../../../backend/realtoruch/account_data.py): The bounded private export exists, but api.ts and AccountDialog expose no download/share action.

## Change

Add Export my data with password reauthentication, then a named JSON download on web or explicit share/save adapter on native. Reuse the existing export endpoint, limits and scope; use temporary files only when needed. Handle export-purpose-token 401 as export reauthentication, not global session invalidation; distinguish it from a truly invalid access session.

## File scope

- `apps/mobile/src/api.ts (export methods)`
- `apps/mobile/src/components/AccountDialog.tsx (export)`
- `apps/mobile/src/accountExport.web.ts (new)`
- `apps/mobile/src/accountExport.ts (new)`
- `apps/mobile/package.json (only required native adapter)`
- `apps/mobile/package-lock.json`
- `backend/tests/test_account_data.py`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q26-AC01:** Wrong password, expired export-purpose token, offline failure and oversized export show distinct safe recovery. Expired export authorization re-prompts for export password without signing out a valid account; invalid/revoked access still follows existing session rules.
- **Q26-AC02:** Password/token are cleared after use; private data/token never appear in URLs, logs, generic cache or persistent state; temporary files are cleaned after sharing/cancel.
- **Q26-AC03:** Existing own-user/session export restrictions remain unchanged; web file content and native adapter cleanup are verified, with installed native share acceptance reported separately.

## Verification

- npm run typecheck; new export adapter tests and browser download-content assertion.
- Run test_export_auth_scope_and_size and other export cases in backend/tests/test_account_data.py; add client regression proving purpose-token expiry preserves a valid session. Report required service prerequisites explicitly.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
