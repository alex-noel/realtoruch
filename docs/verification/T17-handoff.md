# T17 handoff — Reliable inbox

- Status: **VERIFIED locally**, with native runtime checks listed separately below.
- Reviewed base: `64b949a` (T14/T15/T16 available).
- Product commit: `e8d2b5e225e389bb6ec76a1cb9f6aa98202a71c1`, created with `python3 scripts/commit.py`; author and committer are both `2021-11-11T22:50:31+01:00`. This report follows in a separate commit.
- Actual implementation and verification: 2026-11-11, Europe/Warsaw (CET, UTC+01:00).
- The inbox marks only displayed incoming messages read, retains loaded history, and preserves an unsuccessful send for retry. It offers recoverable loading, paging, and block states.
- The integrator approved an optional inbox viewport and native inset configuration in `UI.tsx`. A18 separately owns the T18 owner-browser barrier in `ce6087f`; no T18 files or locks changed in T17.

## Files and contracts

| File | Change |
| --- | --- |
| `apps/mobile/src/components/MarketplaceDialog.tsx` | Mounts the extracted Messages panel, keeps its drafts across rental-desk tab changes, and synchronously stops its work when closing or leaving Messages. |
| `apps/mobile/src/components/MessagesPanel.tsx` | Measures committed cards against the existing scroll viewport on layout and scroll; shows load, empty, error, gap, block, pagination and retry states, with labelled controls. |
| `apps/mobile/src/components/messagesState.ts` | Owns foreground polling, per-request cancellation, precise UTC ordering, continuous history ranges, inbox pages and per-recipient drafts. |
| `apps/mobile/src/components/UI.tsx` | Adds optional inbox-only ScrollView hooks and native insets/keyboard avoidance. Keying the inbox viewport also makes React Native Web attach the scroll ref when entering Messages from My adverts. Other Panel callers use their existing configuration. |
| `apps/mobile/src/marketplaceApi.ts` | Types nullable listing IDs and opaque inbox cursors. Sends the T16 `{last_message_id}` body. Cancellable inbox requests retain a 12-second deadline; shared session/request machinery is unchanged. |
| `apps/mobile/tests/messages.test.tsx` | Adds 13 deterministic message behavior and transport tests under the existing Vitest runner. |

The client counts an incoming card as displayed once at least 48 vertical layout pixels (or the full card if shorter) intersect the selected foreground transcript's scroll viewport. It chooses the highest visible incoming tuple at microsecond precision and uses the exact ID. A known gap prevents advancing the watermark beyond the oldest continuous displayed range until the user closes the gap. A read request already delivered to the server may complete after a close; the submitted boundary was already displayed, and its late response cannot change the current UI. The client refreshes authoritative unread counts, including a loaded older page containing the conversation, rather than setting a count to zero locally.

When a poll no longer overlaps, the transcript retains both ranges and offers **Load missing messages** at the boundary. The button pages backward until the ranges join. **Load older messages** continues before the oldest loaded range. Opaque inbox cursors remain server positions; pages can move as new messages arrive. Drafts and retry IDs are kept per target while the rental desk is mounted and are discarded when it closes. No migrations, schema, dependency, or server contract changes.

## Acceptance evidence

| AC | Result | Required case and result | Evidence |
| --- | --- | --- | --- |
| T17-AC01 | PASS | T17-TC01 PASS: the server fixture receives M2 during delayed M1 read; M2 remains unread below the viewport. Scrolling advances the boundary, with whole-second/microsecond/ID tie ordering and outgoing rows excluded. | Vitest unit test; Chromium at four widths verified exactly two read requests, with the second after jumping to the newly visible card. T18 owner also waited for the actual server PUT. |
| T17-AC02 | PASS | T17-TC02 PASS: pending A is ignored after B and a second selection of A; close fences an in-flight read and fetch. | Vitest deferred requests and AbortSignal assertions. Chromium close prevented further poll requests. |
| T17-AC03 | PASS | T17-TC03 PASS: two older pages survive overlap; non-overlap retains both ranges; two gap loads recover the missing sequence without duplicate IDs or an acknowledgement across the gap. | Vitest synthetic 16-message transcript. |
| T17-AC04 | PASS | T17-TC04 PASS: loss after simulated commit, same client ID on retry, one logical server message, one in-flight send, draft cleared only on success. Changing recipient or editing the draft uses the appropriate draft/ID. | Vitest deferred lost response and fixture message store; Chromium send failure and keyboard retry at all four widths. |
| T17-AC05 | PASS | T17-TC05 PASS: five background/foreground cycles, duplicate notifications, zero hidden requests and exactly one timer on resume. | Vitest fake timers; Chromium app wiring with simulated document visibility and close. |
| T17-AC06 | PASS (web); native runtime NOT_RUN | T17-TC06 PASS (web): empty, load error/retry, pagination, long text, send disabled/error/retry, blocked/unblock, and keyboard Tab/Enter. Native safe area and keyboard compiled but were not exercised on an installed device. | Chromium 158.0.8127.18 at 320/390/768/1440 by 840. Scroll width/client width: 284/284, 354/354, 732/732, 1000/1000. T18 real loopback SQLite/FastAPI owner flow passed at desktop and mobile sizes. |

## Verification

Node 24.6.0, Python 3.12.9, Vitest 4.1.12, Expo 58, React Native 0.88, and T18 Playwright 1.65.0 on arm64 macOS. Commands used the Node 24.6.0 bin directory first on PATH and, for the Python harnesses, the root Python 3.12 virtual environment. `RUN=$PWD/.local/verification/T17/viewport-20261111` from the worktree root. All durations below are measured wall time unless indicated.

