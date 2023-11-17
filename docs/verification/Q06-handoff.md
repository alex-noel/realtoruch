# Task handoff

Task: Q06 Fix decimal and range input in filters

Status: IMPLEMENTED_LOCAL

Base revision: `9c636cd` · branch: `codex/q06-filter-validation` · resulting commit: see branch HEAD

## Result

Filter numeric inputs remain editable text until Apply. Area fields accept a comma or dot decimal separator; rent fields require whole PLN values. Invalid formats and incompatible bounds keep the dialog open and show errors on the affected fields. Equal rent bounds are rejected because the maximum is exclusive, while equal area bounds are accepted.

Changed files:

- `apps/mobile/src/filterNumbers.ts` — strict, pure numeric parsing.
- `apps/mobile/src/components/Dialogs.tsx` — FilterDialog raw draft, validation, field errors, and parsed apply values.
- `apps/mobile/tests/filterNumbers.test.ts` — parser regression cases.
- `apps/mobile/e2e/boundaries.spec.ts` — focused filter validation on desktop and mobile.
- `apps/mobile/e2e/accessibility.spec.ts` — T20-TC01 assertions now verify field-specific errors and accessible descriptions.

No screenshots were needed for this validation behavior change. No scope expansion.

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q06-AC01 | PASS | `filter number parsing` tests cover comma/dot decimals and reject malformed separators, negatives, nonfinite text, scientific notation, partial values, decimals in integer rent, and unsafe integer PLN above `Number.MAX_SAFE_INTEGER`. Browser test confirms `50,5` and `50.5` become `50.5` in the submitted request. |
| Q06-AC02 | PASS | Browser test rejects equal rent bounds with field-specific errors, then accepts equal area bounds and submits both as `50.5`. Rent applies `max_price_exclusive=true`. |
| Q06-AC03 | PASS | Parser test confirms whitespace is unset. Browser test confirms errors are on the rent fields, correcting rent clears the errors, and the area drafts remain unchanged and are applied. |

## Verification

Recorded 2026-11-17 15:43 CET; Node v24.6.0; Python 3.12 from the checkout virtual environment.

| Actual command and working directory | Exit code | Result | Evidence |
| --- | ---: | --- | --- |
| `npm run typecheck` from `apps/mobile` | 0 | Passed | TypeScript check completed. |
| `npm run test:unit -- tests/filterNumbers.test.ts` from `apps/mobile` | 0 | Passed, 3 tests | Vitest reports 1 file and 3 tests passed. |
| `VERIFY_RUN_ID=q06-validation-20261117-1539 npm run test:e2e -- boundaries.spec.ts -g 'filter validation'` from `apps/mobile` with `.venv` active | 0 | Passed, 2 tests | Playwright focused browser regression passed in desktop and mobile projects. Run data is isolated at `.local/verification/T18/q06-validation-20261117-1539/`. |
| `VERIFY_RUN_ID=q06-tc01-20261117-1543 npm run test:e2e -- accessibility.spec.ts -g 'T20-TC01'` from `apps/mobile` with `.venv` active | 0 | Passed, 2 tests | Existing accessibility regression passed in desktop and mobile projects with field-level error and accessible description assertions. Run data is isolated at `.local/verification/T18/q06-tc01-20261117-1543/`. |
| `git diff --check` from checkout root | 0 | Passed | No whitespace errors. |

The browser runner uses disposable loopback services and an isolated SQLite fixture. No external services were used.

## Compatibility and review

No API, schema, configuration, dependency, or lockfile changes. The emitted filter fields retain the existing `Filters` contract, and `max_price_exclusive` remains true. Parsing and validation remain client-side; backend rent semantics were not changed. Rent parsing rejects values outside JavaScript's safe integer range to avoid silently rounded PLN. The existing filter fields and nonnumeric draft options remain intact. Required standard parent review is pending.

## Remaining work

Parent review and integration remain. No known local defects or blockers.
