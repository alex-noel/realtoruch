# T20 handoff

## Identity and outcome

- Task: T20, web accessibility, layout and performance.
- Status: VERIFIED for the scoped local Chromium and production web export checks.
- Reviewed base: `7c8894b`.
- Implementation: `9601581` and navigation follow-up `ad9af7f`, created using `python3 scripts/commit.py` (matching author and committer metadata of 2021-11-11 23:41:07 CET and 23:43:57 CET, respectively). The evidence commit accompanies this handoff.
- Actual work and verification: 2026-11-11, Europe/Warsaw (CET, UTC+01:00).
- Renters can use the primary screens with enlarged text, navigate and dismiss dialogs by keyboard, and define search areas without using a pointer.
- The integrator approved limited edits to `App.tsx` and `theme.ts` and a coordinate alternative for the owner form. The desktop split default remains in place.

## Changed files and contracts

- `UI.tsx` and `web.css` use a named, browser-native modal with inert background, initial close focus, Tab containment, Escape and focus restoration. Fields can associate validation messages; toggle chips expose pressed state; focus outlines remain visible. The native Panel keeps its Modal, safe area, keyboard avoiding behavior and inbox scroll ref/key/callbacks.
- `App.tsx`, `theme.ts`, `Dialogs.tsx` and `ListingCard.tsx` wrap control rows, permit narrower inputs, improve contrast and announce result count changes. Text identifies direct and agency offers, unknown commission, seen, saved, compared and delisted homes. Web photos use native lazy loading, explicit dimensions and alt text; native still uses React Native Image.
- `MapDrawing.tsx` and `coordinates.ts` allow adding, editing, removing and clearing coordinates in a keyboard dialog. The editor and pointer drawing share a vertex model and the backend's geometry rules; the wire order remains `[longitude, latitude]`. The advert editor accepts coordinates as an alternative to the map pin and announces location status and invalid values.
- `DeferredPropertyMap.tsx` and `DeferredPropertyMap.web.tsx` separate map JavaScript from the web entry and preserve native import behavior. The existing marketplace chunk remains lazy.
- `accessibility.spec.ts` runs in the existing T18 harness. `web_budget.py` reads the actual production HTML entry and reports both entry and combined eager JavaScript. [The web baseline](../performance/web-baseline.md) records methods, raw measurements and limits.
- No migration, API shape, dependency lock or provider configuration changed. Existing search, identity, authentication and notification contracts remain in force.

## Acceptance evidence

| AC ID | Status | Test case | Command/run ID and evidence |
| --- | --- | --- | --- |
| T20-AC01 | PASS | T20-TC01 | `t20-final`, both Chromium projects. Search, filters, map, details/report, favorites, notifications, account, advert editor/publish controls and message composer at 320, 390, 768 and 1440 CSS px, each at 100% and 200% text size. No horizontal document overflow; essential actions scrolled into view. |
| T20-AC02 | PASS | T20-TC02 | `t20-final`, both projects. Opened listing with Enter; close received initial focus, Shift+Tab wrapped to the last action, Tab wrapped back, Escape closed and restored the listing trigger. |
| T20-AC03 | PASS | T20-TC03 | `t20-final`, both projects. Keyboard entered, edited and removed vertices; invalid latitude and too few points produced labelled errors. The real local SQL search returned the inside synthetic result and excluded the outside one. Clearing removed the polygon from the query. |
| T20-AC04 | PASS, scoped | T20-TC04 | `t20-final`, both projects. Active navigation and view toggles exposed as current and pressed; listing states distinct in grayscale; nine critical text measurements 5.47:1–9.54:1; visible 2 px focus outline. Contrast JSON and monochrome screenshot under `.local/verification/T20/t20-final/`. |
| T20-AC05 | PASS | T20-TC05 | `t20-final`, both projects. Network inspection verified map UI and Leaflet remained unloaded in initial narrow List view, marketplace loaded on open, and a far-offscreen photo loaded only after scrolling near it. Final entry 604,662 bytes ≤650,000. |
| T20-AC06 | PASS | T20-TC06 | `t20-final`, both projects. Three cold samples and 30 warm actions each; p95 48.3 ms and 48.7 ms, both ≤200 ms. Raw arrays, hardware and profile in the baseline and ignored T20 artifacts. |

## Verification

