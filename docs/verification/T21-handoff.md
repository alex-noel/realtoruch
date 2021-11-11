# T21 handoff

## Identity and outcome

- Task T21
- Status VERIFIED for the local T21 scope. Installed-device behavior and domain association are deferred to T22.
- Reviewed base `a2f53d5`.
- Implementation commit accompanies this report, created with `python3 scripts/commit.py`.
- Work and verification took place on 2026-11-11, Europe/Warsaw (CET, UTC+01:00).
- Native initial and warm links use the same allowlisted routing as existing web and browser push links. Protected destinations can resume after sign-in. Account-link failures offer safe messages and explicit retries.
- The integrator approved the narrow token-error mapping in `api.ts` and the browser spec in the existing T18 harness.

## Changed files and contracts

- `apps/mobile/src/linking.ts` defines the typed parser, browser URL scrubbing, native subscription and lifecycle. It validates exact origin or custom scheme, root route, identifier, token length and percent encoding. It limits each URL to one action. The lifecycle keeps only a typed safe protected destination through sign-in. It suppresses duplicate in-flight and successful token actions in memory. A transient failure can be retried or reopened after another destination.
- `apps/mobile/src/App.tsx` dispatches existing listing, advert, push and account links, as well as protected saved-home and Notifications links. It waits for initial session restore before prompting for protected routes. It routes hydrated alias-resolved listings through the existing detail/seen flow. Explicit email-token calls disable session refresh and retry at the request layer.
- `apps/mobile/src/api.ts` maps endpoint-bound verify, reset, confirmation and unsubscribe errors to fixed copy. The reset form continues to use its existing Change password action for retry.
- `apps/mobile/app.config.js` and `apps/mobile/.env.example` expose the custom scheme, public HTTPS app origin and Android Maps client-key configuration. Existing app identifiers and dependency locks are preserved. No domain association files were generated.
- `apps/mobile/tests/linking.test.ts` and `apps/mobile/e2e/linking.spec.ts` cover parser allowlisting, startup and warm races, protected navigation, retry, reset errors, URL scrubbing and session preservation. Browser token traces are disabled.
- `docs/mobile-validation.md` records the route inventory, configuration, JS export commands and installed-build handoff to T22.
- No database, migration, backend endpoint, environment secret, package or service configuration changes.

## Acceptance evidence

| AC ID | Status | Test cases | Evidence |
| --- | --- | --- | --- |
| T21-AC01 | PASS | TC01 | Vitest accepts each documented route and rejects untrusted origins, schemes, extra actions and invalid encodings. |
| T21-AC02 | PASS | TC02 | Deterministic initial/warm barriers and handler teardown pass in the shared lifecycle. Installed native delivery remains deferred. |
| T21-AC03 | PASS | TC03, TC04 | Vitest proves pending safe destination resume and active-session retention on transient and invalid token responses. Both Chromium profiles verify login resume and an active account after link failure and retry. |
| T21-AC04 | PASS | TC04 | Unit sanitizer and request tests pass. Both Chromium profiles check the URL, history state, local and session storage, console and rendered text for absence of synthetic token values. |
| T21-AC05 | PASS | TC05 | Local SQLite verifies alias resolution and canonical favorite preservation. Both Chromium profiles open an intercepted retained alias, mark its canonical ID seen and verify discovery exclusion. The native link source is covered by unit fixtures. |
| T21-AC06 | PASS | TC06 | Final placeholder export emitted one Hermes bundle per platform. Resolved config has the default scheme and app IDs without association fields. |

| Test case | Status | Evidence |
| --- | --- | --- |
| T21-TC01 | PASS | Table checks all query and fragment routes, configured HTTPS/native schemes, actual browser origin, loopback development, hostile schemes/hosts, encoded separators, duplicates and bounds. |
| T21-TC02 | PASS | Cold and warm copies of one token cause one consumption. Warm-first duplicates and distinct early events are tested. Unmount removes the subscription and ignores late work. Both Chromium profiles coalesce duplicate warm push delivery; a later intentional listing reopening is covered by unit tests. |
| T21-TC03 | PASS | Protected destination waits through restore and resumes once after sign-in. Cancellation clears the pending action. Both Chromium profiles retain an active account on a transient verification failure and complete the explicit retry. |
| T21-TC04 | PASS | Expired/used reset errors and a transient retry are tested. A stale retry callback and duplicate token action cannot consume again after success. Both Chromium profiles verify the expired reset message, transient retry and fragment removal without exposing the token. |
| T21-TC05 | PASS | Local SQLite resolves an old alias after a canonical merge. Both Chromium profiles use a synthetic inactive alias response and local sign-in to open the canonical detail, mark that ID seen, and verify the retained home is absent from discovery. A native URL fixture uses the same typed destination and dispatcher. |
| T21-TC06 | PASS | Final iOS and Android JS exports and resolved config checks passed. Native install and association checks remain deferred to T22. |