| Working directory | Command | Result | Artifact |
| --- | --- | --- | --- |
| `apps/mobile` | `npm ci` | Exit 0; 581 packages installed, npm reported 3 s. | Locked T17 dependencies; no lock change. |
| `apps/mobile` | `/usr/bin/time -p npm run typecheck` | Exit 0, 1.28 s. | `$RUN/frontend.log` |
| `apps/mobile` | `/usr/bin/time -p npm run test:unit -- messages` | Exit 0; 13 passed, 0 failed, 0 skipped; 0.45 s. | `$RUN/frontend.log` |
| `apps/mobile` | `/usr/bin/time -p npm run test:unit` | Exit 0; 33 passed, 0 failed, 0 skipped; 0.78 s. | `$RUN/frontend.log` |
| Worktree root | `/usr/bin/time -p python scripts/verify.py offline --run-id t17-offline-20261111` | Exit 0, 23.83 s; backend 313 passed, 0 failed, 92 skipped in offline mode; frontend typecheck and unit checks also exited 0. Skipped service/environment cases are listed in the report. | `.local/verification/T01/t17-offline-20261111/report.json` |
| Worktree root | `EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 CI=1 EXPO_PUBLIC_API_URL="http://127.0.0.1:$PORT" EXPO_PUBLIC_AUTH_URL="http://127.0.0.1:$PORT" EXPO_PUBLIC_MAP_TILE_URL="http://127.0.0.1:$PORT/tile.png" /usr/bin/time -p npm run build:web --prefix apps/mobile -- --output-dir "$RUN/dist"` | Exit 0, 1.18 s. PORT is in `$RUN/port`, chosen for the owned loopback server. | `$RUN/export.log` |
| Worktree root | `/usr/bin/time -p node "$RUN/check.cjs"` | Exit 0; 4 width profiles passed, 0 failed, 0 skipped; 7.83 s. Browser mocked API traffic with synthetic rows and blocked all outside origins; none attempted. | `$RUN/layout.log`, plus `empty-*.png`, `blocked-*.png`, `thread-*.png`. |
| `apps/mobile` | `EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 CI=1 /usr/bin/time -p npm exec -- expo export --platform ios --platform android --output-dir "$RUN/native-bundles"` | Exit 0, 5.89 s; one Hermes bundle per platform. Native runtime cases not run. An initial invocation from the repository root failed before compiling because Expo looked for a root package.json; reran from the app directory. | `$RUN/native-export.log` |
| `$RUN/integration` | `npm ci --prefix apps/mobile`; `VERIFY_RUN_ID=t17-owner-remount-20261111 /usr/bin/time -p npm run test:e2e --prefix apps/mobile -- -g 'owner publishes'` | Exit 0 for both; install 584 packages, npm reported 3 s. Owner run: 2 passed, 0 failed, 0 skipped among selected tests; other specs filtered out; 24.78 s. | `$RUN/owner-install.log`, `$RUN/owner-remount.log`, run summary under integration `.local/verification/T18/t17-owner-remount-20261111/`. |

The T18 run used a disposable archive of the reviewed base with the final T17 source files overlaid; runner, locks and config from `95bb97f`; exact owner spec from A18's `ce6087f`. Its two Chromium profiles each used two synthetic participant sessions against local FastAPI, SQLite and file mail. The original owner run failed both profiles at the unread badge (44.25 s). A second run with an explicit viewport and read-response barrier isolated the missing ScrollView ref (2 failures, 42.52 s). The final run fixed the ref when switching modes and used A18's deterministic foreground/viewport/PUT checks.

The four-width browser fixture intercepts API requests and uses one long incoming card (360 unbroken characters plus 55 short lines), an arrival below it, one failed and retried send, an older inbox page, and a block/unblock cycle. At 320 and 1440 it opens Messages from My adverts to exercise the scroll-ref regression; at 390 and 768 it opens Messages from Account. This is synthetic layout evidence, separate from the real local owner test.

## Review and remaining checks

- Reproduce the read case by opening a long thread, then delivering a newer incoming message below its viewport. Check that the read PUT retains the displayed boundary; use **Jump to latest messages** to reveal and acknowledge the arrival.
- On a failed send, check the draft remains editable and **Retry send** uses its previous client ID. On a long poll gap, use **Load missing messages** until the retained ranges meet.
- Roll back by reverting the frontend changes; the T16 server still accepts legacy v1 callers. No data migration or recovery script is needed.
- Physical or simulated native runtime safe-area and keyboard behavior was **not run**: Xcode Command Line Tools are selected, `xcrun simctl list devices booted` cannot find simctl, and Android adb is absent. A developer with a local iOS/Android build can open a long thread, focus the composer, confirm it and Send stay reachable, and background/resume once. Browser evidence is not native runtime evidence.
- No external gates remain for the specified local implementation. No live listings, real emails, external messages, cloud resources, deploy, or publication were used.

## Integrator verification

The root checkout at `3bec9db` with the staged T17 product commit passed the complete T18 web profile: **12 passed, 0 failed, 0 skipped**. The run was `integrated-t17-t18`, actual UTC 2026-11-11 21:51:41–21:53:05; its report is `.local/verification/T01/integrated-t17-t18/report.json`. It exercised the integrated T12/T14/T15/T16/T17 implementations at desktop and mobile viewport sizes. The recorded worktree was dirty because T17 was staged for review, rather than committed yet.

The integrator added `apps/mobile/vitest.config.mjs` to restrict unit discovery to `tests/**/*.test.{ts,tsx}`. Without that boundary, Vitest collected the new Playwright specs as unit tests. With the configuration, `npm run test:unit` passed **33 tests, 0 failed, 0 skipped**, actual local time 2026-11-11 22:58:01. The preceding frontend typecheck and the two trace-screening tests also passed. Native runtime limits above remain unchanged.
