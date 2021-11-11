# T18 browser regression handoff

## Identity and outcome

- Task: T18
- Status: IMPLEMENTED_LOCAL. The isolated local cases passed; integrated T15/T16/T17 producer/UI revisions and hosted CI have not yet been tested together.
- Base revision: `49d4bcf`. Session fixes `3fbab65` and `64b949a` were ported as `26d3124` and `7721dea` using `scripts/commit.py`; the integrator owns their original commits.
- T18 implementation commits: `95bb97f`, `ddbf681` and `ce6087f`, created using `python3 scripts/commit.py`. This report is a separate handoff commit.
- Actual work and test date: 11 November 2026, Europe/Warsaw (CET); reports preserve UTC timestamps independently of Git metadata.
- Outcome: repeatable Chromium exercises synthetic rental, account, two-tab and owner/renter flows against the production web export and local services.
- Scope: integrator approved the narrow CI browser system-dependency extension; no production endpoint or application UI changes in T18. The two session fixes above were produced by the integrator.

## Changed files and contracts

`apps/mobile/e2e/` contains isolated run orchestration, synthetic observation child process, desktop/mobile behavioral tests, aggregate reporter and trace screening/canary tests. `playwright.config.ts` uses pinned Chromium, one worker, zero retries and bounded timeouts. The package and lock add only Playwright Test 1.65.0; Vitest remains 4.1.12. `scripts/verify.py` runs the web profile and reports aggregate counts, forwarding the explicit browser-cache path. The CI workflow installs Chromium system dependencies without changing pinned actions. `docs/testing.md` documents operation and artifact boundaries. There are no migrations, public DTO or API changes.

The fixture mutation path is a local child process, not an HTTP endpoint. It checks a random per-run token, non-production mode, an exact run-owned SQLite path and an ignored T18 run directory. Browser routing permits only the three run-owned loopback ports, including a deterministic local tile; SMTP, push, collectors, portals and cloud are disabled. A single worker is required because the suite shares a run-owned catalog. This is responsive Chromium, not native-device acceptance.

## Acceptance evidence

| AC ID | Status | Mapped cases and evidence |
| --- | --- | --- |
| T18-AC01 | PASS, local | TC01: `t18-final-2` and `t18-final-3`, complete synthetic lifecycle, each profile. |
| T18-AC02 | PASS, local | TC01/TC02: same canonical ID on repost/drop; seen and favorite floor; active map/list and delisted saved state; exact logical inbox and rental `.eml` counts; exclusive rent, minimum area, direct, polygon, unknown vs zero commission. |
| T18-AC03 | PASS, local; integrated producer rerun pending | TC03: real file verification link, session reload/logout, two-tab lock barrier and stale-account switch. TC04: real local owner and renter contexts, draft/publish/edit, dialog price history, messages/read/reply and withdrawal. The strengthened dialog-only history locator passed `t18-owner-final`, and foreground/viewport/read-response checks passed `t18-owner-read`, after the two complete runs. |
| T18-AC04 | PASS, local | TC05: browser outbound route guard, loopback services, file mail and local tile; no external provider used. |
| T18-AC05 | PASS, local | TC06: `t18-fault-4` deliberately injected a duplicate local notification; the UI assertion failed with expected 1 / received 2. |
| T18-AC06 | PASS with artifact limitation; integrated rerun pending | TC06/TC07: `t18-final-2` and `t18-final-3` each passed 12/12 with zero skips or retries. Fault screenshot and screened trace retained under the ignored fault run; ordinary journey failures have screenshot/error context but no trace. Traces containing known token fields or values are omitted, not uploaded. |

TC01–TC07 respectively: PASS, PASS, PASS, PASS, PASS, PASS, PASS in the local evidence above. TC07's two full runs precede the final change that scoped two owner-history locators to the detail dialog; those changes were separately tested at both widths in `t18-owner-final` and `t18-owner-read`. The integrator will repeat the full suite after merging T15/T16/T17.

## Verification

All commands ran from this worktree on macOS 15.7.7 arm64, Python 3.12.9, Node 24.6.0, Playwright 1.65.0 and Chromium 158.0.8127.18. The root Python 3.12 venv was used read-only through a temporary worktree symlink, removed after the runs. `PLAYWRIGHT_BROWSERS_PATH` pointed at the Playwright-installed cache; no personal browser profile was used.

