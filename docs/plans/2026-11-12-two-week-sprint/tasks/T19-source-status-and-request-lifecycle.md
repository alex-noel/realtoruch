# T19 — Show collection freshness and prevent stale browser/mobile requests

**User instruction:** I want users to understand how fresh their Kraków results are, and I want rapid filter changes to show only the latest requested results.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D4–D5 (2026-11-17–2026-11-18) |
| Worker slot | B |
| Dependencies | [T03](T03-collector-leases.md), [T14](T14-session-resilience.md) |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | root-ui, api-types |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Collection health already exists in the backend. Its operational states need a concise user-facing presentation, and the shared app must handle overlapping requests and temporary failures without replacing a newer search with stale data.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T19/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/api.py`
- `apps/mobile/src/App.tsx`
- `apps/mobile/src/api.ts`
- `apps/mobile/src/types.ts`
- `apps/mobile/src/components/Insights.tsx`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/components/SourceStatus.tsx (new)`
- `apps/mobile/src/hooks/useListingSearch.ts (new, if extraction simplifies ownership)`
- `apps/mobile/src/App.tsx (small integration hook)`
- `apps/mobile/src/api.ts`
- `apps/mobile/src/types.ts`
- `apps/mobile/tests/sourceStatus.test.ts (new)`
- `apps/mobile/tests/searchLifecycle.test.ts (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Map the existing source/city health response to never-collected, collecting, fresh, delayed, partial/failed, access-blocked and disabled states. Preserve last successful observation and latest attempt as different timestamps. A failed attempt must not make old results appear fresh.

2. Define freshness against the configured collection cadence: fresh when the last complete success is no older than twice that cadence; delayed otherwise. Missing/invalid timestamps are unknown. Display the exact last-success timestamp on demand and use a bounded provider list; do not show backend exception text.

3. Keep source health scoped to the selected city. Distinguish 'OLX automatic collection unavailable' from manual/imported OLX records. The status badge must not imply complete portal coverage or that every source listing was rechecked.

4. Use AbortController where supported plus a monotonically increasing request generation. Accept results only for the current normalized query. Batch canonical seen/favorite state through the existing bulk API rather than requesting it once per card. Preserve filter controls and usable previous results while a replacement fetch is pending.

5. Debounce text/number input by 250 ms, but submit explicit Apply, polygon completion, pagination and retry immediately. Cancel/ignore outdated health and search responses independently. A network failure shows a retry action and the age of retained results; confirmed logout clears private state.

6. Use existing square controls, theme tokens, readable text and accessibility labels. Add a test harness compatible with the project's pinned React/TypeScript versions; share it with T14/T17 rather than adding a second competing runner.

## Acceptance criteria

- **T19-AC01:** Each provider state has accurate concise copy and does not expose exception details.

- **T19-AC02:** Freshness derives from last complete success and configured cadence; unknown values never become fresh.

- **T19-AC03:** Rapid query changes cannot display an older city's listings or status.

- **T19-AC04:** Listing user state is fetched in bounded batches and requests are cancelled or ignored on unmount.

- **T19-AC05:** Offline/retry and logout preserve the intended public filters while protecting private state.

- **T19-AC06:** The component works at 320 px and with screen-reader labels without adding unnecessary initial bundle dependencies.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T19-TC01 — covers T19-AC01, T19-AC02

**Given:** Success at 10:00, failed attempt at 12:00, configured cadence one hour.

**When:** Render at 12:01.

**Then:** State is delayed/failed with last success 10:00; the failure does not reset freshness.

### T19-TC02 — covers T19-AC01, T19-AC02

**Given:** Disabled OLX with one imported listing and missing health timestamps.

**When:** Render source summary.

**Then:** Automatic coverage is unavailable and freshness is unknown; imported data is not described as an operational scraper.

### T19-TC03 — covers T19-AC03

**Given:** Slow Kraków request A followed by fast Warszawa request B.

**When:** Resolve B, then A.

**Then:** Only Warszawa results and Warszawa provider status remain visible.

### T19-TC04 — covers T19-AC03, T19-AC04

**Given:** Twenty keystrokes and a page of fifty listings.

**When:** Observe requests using a fake clock.

**Then:** One debounced search is issued; user-state requests follow the documented bulk size, never one per card.

### T19-TC05 — covers T19-AC04, T19-AC05

**Given:** Pending request while component unmounts or account signs out.

**When:** Complete the request afterward.

**Then:** No stale render, state update warning or private-state resurrection occurs.

### T19-TC06 — covers T19-AC05, T19-AC06

**Given:** Previously successful result and simulated offline failure.

**When:** Use Retry at 320 px with keyboard/screen reader.

**Then:** Retained results are labelled with age; retry works and controls remain reachable.


## Verification commands and checks

- `cd apps/mobile && npm run typecheck`
- `cd apps/mobile && npm run test:unit -- sourceStatus searchLifecycle`
- `make verify-web`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Provider status component and freshness contract
- Request lifecycle tests and request-count evidence
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not add a new provider or change collection pacing.
- Do not add auto-refresh traffic per listing card.
