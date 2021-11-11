# T19 handoff

## Identity and outcome

- Task T19
- Status VERIFIED locally after parent integration review and browser correction. Installed native behavior remains unverified.
- Reviewed base `3bec9db82dff9747e5c65f6e28edd608b0c224d6`.
- Implementation commit accompanies this report, created with `python3 scripts/commit.py`.
- Work and unit verification took place on 2026-11-11, Europe/Warsaw (CET, UTC+01:00).
- Discover displays the selected city's collection status, keeps usable same-city results visible during refresh and offers retry after a search or status failure.
- The integrator approved a scoped Playwright spec in the existing T18 harness and confirmed Apply-only numeric drafts. The existing T14 Vitest runner was used. The temporary copy of the integrator's Vitest test include configuration is outside this patch.

## Changed files and contracts

- `apps/mobile/src/components/SourceStatus.tsx` shows up to six providers with city-scoped statuses and an accessible timestamps control. It keeps complete success, latest attempt and last stored observation separate. It uses the configured cadence, validates UTC timestamps and displays fixed status text for known error categories.
- `apps/mobile/src/hooks/useListingSearch.ts` normalizes city aliases and text, independently cancels and fences requests for listings, source status and market summary, and retains a dated snapshot for same-city replacement and retry. Search input uses a 250 ms debounce. Apply, polygon completion, pagination and explicit retry submit immediately. Existing numeric inputs hold a draft until Apply and issue zero searches on typing or cancel.
- `apps/mobile/src/App.tsx` connects the search state, filters, status, retry controls and logout handling. Account favorite membership comes from the existing favorites list endpoint. The app reads seen state for visible canonical IDs in batches of up to 100 via the existing listing-state endpoint and fences publication by account generation. Guest seen data stays separate.
- `apps/mobile/src/api.ts` reads city source status through `GET /v1/sources?city=…`. Listing search, source status and summary use anonymous requests, so sign-out cannot invalidate public work. The shared transport composes caller cancellation with a 12-second deadline across request, refresh wait and retry. An abandoned waiter leaves shared refresh running. A logout that already owns the cookie lock holds it until its started rotation settles under the rotation's own 12-second deadline and checks the logout deadline before retrying.
- `apps/mobile/src/types.ts` adds projections of the existing T12 public source health types. No API response, schema, migration, package lock or provider configuration changed.
- `apps/mobile/tests/sourceStatus.test.ts`, `apps/mobile/tests/searchLifecycle.test.ts` and `apps/mobile/e2e/source-status.spec.ts` cover classification, timers, stale responses, request counts, account cleanup and the 320 px browser controls.

## Acceptance evidence

| AC ID | Status | Test cases | Evidence |
| --- | --- | --- | --- |
| T19-AC01 | PASS | TC01, TC02 | Unit cases check fixed copy for all state categories and no exception detail in the view model. Mounted rendering passed in the parent browser checks. |
| T19-AC02 | PASS | TC01, TC02 | Unit checks stale previous success, inclusive freshness boundary, invalid cadence, impossible/missing/future times and disabled OLX with one stored advert. |
| T19-AC03 | PASS | TC03, TC04 | Independent request generations reject late Kraków results and status in unit barriers. The mounted browser check passed in the parent run. |
| T19-AC04 | PASS | TC04, TC05 | Unit checks one batch of 50 and batches of 100/100/1 for 201 unique IDs, cleanup before/after dispatch and late authenticated response fencing. The mounted browser check passed in the parent run. |
| T19-AC05 | PASS | TC05, TC06 | Unit and parent browser checks verify late private state is fenced on logout, public filters/results remain, and offline results retain an age and usable retry. |
| T19-AC06 | PASS, web | TC06 | Parent Chromium checks passed keyboard retry, timestamps, expanded state and zero horizontal document overflow at 320 px. No runtime dependency added. |

| Test case | Status | Evidence |
| --- | --- | --- |
| T19-TC01 | PASS | 10:00 success with one-hour cadence, 12:00 failure and 12:01 clock produces failed/delayed with separate timestamps. |
| T19-TC02 | PASS | Disabled OLX with one stored advert and no health shows unavailable automatic collection and unknown freshness. |
| T19-TC03 | PASS | Separate signal and generation barriers accept Warszawa then release late Kraków. Mounted App browser checks passed. |
| T19-TC04 | PASS | Fake clock issues one search at 250 ms after the twentieth edit and one 50-ID read. Mounted App browser checks passed. |
| T19-TC05 | PASS | Scheduler cleanup suppresses pending/late callbacks and logout fences a late private request. Mounted App browser checks passed. |
| T19-TC06 | PASS | The parent targeted browser run passed offline retry, timestamps, accessible expanded state and viewport width in both profiles. |

