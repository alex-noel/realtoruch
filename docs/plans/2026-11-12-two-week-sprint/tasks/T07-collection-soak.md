# T07 — Run and report a bounded 72-hour collection soak

**User instruction:** I want you to prove that collection can run unattended over several days, recover from interruption, and preserve listing/alert history without exceeding provider limits.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 6 hours; additionally >=72 real elapsed hours for the live run |
| Proposed window | D4–D7 (2026-11-17–2026-11-20) |
| Worker slot | B |
| Dependencies | [T03](T03-collector-leases.md), [T04](T04-conditional-fetching.md), [T05](T05-parser-contracts.md) |
| Required review | standard |
| External gates | G04: an available local runner for the elapsed soak |
| Shared merge/contract locks | live-collector |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Only three approximately 31-second live cycles are recorded. A successful sample is not long-running reliability. This task has roughly six hours of active work plus at least 72 elapsed hours; start the soak early enough to finish in week two.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T07/<run-id>/`; commit sanitized reports only.

## Read first

- `scripts/reliability.py`
- `scripts/collect.py`
- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/worker.py`
- `docs/verification.md`
- `config/sources.live.json`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `scripts/reliability.py`
- `scripts/soak_report.py (new)`
- `backend/tests/test_reliability_runner.py (new)`
- `docs/verification/collection-soak.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Add resumable run manifests with real UTC timestamps, source/city budgets, checkpoint IDs and per-cycle counts. Support at least 72 hours without removing existing bounded one-shot usage.

2. Use six-hour scheduled cycles for Kraków and the currently enabled three portals. Keep at most one discovery page, two new details and four due rechecks per provider per cycle, plus bounded control/retry requests. Keep OLX disabled and respect robots/backoff.

3. Run a separate deterministic failure drill with fake sources: timeout, 403, 429, malformed HTML, duplicate delivery, worker restart and confirmed removal. Do not induce failures against real portals.

4. Record attempted/eligible/deferred/missed cycles, checked/changed/delisted counts, bytes, lease losses, queue depths and history growth. Distinguish an unavailable runner from a provider failure.

5. A runner reboot/sleep pauses real elapsed evidence; resume from the manifest and report the gap. Never fill gaps with fabricated success or reset the clock to hide downtime.

6. Retain private raw reports under ignored .local storage; commit only aggregate sanitized evidence. If no real removal occurs, explicitly report that limitation and retain the controlled removal test as separate evidence.

7. Start the live soak from a pinned reviewed code/config commit and do not edit its worktree or database while it is running. At final integration, identify any later collector/ingestion changes that invalidate the evidence and rerun the affected checks; report version gaps instead of pretending the entire final candidate ran for 72 hours.

## Acceptance criteria

- **T07-AC01:** The harness resumes without duplicate scheduled cycles or corrupted state after interruption.

- **T07-AC02:** The live report covers at least 72 real elapsed hours and at least 12 eligible six-hour intervals; missing duration is BLOCKED_EXTERNAL or INCOMPLETE, not a passing result.

- **T07-AC03:** Every enabled provider has at least one successful real check; every attempted/deferred/missed cycle is accounted for.

- **T07-AC04:** No transport/parser failure causes a false inactive observation or duplicate new-match/price-drop notification.

- **T07-AC05:** Unchanged observations obey one checkpoint per source/day; every actual rent/status change is retained.

- **T07-AC06:** The report distinguishes live evidence, injected failures, runner gaps and unobserved real removals.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T07-TC01 — covers T07-AC01

**Given:** A persisted soak manifest after two cycles.

**When:** Terminate and resume runner.

**Then:** Completed cycles are not rerun; next cycle ID/time is preserved.

### T07-TC02 — covers T07-AC02, T07-AC03

**Given:** An available runner and approved existing source budgets.

**When:** Run the bounded 72-hour schedule.

**Then:** Actual timestamps and at least 12 eligible intervals are recorded; all gaps are explicit.

### T07-TC03 — covers T07-AC04

**Given:** Separate fixture source emits 403/timeout/malformed response.

**When:** Run failure drill.

**Then:** Previous active source stays active/unknown according to policy; no false removal/alert.

### T07-TC04 — covers T07-AC04, T07-AC05

**Given:** Fixture source repeats unchanged, repriced, inactive and same-price relist events.

**When:** Replay with process restarts.

**Then:** Daily checkpoints and genuine changes remain correct; same-price repost stays quiet.

### T07-TC05 — covers T07-AC03, T07-AC06

**Given:** Provider blocked for multiple scheduled intervals.

**When:** Generate aggregate report.

**Then:** Failures/deferred counts remain visible; success percentage excludes no failures silently.

### T07-TC06 — covers T07-AC06

**Given:** No live advert delists during the run.

**When:** Write verification result.

**Then:** Real removal remains unverified; fixture removal is not relabelled as live evidence.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_reliability_runner.py -q`
- Use the task’s bounded soak command; do not run it in default CI

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Resumable soak runner and aggregate report
- Private manifest/log paths and exact start/end times
- Explicit remaining live-data uncertainty
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No operating-system startup task or paid cloud runner installation.
- Do not claim a 30-day SLA from this experiment.
