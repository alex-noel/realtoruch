# Q39 Add focused visual and cross-browser quality coverage

Status: **PLANNED** · Priority: **P1** · Active effort: **4–6 hours**

Executor: **economy** · Review: **strong: visual baseline approval and coverage claims**

Dependencies: **Q01, Q02, Q03, Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11, Q12, Q13, Q14, Q15, Q16, Q17, Q18, Q19, Q20, Q21, Q22, Q23, Q24, Q25, Q26, Q27, Q28, Q29, Q30, Q31, Q32, Q33, Q34, Q35, Q36, Q37, Q38** · Merge locks: **browser-tests, frontend-test-dependencies**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/playwright.config.ts](../../../../apps/mobile/playwright.config.ts): Both projects use Chromium, one at a mobile-sized viewport.
- [apps/mobile/e2e/accessibility.spec.ts](../../../../apps/mobile/e2e/accessibility.spec.ts): Good geometry/focus/text checks exist, but reviewed screenshot baselines do not.

## Change

Add a small deterministic screenshot set for discovery, detail, saved homes, owner editor and messages at 390 and 1440 px, reviewed before baselining. Add a tagged WebKit/Firefox functional smoke profile for discovery/filter, sign-in/restore, detail, saved action and one owner/message flow. Keep existing performance cases Chromium-only.

## File scope

- `apps/mobile/playwright.config.ts`
- `apps/mobile/e2e/run.py`
- `apps/mobile/e2e/quality.spec.ts (new)`
- `apps/mobile/e2e/quality.spec.ts-snapshots (new)`
- `docs/verification/Q39-quality.md (new)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q39-AC01:** Use synthetic catalog, local photos/tiles and fixed clock; screenshots contain no real accounts, tokens or mail.
- **Q39-AC02:** A deliberately introduced overlap fails the baseline check; revert the fault before handoff; never bulk-accept diffs just to pass.
- **Q39-AC03:** Browser binaries and results are reported honestly; missing engines are blocked, not passed or silently skipped; responsive Chromium is not described as installed mobile.

## Verification

- Run the new focused profile on installed Chromium/WebKit/Firefox; npm run typecheck.
- Run existing accessibility suite for 320/390/768/1440 px and 200% text, retaining keyboard polygon and modal checks.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No unrelated refactor, framework upgrade or backend behavior change.