- `npm ci --ignore-scripts --no-audit --no-fund` in `apps/mobile`: exit 0. `npm audit --json`: no advisory for the added Playwright package; 0 high/critical and 4 moderate overall. `npm run typecheck`: exit 0.
- `make verify-web ARGS='--run-id t18-final-2'`: exit 0, 12 passed / 0 failed / 0 skipped. Actual UTC 21:43:19–21:44:42. Report `.local/verification/T01/t18-final-2/report.json`; this run used the same implementation as `95bb97f` while it was uncommitted.
- `make verify-web ARGS='--run-id t18-final-3'`: exit 0, 12 passed / 0 failed / 0 skipped. Report `.local/verification/T01/t18-final-3/report.json`; revision `95bb97f` clean at run start.
- `VERIFY_RUN_ID=t18-owner-final npm run test:e2e --prefix apps/mobile -- -g 'owner publishes'`: exit 0, 2 passed / 0 failed / 0 skipped, after dialog-scoped history assertions; `.local/verification/T18/t18-owner-final/summary.json`.
- `VERIFY_RUN_ID=t18-owner-read npm run test:e2e --prefix apps/mobile -- -g 'owner publishes'`: exit 0, 2 passed / 0 failed / 0 skipped, after foregrounding the owner tab, checking the incoming message is in the viewport and waiting for the successful read PUT. This run used the legacy inbox; T17 integration remains pending.
- `python apps/mobile/e2e/test_sanitize.py`: exit 0, 2 tests / 0 failures, including seven synthetic verify/confirm/unsubscribe/reset/authorization/cookie/JWT canary variants and a safe Playwright-shaped trace. Network, response bodies, sources and stacks are not retained.
- `VERIFY_RUN_ID=t18-fault-4 T18_FAULT_DUPLICATE=1 npm run test:e2e --prefix apps/mobile -- --project=desktop -g 'draw and save'`: expected exit 1, 0 passed / 1 failed / 0 skipped. The screenshot shows two synthetic NEW MATCH cards. `trace-handling.json` records one retained screened trace and zero omitted; its archive contains `trace.trace` and eight synthetic `screencast/*.jpeg` frames only. The network archive, response/resource bodies and stacks are excluded. Screenshot and trace remain in `.local/verification/T18/t18-fault-4/`; no raw trace is retained or published.
- Account-switch defect demonstration: `t18-switch-before` failed desktop and its synthetic A-tab mutation was actually stored under synthetic B. After the integrator's fix, `t18-switch-after` passed 2/2 with no skips. Two-tab refresh test holds the first refresh before network continuation, waits until the other tab's `realtoruch-refresh` Web Lock is pending, asserts only one refresh has reached the network, then releases and verifies both sessions. Logout waits for the second tab's real 401 on reload before checking private identity is absent.
- `t18-clean-1`: 10 passed / 2 failed / 0 skipped due to fixture interference; fixture source IDs were narrowed before later runs. `t18-clean-2`: 12 passed / 0 failed / 0 skipped. `t18-final-1` was deliberately interrupted after repeated actionability failures with a copied browser cache, and `t18-termination` was deliberately terminated to test cleanup; neither is a passing run. A standalone local-page probe with equal browser version, executable bytes and normalized launch arguments produced no animation frames/click from the copied cache and succeeded from the original installed cache. The interrupted-run cleanup drill left no owned processes or raw trace archives.

Fixture counts: one silent qualifying baseline and one lifecycle home per viewport, six boundary records per viewport, and synthetic owner/renter accounts. The first two full runs use fresh run IDs, separate from all targeted and injected runs. No real inbox, SMTP delivery, portal, cloud, push, personal-browser data, deployment or physical device was used.

## Reproduction and review

See `docs/testing.md` for setup and exact local commands. The controlled duplicate must fail rather than retry or pass. `test_sanitize.py` proves synthetic negative canaries are rejected without an archive; the filter excludes raw network/response content but is scoped to this synthetic suite and is not a general-purpose trace sanitizer. Unscreened logs, mail, databases and error contexts remain ignored private run data. The CI uploader receives only selected aggregate report fields, synthetic screenshots and screened traces; token-bearing traces are omitted and counted. A crash or SIGKILL can bypass process cleanup; inspect only the run's owned process group and ignored directory, never prune unrelated resources.

Remaining review: integrate T15/T16 and T17, rerun the complete web profile and verify owner inbox/read behavior with the final cursor implementation. T17's updated `Open conversation: <title>` accessible name is accepted by the test's prefix locator. The tested session fixes need normal integration review. CI hosted execution and required-check configuration are unverified. Rollback is a reviewed revert of the T18 commits, leaving user data untouched; run resources are disposable. No push or deployment was performed.