## Verification

Commands run from `apps/mobile` with `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH` on macOS. Locked install used `npm ci --offline --no-audit` and installed 584 packages. TypeScript 5.9 and Vitest 4.1.12 came from the lock.

| Actual time (CET) | Command | Exit | Result |
| --- | --- | --- | --- |
| 23:08:05 | `npm run test:unit -- sourceStatus searchLifecycle` | 0 | 31 passed, 0 failed, 0 skipped |
| 23:08:06 | `npm run test:unit` | 0 | 51 passed, 0 failed, 0 skipped, including 20 T14 session tests |
| 23:08 | `npm run typecheck` | 2 | First pass identified nullable URL in the browser test's injected fetch wrapper |
| 23:08–23:09 | `npm run typecheck` | 0 | Fixed narrowing. Typecheck completed. |

Transport tests use synthetic account tokens and fake clocks. They check the caller/deadline/combined cancellation paths and listener cleanup. A simulated browser lock outlives the first request's deadline, then the later sibling uses the rotated token with its own original deadline. The logout lock test keeps the lock held through started rotation after the original deadline and confirms no late retry.

## Reproduction and review

- Fill City with Warszawa while delaying Kraków listing and status responses. Release Kraków only after both Warszawa panels render. Type 20 characters and observe one listing request after debounce.
- Load a city, apply a rent and area filter with the catalog request set offline, then activate Retry search. Same-city results are usable and display their load age while the request fails.
- Review T17's temporary transport helper at integration. The shared deadline now supplies its core behavior. Preserve its per-thread request cancellation, account fencing and user-facing error behavior.
- Safe rollback is the frontend patch. No database recovery or service configuration is required.

## Blockers and next action

The parent browser evidence below closes the local browser gate. The browser spec uses intercepted synthetic listings and source responses, plus the isolated local auth service for logout. Installed native behavior remains unverified. This work used no cloud resources, real mail or live provider requests.

## Integrator review in progress

The parent reviewed request generation, normalized city boundaries, private-state clearing and the deadline/refresh interaction. The staged integration includes T17's inbox. Its temporary timeout wrapper is now removed: inbox calls pass their original caller signal to the shared request transport, which owns the deadline. The integration test exercises actual shared transport cancellation and timeout through `market.thread` and `market.conversations`, replacing the earlier wrapper-only mock timer test. All **64 frontend unit tests passed, 0 failed, 0 skipped**, at actual CET 2026-11-11 23:10:29. The complete browser check remains pending the isolated T25 measurement window; this unit result does not close AC05 or AC06.

## Browser correction and acceptance

The complete root `make verify-web ARGS='--run-id integrated-t19-final'` run on 2026-11-11 22:16:35–22:18:29 UTC produced **14 passed, 2 failed, 0 skipped**. All twelve existing journeys and both new city/batch/logout cases passed. Both 320 px cases failed because React Native Web does not translate nested `accessibilityState.expanded` to `aria-expanded`. The parent changed the timestamp toggle to the explicit `aria-expanded` prop, which the installed React Native native typings also support. No assertion was weakened.

With root `.venv/bin` and Node24.6.0 on PATH and the installed Playwright cache, `VERIFY_RUN_ID=integrated-t19-320b npm run test:e2e --prefix apps/mobile -- -g '320 px retains'` passed **2 tests, 0 failed, 0 skipped**, on 2026-11-11 UTC. Both tests ran at320 px and verified keyboard timestamps, expanded state, numeric draft cancel/Apply behavior, offline retained results, retry, and document width. Evidence is `.local/verification/T18/integrated-t19-320b/summary.json`; the failed combined run is preserved under `.local/verification/T01/integrated-t19-final/report.json`. An initial targeted invocation used system Python and failed before starting services due to missing Pydantic; the rerun used the correct virtual environment. This is focused correction evidence, not a claim that the earlier16-case run passed. The final integrated release profile will exercise all cases together again.
