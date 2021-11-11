# T22 — Verify the complete rental journey in installed iOS and Android apps

**User instruction:** I want evidence that the app works when installed on iOS and Android, including maps, keyboard behavior, email links and session recovery.

| Field | Instruction |
| --- | --- |
| Tier / priority | CONDITIONAL / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D8–D10 (2026-11-23–2026-11-25) |
| Worker slot | UNALLOCATED |
| Dependencies | [T17](T17-inbox-client.md), [T18](T18-browser-regression-suite.md), [T21](T21-native-links-and-lifecycle.md) |
| Required review | strong: platform evidence |
| External gates | G03 |
| Shared merge/contract locks | native-config |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The baseline has JS exports, not installed-device acceptance. Full Xcode, Android SDK/devices and any required map/signing configuration are external prerequisites. Missing prerequisites must remain explicit blockers.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T22/<run-id>/`; commit sanitized reports only.

## Read first

- `docs/mobile-validation.md (from T21)`
- `scripts/mobile_check.py`
- `apps/mobile/app.config.js`
- `apps/mobile/src/components/PropertyMap.tsx`
- `apps/mobile/src/linking.ts (from T21)`
- `apps/mobile/src/api.ts`
- `apps/mobile/src/pushClient.ts`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `docs/verification/mobile-acceptance.md (new)`
- `scripts/mobile_check.py (diagnostics/validation only)`
- `apps/mobile/app.config.js (targeted build fixes)`
- `apps/mobile/src/components/PropertyMap.tsx (platform fixes only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Inventory local Xcode/SDK versions, emulator/simulator or physical device models, OS versions, map configuration and signing availability without installing paid services or accepting account terms. Distinguish simulator, emulator and physical-device evidence in the report.

2. Build and install a local development/debug app using the pinned project toolchain. Use synthetic isolated accounts/listings and local test email preview links. Record commit, build ID, commands and platform logs with credentials redacted.

3. Run the full eight-step scenario on each platform: Kraków, polygon, <5,000 base rent, >=50 m², direct, saved-search baseline, new notification, seen, favorite, same-price repost silence, lower-price alert and delisted favorite persistence/map exclusion.

4. Verify app cold start, background/foreground, valid SecureStore restoration, offline restoration followed by reconnect, confirmed logout and an email account/listing deep link from outside the app. Test keyboard covering form controls, permission denial and map failure with list fallback.

5. Fix only platform-specific defects inside the named scope. Backend behavior changes go back to the owning task. If push is available, check foreground/background routing; email remains the requested primary closed-app delivery channel and native push credentials are not a reason to mislabel email tests.

6. Produce separate pass/fail/not-run rows per platform and scenario with screenshots or short logs. If only one platform or an emulator is available, mark partial verification and list exact missing prerequisites; never substitute a web viewport or JS export for an installed native test.

## Acceptance criteria

- **T22-AC01:** An installed build is tested on both iOS and Android, with device type and OS recorded.

- **T22-AC02:** The full eight-step rental journey passes on both platforms.

- **T22-AC03:** Cold-start/background session and deep-link behavior pass without credential leakage.

- **T22-AC04:** Map/keyboard/permission/offline failure states remain usable.

- **T22-AC05:** Any platform fixes pass shared typecheck, JS exports and relevant regression tests.

- **T22-AC06:** Evidence distinguishes verified behavior from blocked or not-run checks and contains no personal data.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T22-TC01 — covers T22-AC01, T22-AC02

**Given:** Installed iOS build and fresh synthetic catalog.

**When:** Execute the journey from T18 with real native controls.

**Then:** All lifecycle assertions pass; artifact identifies simulator versus physical device.

### T22-TC02 — covers T22-AC01, T22-AC02

**Given:** Installed Android build and independent fresh catalog.

**When:** Execute the same journey.

**Then:** All lifecycle assertions pass with Android-specific map/input behavior captured.

### T22-TC03 — covers T22-AC03

**Given:** Authenticated app terminated, then network unavailable.

**When:** Reopen, restore, reconnect and open an email link externally.

**Then:** Session is retained appropriately; one safe navigation occurs after readiness.

### T22-TC04 — covers T22-AC03, T22-AC04

**Given:** Background app, invalid/expired link and denied permissions.

**When:** Resume and use the relevant actions.

**Then:** No crash or token logging; errors and recovery actions are clear.

### T22-TC05 — covers T22-AC04

**Given:** Small device with keyboard open and unavailable map tiles.

**When:** Edit filters/publish form and switch to list.

**Then:** Essential controls remain reachable and listing discovery continues.

### T22-TC06 — covers T22-AC05, T22-AC06

**Given:** One missing SDK, signing identity or map prerequisite.

**When:** Run preflight and review the report.

**Then:** Missing platform checks are BLOCKED_EXTERNAL, never recorded as passed.


## Verification commands and checks

- `python3 scripts/mobile_check.py --help, then documented native diagnostics`
- Platform-specific local build/install commands recorded with exact versions
- `make verify-web for shared-flow regressions`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Per-platform acceptance matrix and sanitized native evidence
- Bounded fixes or an exact external-blocker handoff
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not submit to app stores, purchase developer memberships or use cloud build credits without separate authorization.
- Do not claim push delivery on physical devices if only an emulator was tested.