## Verification

Node v24.6.0, Expo ~58.0.23, React Native 0.88.1, Vitest 4.1.12. All paths below are relative to the T21 worktree. Frontend commands use `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH`. Python checks use the repository's Python 3.12 environment with the T21 backend on `PYTHONPATH`.

| Actual time (CET) | Working directory | Command | Exit and result |
| --- | --- | --- | --- |
| 23:11 | `apps/mobile` | `npm ci --offline --no-audit` | 0, locked dependencies installed |
| 23:16–23:17 | root | `python3 scripts/mobile_check.py --help` then `python3 scripts/mobile_check.py` | 0 with the Python 3.12 environment. The initial system-Python invocation failed because it lacked `dotenv`. Prerequisite report confirms Node and CocoaPods, with Xcode selection, Android platform tools, Android Maps key and production HTTPS endpoints missing in this local configuration. |
| 23:17:00–23:17:06 | `apps/mobile` | Load `.env.example` via `set -a; . ./.env.example; set +a`, then with `CI=1 EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 EXPO_UNSTABLE_HEADLESS=1`, run `npm exec --offline -- expo config --type public --json` and `npm exec --offline -- expo export --platform ios --platform android --output-dir ../../.local/verification/T21/native-local/native` | 0 for each. One iOS and one Android Hermes bundle and one export metadata file. |
| 23:22–23:23 | root | `PYTHONPATH="$PWD/backend" /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest -q backend/tests/test_identity_review.py::test_manual_merge_preserves_favorites_seen_history_and_old_links` | 0, 1 passed, 0 failed, 0 skipped. Existing Starlette test-client deprecation warning. |
| 23:24:20 | `apps/mobile` | `npm run test:unit -- linking session` | 0, 71 passed, 0 failed, 0 skipped |
| 23:25:59 | `apps/mobile` | `npm run test:unit` and `npm run typecheck` | 0 for each. 84 unit tests passed, 0 failed, 0 skipped. |
| 23:31:23 | `apps/mobile` | `npm run test:unit -- linking session` and `npm run typecheck` | 0 for each after the link lifecycle review fixes. 74 tests passed, 0 failed, 0 skipped. |
| 23:31:37 | `apps/mobile` | `npm run test:unit` | 0. 87 unit tests passed, 0 failed, 0 skipped. |
| 23:32:57–23:33:04 | `apps/mobile` | Same placeholder environment and Expo config command, then `npm exec --offline -- expo export --platform ios --platform android --output-dir ../../.local/verification/T21/native-final/native` | 0. Final iOS and Android JS export each emitted one Hermes bundle, with one metadata file. |
| 23:33:04–23:33:14 | `apps/mobile` | `PATH=/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin:/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/Users/alexnoel/Library/Caches/ms-playwright VERIFY_RUN_ID=t21-linking-local npm run test:e2e -- linking.spec.ts` | 0. Playwright 1.65.0 with pinned Chromium, 2 desktop and 2 responsive mobile cases passed, 0 failed, 0 skipped. |
| 23:25:59 | root | Node assertions inspect resolved Expo config, then load `apps/mobile/app.config.js` with `EXPO_PUBLIC_LINK_SCHEME=realtoruch-dev` and `EXPO_PUBLIC_LINK_SCHEME=javascript` | 0. Defaults and app IDs match, association fields absent, override accepted, reserved scheme rejected. |

Final native bundles and public config are in ignored `.local/verification/T21/native-final/`. Browser aggregate `.local/verification/T18/t21-linking-local/summary.json` came from the existing T18 runner. The spec used the isolated local auth service and intercepted synthetic listing, seen and token responses. There were zero browser traces. No token values are included in this report. [Expo incoming-link API](https://docs.expo.dev/linking/into-your-app/). [Expo public environment variables](https://docs.expo.dev/guides/environment-variables/).

## Reproduction and review

- Open a supported listing query or token fragment on the app origin. On native, use the corresponding custom-scheme URL in a development build. Repeat the same startup link through the warm event source while the first request is pending.
- Open a saved listing while signed out, then sign in. The retained canonical home opens once and is marked seen after the authenticated detail opens.
- Force a transient verification response and use Retry link. The signed-in account remains present.
- Merge App's session-ready callback with T19's generation and unmount cleanup. Preserve T19's new transport and carry over only the endpoint-specific error mapping and response message selection in `api.ts`.
- Rollback is the client patch. A scheme change requires rebuilding installed app configuration.

## Blockers and next action

- Native installation, platform association, Android Maps and actual OS link delivery are deferred to T22. No user-supplied domain or Maps key was provided.
- No real mail, live provider requests, account creation outside the local synthetic test environment, cloud resources, push, deployment or publication were used.
