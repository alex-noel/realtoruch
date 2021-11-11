# T21 — Handle native deep links and account lifecycle across app restarts

**User instruction:** I want a rental, notification or account email link to open the correct screen on mobile, including when the app starts from a closed state.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D4 (2026-11-17) |
| Worker slot | D |
| Dependencies | [T14](T14-session-resilience.md) |
| Required review | strong: account links and token handling |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | root-ui, native-config, session-client |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Native JS exports exist, but export success does not prove installed-app behavior. This task implements deterministic link routing and configuration; T22 verifies actual iOS/Android builds.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T21/<run-id>/`; commit sanitized reports only.

## Read first

- `apps/mobile/app.config.js`
- `apps/mobile/app.json`
- `apps/mobile/src/App.tsx`
- `apps/mobile/src/api.ts`
- `apps/mobile/src/pushClient.ts`
- `apps/mobile/src/components/AccountDialog.tsx`
- `backend/realtoruch/auth.py`
- `backend/realtoruch/email_alerts.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/linking.ts (new)`
- `apps/mobile/src/App.tsx (link dispatch hook only)`
- `apps/mobile/app.config.js`
- `apps/mobile/.env.example`
- `apps/mobile/tests/linking.test.ts (new)`
- `docs/mobile-validation.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Inventory existing web email/push URLs first and document an explicit route allowlist for listing, notification, email verification, password reset and email alert confirmation. Preserve current web URLs and fragment-based secrets. Add a configurable realtoruch custom scheme and one shared parser producing typed actions.

2. Use Expo/RN link APIs for cold-start initial URL and warm app URL events. Deduplicate the same event within the current processing lifecycle; do not persist secret links in history, logs, analytics or AsyncStorage. Subscribe once and remove handlers on teardown.

3. Validate scheme, configured HTTPS host, route, identifier and required token shape before dispatch. Reject protocol-relative/external redirects, malformed encodings, oversized tokens, javascript/data URLs and unknown actions. Do not fetch arbitrary URLs from incoming links.

4. If an account-protected route arrives while logged out, retain only its safe destination and show login; resume after authentication. Consume verification/reset/confirmation tokens through existing auth endpoints once; display expired/used token and network-retry states without destroying a valid session.

5. Account links, push notifications and ordinary navigation must converge on the same canonical listing/detail handler so aliases work and opening marks seen. A delisted favorite can open its retained detail but must not return to discovery.

6. Expose API/auth/public-app URL and Android map configuration through documented environment variables with example placeholders only. Configure platform link association files only for a user-supplied domain; without one, mark universal/app links unverified and keep custom-scheme tests separate. New schemes need a new development build, so record that handoff to T22.

## Acceptance criteria

- **T21-AC01:** A typed allowlisted parser handles all documented route types and rejects invalid inputs.

- **T21-AC02:** Cold-start and warm link delivery each navigate once without duplicate token consumption.

- **T21-AC03:** Protected destinations resume safely after login and valid sessions survive temporary link-request failures.

- **T21-AC04:** Token values never appear in logs, persisted navigation state or exported test reports.

- **T21-AC05:** Web link compatibility, canonical aliases and delisted-favorite detail access are preserved.

- **T21-AC06:** Both native JS exports pass with documented placeholder configuration, and installed-app checks are explicitly deferred to T22.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T21-TC01 — covers T21-AC01

**Given:** Table of valid listing/account URLs and malicious schemes/hosts/encodings.

**When:** Parse every case.

**Then:** Only documented actions are accepted; malformed or untrusted links produce a safe error.

### T21-TC02 — covers T21-AC02

**Given:** Same link delivered by getInitialURL and a warm event.

**When:** Dispatch both in one lifecycle.

**Then:** Navigation or token consumption occurs once, with handlers removed on unmount.

### T21-TC03 — covers T21-AC03

**Given:** Protected listing link while logged out.

**When:** Log in and then simulate temporary auth service failure for a separate action.

**Then:** The safe destination resumes; unrelated valid session state is retained.

### T21-TC04 — covers T21-AC03, T21-AC04

**Given:** Expired reset token and network failure followed by retry.

**When:** Inspect screen, logs and storage.

**Then:** Correct error/retry is shown without exposing token or consuming it twice after success.

### T21-TC05 — covers T21-AC05

**Given:** Old canonical alias and delisted favorite link.

**When:** Open through web and native handlers.

**Then:** Correct retained listing opens and is marked seen; discovery remains unchanged.

### T21-TC06 — covers T21-AC06

**Given:** Clean checked-in example configuration.

**When:** Run iOS/Android JS exports and inspect app config.

**Then:** Build-time JS validation succeeds; report does not claim native installation or domain association was tested.


## Verification commands and checks

- `cd apps/mobile && npm run typecheck`
- `cd apps/mobile && npm run test:unit -- linking session`
- `python3 scripts/mobile_check.py --help, then use its documented JS-export checks`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Shared link parser/dispatcher and tests
- Native configuration and installed-build validation instructions
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not buy a domain, create developer accounts, generate paid builds or publish an app.
- Do not embed sender credentials or unrestricted server keys in the app.

## Primary technical references

- [Expo incoming links, cold starts and custom schemes](https://docs.expo.dev/linking/into-your-app/).

Use these with the installed project versions; recheck current version-specific details before implementation.
