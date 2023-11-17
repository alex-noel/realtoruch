# Q40 Verify the integrated app and reconcile remaining gates

Status: **PLANNED** · Priority: **P1** · Active effort: **4–6 hours**

Executor: **experienced** · Review: **strong: independent integration and evidence review**

Dependencies: **Q39** · Merge locks: **integration, release-docs**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [docs/release-readiness.md](../../../release-readiness.md): Current LOCAL_PARTIAL evidence validates the prior candidate, not future quality changes.
- [docs/testing.md](../../../testing.md): Some instructions still describe already-existing T14/T18 commands as future work.
- [docs/plans/2026-11-12-two-week-sprint/execution.json](../../2026-11-12-two-week-sprint/execution.json): Old operational status needs reconciliation; elapsed time cannot complete a soak.

## Change

On the integrated revision, verify renter and owner journeys end to end, run the appropriate final local profiles and update documentation from actual results. Inspect the existing soak manifest read-only and reconcile its evidence without relabeling old-pin data. Produce separate local implementation and external acceptance statuses.

## File scope

- `docs/feature-status.md`
- `docs/release-readiness.md`
- `docs/testing.md`
- `docs/mobile-validation.md`
- `docs/verification/Q40-quality-handoff.md (new)`
- `docs/plans/2026-11-17-app-quality/execution.json`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q40-AC01:** Renter: filter/draw/save after login/favorite/detail/compare/notification/unavailable favorite. Owner: validate/draft/preview/upload/order/publish/conflict/message/withdraw/appeal. Export and sign-out private-state cleanup also pass.
- **Q40-AC02:** Reports identify real revision, commands, pass/fail/skip counts and actual wall-clock dates; failed targets are not waived and screenshots do not substitute for behavior.
- **Q40-AC03:** Remaining real mail/push, map-provider, installed-device/assistive-technology, corrected-parser/72-hour collection, OLX and cloud gates have exact missing inputs and owners; no deployment or external sends happen as part of this task.

## Verification

- make verify; make verify-services; make verify-web on the final integrated candidate with unique run IDs.
- Q39 cross-browser smoke, scripts/web_budget.py on that export, and iOS/Android JS export; retain ≤650000-byte entry and ≤200ms warm p95 unless a reviewed change explicitly revises the existing budget.
- Read-only soak aggregation; do not start collectors, resend mail or modify the old experiment.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No push, deployment, live provider validation, message email rollout or claim of production readiness from local tests.
