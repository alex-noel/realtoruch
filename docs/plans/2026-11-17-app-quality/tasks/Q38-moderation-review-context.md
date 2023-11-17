# Q38 Make moderation decisions contextual and deliberate

Status: **PLANNED** · Priority: **P1** · Active effort: **3–5 hours**

Executor: **economy** · Review: **strong: moderation action targeting and identity correction boundaries**

Dependencies: **Q03, Q27** · Merge locks: **moderation-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/components/MarketplaceDialog.tsx](../../../../apps/mobile/src/components/MarketplaceDialog.tsx): Original ReviewDesk shares one reason between all reports and sends hide/restore/merge/split immediately.

## Change

Use per-report reason state, explicit loading/error/empty states and selected report context. Show report age from the existing response. Confirm consequential actions with the affected home and source/target details; handle already-reviewed conflicts by refreshing safely.

## File scope

- `apps/mobile/src/components/ReviewDesk.tsx (from Q27)`
- `apps/mobile/src/marketplaceApi.ts (existing report fields only)`
- `apps/mobile/e2e/owner.spec.ts`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q38-AC01:** Editing one report reason never changes another; failed decisions preserve the intended row input.
- **Q38-AC02:** Hide/restore/merge/split confirmation names exactly what changes; cancellation makes no request and submission is single-flight.
- **Q38-AC03:** 401/403/409 produce safe recovery; normal users still cannot access the queue or grant themselves moderation; identity correction semantics remain unchanged.

## Verification

- npm run typecheck
- Local moderator/normal-user browser scenarios and existing moderation/identity regression checks for unchanged behavior.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No new merge/split algorithm, automatic decision, report-content disclosure or queue pagination in this task.
