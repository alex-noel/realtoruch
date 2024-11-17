# Task handoff

Task: Q19 — resume saving after sign in and clarify saved searches

Status: VERIFIED_LOCAL

Base revision: `07e2950` (Q05, with Q07/Q18 integrated in its ancestry). Branch: `codex/q05-discovery-shell`. Resulting revision: amended Q19 task commit, reported to the integrator.

## Result

Save search captures the current filters, including a drawn polygon, before asking a guest to sign in. After authentication the editable naming panel reopens with those exact filters and a useful city/constraint name; closing either auth or naming without saving creates no record. Saved searches show the constraints returned by the API. Deletion now requires confirmation naming the selected search, keeps failures on that row with a retry action, and tracks busy state per row.

Changed files: `apps/mobile/src/App.tsx` and `apps/mobile/e2e/journey.spec.ts`. The browser journey covers guest polygon continuation, a canceled guest sign-in, a silent existing-match baseline, persisted constraint display, canceling deletion, an injected transient delete failure, retry, and preservation of a second search. A delayed deletion from account A is released after sign-out and account B opens a new naming dialog; the stale response cannot change B's dialog or draft. Synthetic saved-search screenshots: [mobile](Q19-mobile-saved-searches.png) and [desktop](Q19-desktop-saved-searches.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q19-AC01 | PASS | Journey draws a polygon as a guest, opens Save search, registers, and verifies the naming panel’s filter summary still includes price, area, Direct offers, and Drawn map area. Separate test closes guest auth, registers, and confirms the saved-search list is empty. |
| Q19-AC02 | PASS | Journey confirms exactly one saved row after the first save; its displayed filters are returned from persisted search filters. The existing synthetic home predates the search and the fixture reports no notices after save (silent baseline). |
| Q19-AC03 | PASS | Journey cancels named confirmation and confirms the row remains; then injects a 503, verifies the row error/retry action, retries successfully, and verifies only the selected search is gone. A delayed removal released after account switch returns 401 and does not alter the next account's open draft. |

## Verification

| Actual command and working directory | Exit code | Result | Evidence path |
| --- | ---: | --- | --- |
| `npm run typecheck` from `apps/mobile` with Node 24.6.0 | 0 | Passed | — |
| `VERIFY_RUN_ID=q19-reviewed-final-20261117-1755 npm run test:e2e -- journey.spec.ts` from `apps/mobile` with Node 24.6.0 and `.venv` activated | 0 | 6 tests passed (desktop/mobile) | `.local/verification/T18/q19-reviewed-final-20261117-1755/` |

Evidence recorded 2026-11-17. The browser journey uses the repository's isolated local services, synthetic account/listing data, and an injected local 503 for failure recovery. No external checks were required.

## Compatibility and review

No API, schema, configuration, or dependency changes. The save operation continues to call the existing endpoint once with the captured filter object; no alert-baseline behavior changed. Deletion uses the existing endpoint and refreshes only saved-search collection state. Save/delete completions check the captured session generation and account before updating UI state; duplicate in-flight operations are fenced synchronously. Account transitions clear row errors, busy state and confirmation UI while preserving only the guest intent during sign-in's initial signed-out event. Final integration review is pending.

## Remaining work

None for local Q19 acceptance. Parent integration review remains pending.
