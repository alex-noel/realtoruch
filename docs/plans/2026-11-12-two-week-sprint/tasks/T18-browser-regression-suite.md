# T18 — Automate the eight-step rental journey and account/owner browser regressions

**User instruction:** I want you to turn the manually verified rental journey into repeatable browser tests, so cheaper workers can prove they have not broken the main user experience.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 8 hours |
| Proposed window | D4–D5 (2026-11-17–2026-11-18) |
| Worker slot | A |
| Dependencies | [T01](T01-isolated-verification.md), [T14](T14-session-resilience.md), [T02](T02-ci-quality-gates.md) |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | browser-test-harness |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The app has browser screenshots and API tests but no tracked browser automation suite. Tests must run against synthetic isolated data and local mail previews, using the production web export.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T18/<run-id>/`; commit sanitized reports only.

## Read first

- `docs/verification.md`
- `scripts/journey.py`
- `scripts/verify.py (from T01)`
- `apps/mobile/src/App.tsx`
- `apps/mobile/src/components/Dialogs.tsx`
- `apps/mobile/src/components/MarketplaceDialog.tsx`
- `backend/tests/test_rental_journey.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/playwright.config.ts (new)`
- `apps/mobile/e2e/* (new)`
- `apps/mobile/package.json and package-lock.json (test dependency only)`
- `scripts/verify.py (web profile hook)`
- `docs/testing.md`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Add a pinned compatible Playwright Test dev dependency and Chromium profile, with a deterministic test catalog/account setup and isolated API/auth/worker/static-web processes from T01.

2. Drive actual controls for Kraków, below 5,000 PLN base rent, >=50 m², direct offers, polygon drawing, save search, email opt-in confirmation, open/seen, favorite and delist/relist/drop. Assert inbox and local .eml counts, not only screenshot text.

3. Expected lifecycle: initial baseline is silent; new qualifying home yields one alert; opening marks seen; same-price repost yields zero additional alert; 4,500→4,200 favorite drop yields one; delisted favorite remains while discovery/map exclude it.

4. Add account verification/reload/session/logout tests and owner draft/publish/edit/withdraw/private-message tests. Use two isolated browser contexts for different users. Never use personal browser cookies or real inboxes.

5. Use role/label locators, deterministic readiness and condition polling, bounded timeouts and traces/screenshots on failure. No arbitrary multi-second sleeps or retries that silently convert flaky tests into success.

6. Run desktop and 390x844 profiles. Keep native claims separate. Wire into T02 after the suite is stable and default to one CI browser worker until per-test isolation is proven.

7. Add a separate mobile-width list/map visibility assertion and cap fixture mutation endpoints to test mode bound to loopback with a per-run token. Test-only event injection must never be enabled by production configuration or exposed through public ingress.

## Acceptance criteria

- **T18-AC01:** The complete eight-step scenario passes unattended on a clean isolated catalog.

- **T18-AC02:** Tests assert canonical identity, seen/favorite states, map/list visibility and exact logical alert counts.

- **T18-AC03:** Account verification/session reload and owner publishing/messages are tested with real local services.

- **T18-AC04:** The suite has no live portal, external SMTP, personal-browser or cloud dependency.

- **T18-AC05:** A deliberately injected duplicate notification or visible delisted pin causes a deterministic test failure.

- **T18-AC06:** Failure artifacts are useful and sanitized; two consecutive clean runs pass without ignored failures.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T18-TC01 — covers T18-AC01, T18-AC02

**Given:** Fresh journey catalog and a user-saved Kraków polygon/search.

**When:** Run new/delist/relist/drop/delist sequence.

**Then:** Expected 1 new-match + 1 price-drop and silent same-price repost; saved delisted home persists.

### T18-TC02 — covers T18-AC02

**Given:** Rent exactly 5,000; area 49.9; agency; unknown commission; point outside polygon.

**When:** Exercise corresponding filters.

**Then:** Each boundary follows the documented filter contract; direct and no-commission remain separate.

### T18-TC03 — covers T18-AC03

**Given:** Local account verification preview and reload.

**When:** Verify, reload, revoke/sign out.

**Then:** Session/cookie states match account contract; private views clear on confirmed logout.

### T18-TC04 — covers T18-AC03

**Given:** Owner and renter in separate contexts.

**When:** Publish, edit, message, read and withdraw.

**Then:** Price history and private messaging work; withdrawn listing leaves discovery.

### T18-TC05 — covers T18-AC04

**Given:** Outbound network interception denies portals/mail/cloud.

**When:** Run suite.

**Then:** All tests still pass using only approved local/static resources.

### T18-TC06 — covers T18-AC05, T18-AC06

**Given:** Inject an extra notification or stale visible pin into the fixture path.

**When:** Run relevant test and inspect trace.

**Then:** Test fails with explicit mismatch; sanitized trace points to the failure.

### T18-TC07 — covers T18-AC06

**Given:** Two clean executions on fresh run IDs.

**When:** Run desktop and mobile-width projects.

**Then:** Both pass with no unexplained retries or leaked state.


## Verification commands and checks

- `cd apps/mobile && npm run test:e2e (new script)`
- `make verify-web (T01 hook completed here)`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Browser suite, deterministic fixture setup and CI hook
- Sanitized failure example and two passing runs
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not claim physical iOS/Android acceptance from responsive Chromium.
- Do not send real emails or use real portal accounts.

## Primary technical references

- [Playwright CI configuration and timeouts](https://playwright.dev/docs/ci).

Use these with the installed project versions; recheck current version-specific details before implementation.