Commands used Node 24.6.0, Python 3.12.9, the locked Expo 58.0.23 / RN 0.88.1 / React Native Web 0.21.4 stack, Vitest 4.1.12 and installed Playwright 1.65.0 Chromium 158.0.8127.18. The browser harness ran offline with disposable SQLite files, loopback FastAPI/auth and a local file mail worker. Browser routes allow only the three run-owned origins and data URLs; the fixtures use synthetic accounts and messages. See the [web baseline](../performance/web-baseline.md) for machine configuration, throttle, sample counts and timestamps.

| Actual time (CET) | Work directory and exact invocation | Exit | Result |
| --- | --- | ---: | --- |
| 23:33–23:34 | `apps/mobile`: `VERIFY_RUN_ID=t20-first npm run test:e2e -- accessibility.spec.ts` | 1 | Web export succeeded; four passed, two failed, zero skipped. The first text-only multiplier gave an incorrect heading font by overriding its inline React Native Web style. The corrected multiplier now verifies the actual computed doubled size. |
| 23:35–23:36 | `apps/mobile`: `VERIFY_RUN_ID=t20-perf1 npm run test:e2e -- accessibility.spec.ts --grep T20-TC06` | 0 | Two passed, zero failed, zero skipped. Cold profile and warm budgets reproduced in both projects. |
| 23:36–23:37 | `apps/mobile`: `VERIFY_RUN_ID=t20-functional1 npm run test:e2e -- accessibility.spec.ts --grep-invert T20-TC06` | 1 | Eight passed, two failed, zero skipped. TC02–TC05 passed in both; TC01 exposed real header overflow at 320 px and navigation overflow at 768 px with doubled text. The header and navigation now wrap. |
| 23:39–23:40 | `apps/mobile`: `VERIFY_RUN_ID=t20-layout2 npm run test:e2e -- accessibility.spec.ts --grep T20-TC01` | 0 | Two passed, zero failed, zero skipped. No overflow after wrapping changes. Manually inspected the 320 px screenshot of the message composer at 200% text: the full textarea, Send message action and Close dialog were visible together. |
| 23:40 | Repository root: `python3 scripts/web_budget.py --output-dir .local/verification/T18/t20-layout2/dist` | 0 | Entry 604,567 bytes; all eager JS 608,607 bytes. An isolated HTML fixture also accepted exactly 650,000 bytes (exit 0), rejected 650,001 bytes (exit 1) and ignored a larger unreferenced lazy chunk. |
| 23:40 | `apps/mobile`: `npm run typecheck && npm run test:unit` | 0 | TypeScript passed, 64 unit tests passed, zero failed or skipped. Earlier development checks identified a stale symlink, a NodeList iteration type and a test-window type cast; all were corrected. |
| 23:43:30–23:46:06 | Repository root: `make verify-web ARGS='--run-id t20-final'` | 0 | Production web export and all 28 browser cases passed, zero failed or skipped. This includes all 16 predecessor cases and the 12 T20 cases. The navigation patch was in the tested checkout when this run started; its commit was recorded while the run was in flight, so the report correctly records the earlier HEAD with a dirty worktree. |
| 23:44 | Repository root: `python3 scripts/web_budget.py --output-dir .local/verification/T18/t20-final/dist` | 0 | Final entry 604,662 bytes; all eager JS 608,702 bytes. |
| 23:47 | `apps/mobile`: `npm run typecheck` | 0 | Passed after the navigation-state follow-up. |

Browser summaries and production exports are under `.local/verification/T18/<run-id>/`. The full regression result is `.local/verification/T01/t20-final/report.json`. Sanitized numeric and screenshot evidence is under ignored `.local/verification/T20/<run-id>/`. The existing browser harness retains only sanitized traces.

## Reproduction and review

- Open a listing with Enter, Tab and Shift+Tab through its actions and press Escape. The opening button should regain focus.
- Open Map view → Enter area coordinates. Invalid ranges show an associated error; valid points must be distinct and enclose a simple area. Use this area updates the ordinary search; Clear area removes the same filter. Pointer drawing still uses the same validation.
- Test compact and tablet navigation with text doubled. The header can grow vertically and compact navigation wraps; no essential action is hidden. The browser remains able to scroll each dialog body independently of its close control.
- Safely revert the scoped frontend files to roll back; no persisted state or migrations require recovery. Review the small App hunks alongside T21 and rerun the integrated web profile. There is no shared API change.

## Blockers and next action

No external gate for T20. This audit did not exercise installed iOS/Android, assistive technology hardware, alternate browser engines or a production catalog. No cloud resources, real mail or live map/provider requests were used. No push or deployment was performed.
