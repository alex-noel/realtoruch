# T17 — Finish reliable inbox polling, pagination and user feedback

**User instruction:** I want you to update the web/native inbox to use precise read cursors, preserve older loaded messages, and show useful loading, empty, blocked and retry states.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 5 hours |
| Proposed window | D6–D7 (2026-11-19–2026-11-20) |
| Worker slot | D |
| Dependencies | [T14](T14-session-resilience.md), [T16](T16-message-read-cursors.md) |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | marketplace-ui, frontend-api-client |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

MarketplaceDialog currently polls visible conversations every 15 seconds and merges overlapping message windows. Wire T16’s cursor API and close the remaining client race/state gaps without redesigning the whole app.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T17/<run-id>/`; commit sanitized reports only.

## Read first

- `apps/mobile/src/components/MarketplaceDialog.tsx`
- `apps/mobile/src/marketplaceApi.ts`
- `docs/contracts/messages.md (from T16)`
- `apps/mobile/src/components/UI.tsx`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/components/MarketplaceDialog.tsx (Messages section or extracted MessagesPanel.tsx)`
- `apps/mobile/src/marketplaceApi.ts`
- `apps/mobile/tests/messages.test.tsx (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Send the highest displayed incoming message ID when acknowledging reads. A poll response that is stale for the selected thread must never replace the current thread or mark another thread read.

2. Preserve explicitly loaded older messages when polling windows overlap; after a long gap, show a documented refresh/load-older path rather than silently losing a missing range. Deduplicate by message ID.

3. Pause polling while the app is backgrounded, document hidden or panel closed. Cancel/ignore in-flight responses on unmount or selection change; clean up listeners and intervals.

4. Keep a stable client_id across retries of the same unsent body/recipient and create a new ID only when content/target changes or send succeeds. Prevent duplicate sends from rapid taps.

5. Implement visible loading, empty inbox, failed load/send with retry, blocked/unblock and conversation pagination states. Preserve typed drafts when a network failure occurs.

6. Retain square corners, existing typography and minimal layout; check 320/390/768/1440-pixel widths and native-safe-area/keyboard behavior. Do not add a heavyweight chat dependency.

## Acceptance criteria

- **T17-AC01:** An unseen arrival after a displayed cursor remains unread until displayed.

- **T17-AC02:** Switching threads or closing the panel cannot apply stale responses/read acknowledgements.

- **T17-AC03:** History survives normal polls and has an explicit recovery path after long gaps.

- **T17-AC04:** Failed send retries retain draft and client ID; rapid taps cannot duplicate a message.

- **T17-AC05:** Polling stops in the background and resumes once without duplicate timers.

- **T17-AC06:** Loading/empty/error/blocked/pagination UI is accessible and fits the specified widths.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T17-TC01 — covers T17-AC01

**Given:** M1 is visible and M2 arrives before acknowledgement.

**When:** Send displayed read cursor.

**Then:** Only M1 is read; next display of M2 advances the cursor.

### T17-TC02 — covers T17-AC02

**Given:** Slow A-thread request followed by fast B-thread selection.

**When:** Resolve A after B.

**Then:** B remains visible; A is not accidentally acknowledged.

### T17-TC03 — covers T17-AC03

**Given:** Load two older pages, then poll new messages.

**When:** Merge overlapping and non-overlapping responses.

**Then:** No duplicate IDs; loaded history retained or explicit gap recovery shown.

### T17-TC04 — covers T17-AC04

**Given:** Send response is lost and user retries unchanged draft.

**When:** Retry after recoverable error.

**Then:** Same client ID, one server message, draft cleared only after success.

### T17-TC05 — covers T17-AC05

**Given:** Background/foreground transitions repeated five times.

**When:** Observe requests with fake timers.

**Then:** No hidden polling; one active timer after resume.

### T17-TC06 — covers T17-AC06

**Given:** Empty/error/blocked and long-message fixtures.

**When:** Render at four widths and navigate by keyboard.

**Then:** Controls labelled, text wraps, no horizontal overflow or inaccessible send state.


## Verification commands and checks

- `cd apps/mobile && npm run typecheck`
- `cd apps/mobile && npm run test:unit -- messages`
- Run T18 inbox browser tests when available

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Updated typed client/UI and deterministic state tests
- Synthetic desktop/narrow-screen evidence
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No external messages to real advertisers.
- No live-chat vendor, attachments or push/email message alerts.
