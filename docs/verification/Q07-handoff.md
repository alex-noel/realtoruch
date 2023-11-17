# Task handoff

Task: Q07 Expose active filters and predictable reset actions

Status: IMPLEMENTED_LOCAL

Base revision: Q06 `e7de3567c5f074bd186559094336b7b63c3fd1e5` · branch: `codex/q06-filter-validation` · resulting commit: see branch HEAD

## Result

Discovery now shows a removable summary for every active search constraint, including the default Apartments constraint. The Filters badge counts deviations from the documented filter defaults (city and sort are context/order, not filter deviations), and the same summary helper renders saved-search criteria. Rent ceiling labels follow the stored inclusive/exclusive flag, and area labels preserve the exact value. “All property types” has no summary chip because it adds no constraint. Both reset actions restore defaults while retaining the selected city and clearing text and polygon constraints.

Changed files:

- `apps/mobile/src/filterSummary.ts` — summary labels, deviation count, single-constraint removal, and city-preserving reset helpers.
- `apps/mobile/src/App.tsx` — discovery summaries/badge, saved-search summaries, removable constraints, and current-city empty-state recovery.
- `apps/mobile/src/components/Dialogs.tsx` — FilterDialog Reset filters action.
- `apps/mobile/tests/filterSummary.test.ts` — summary/count, removal, and reset helper cases.
- `apps/mobile/e2e/boundaries.spec.ts` — browser workflow for summaries, removal, and current-city reset.

No screenshots were needed for this behavior change. No unrelated scope expansion.

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q07-AC01 | PASS | `filter summaries and reset behavior` verifies Apartments is visible with zero deviations and summaries include base rent, area, Direct offers, explicitly zero commission, risk, and drawn area. Saved-search cards reuse the same summary helper. |
| Q07-AC02 | PASS | Browser test removes only the rent minimum while preserving query, area, property type, and Warszawa; the subsequent search is page 1. Both empty-state and FilterDialog Reset filters actions restore apartment defaults, clear query/polygon, retain Warszawa, and show Filters (0). |
| Q07-AC03 | PASS | Browser workflow reaches an empty Warszawa result, verifies the recovery copy explains apartments are the default, and resets into apartments in Warszawa rather than Kraków. |

## Verification

Recorded 2026-11-17 15:55 CET; Node v24.6.0; Python 3.12 from the checkout virtual environment.

| Actual command and working directory | Exit code | Result | Evidence |
| --- | ---: | --- | --- |
| `npm run typecheck` from `apps/mobile` | 0 | Passed | TypeScript check completed after App and FilterDialog updates. |
| `npm run test:unit -- tests/filterSummary.test.ts` from `apps/mobile` | 0 | Passed, 6 tests | Vitest reports 1 file and 6 tests passed, including inclusive rent ceiling, full decimal precision, and all-types omission cases. |
| `VERIFY_RUN_ID=q07-review-20261117-1600 npm run test:e2e -- boundaries.spec.ts -g 'filter summaries'` from `apps/mobile` with `.venv` active | 0 | Passed, 2 tests | Focused Playwright workflow passed in desktop and mobile projects. Run data is isolated at `.local/verification/T18/q07-review-20261117-1600/`. |
| `VERIFY_RUN_ID=q07-tc01-20261117-1555 npm run test:e2e -- accessibility.spec.ts -g 'T20-TC01'` from `apps/mobile` with `.venv` active | 0 | Passed, 2 tests | Existing responsive accessibility regression passed in desktop and mobile projects at documented widths and 200% text size. Run data is isolated at `.local/verification/T18/q07-tc01-20261117-1555/`. |
| `git diff --check` from checkout root | 0 | Passed | No whitespace errors. |

The browser runner uses disposable loopback services; the Q07 search responses are synthetic and local. No external services were used.

## Compatibility and review

No API, schema, configuration, dependency, or lockfile changes. Constraint removals reuse `changeFilters`, which resets pagination. The helper excludes city and sort from filter-deviation counts so reset can retain the selected city and filter counts can accurately return to zero; property type `apartment` remains visible as a default constraint. Saved-search copy says “Applied filters” without exposing the deviation count. No session, privacy, or visibility state is touched. Required standard parent review is pending.

## Remaining work

Parent review and integration remain. No known local defects or blockers.
