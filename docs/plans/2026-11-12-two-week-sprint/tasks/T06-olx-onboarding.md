# T06 — Prepare a configurable OLX feed/access preflight

**User instruction:** I want you to prepare a clear OLX onboarding path so a supplied accessible feed or authorized public transport can be validated without rewriting the collector.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 4 hours |
| Proposed window | D3 (2026-11-16) |
| Worker slot | D |
| Dependencies | [T05](T05-parser-contracts.md) |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | source-configuration |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Scheduled OLX HTTP/robots requests returned 403, while public Chrome pages were readable without signing in. An account has not been shown to fix automated access. Existing feed, portal and manual-snapshot modes must remain distinct.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T06/<run-id>/`; commit sanitized reports only.

## Read first

- `config/sources.json`
- `config/sources.live.json`
- `backend/realtoruch/connectors.py`
- `backend/realtoruch/portals.py`
- `scripts/import_html.py`
- `docs/source-connectors.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `scripts/source_preflight.py (new)`
- `config/sources.json`
- `config/sources.live.json`
- `backend/tests/test_source_preflight.py (new)`
- `docs/source-connectors.md`
- `config/provider-feed.example.json (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Add an opt-in preflight command that validates configured mode, exact HTTPS hosts, city scope, secret variable presence without printing values, page/request budgets and expected mapping contract.

2. Default preflight is offline. An explicit --network option may fetch at most one robots page, one discovery/feed page and one detail page within current pacing; no collection is enabled automatically.

3. Return machine-readable states: not_configured, ready_offline, blocked_access, unsupported_payload and live_sample_verified. Include what evidence is missing, not an unsubstantiated success label.

4. For a provider feed, document source-field mapping, pagination, observation time, explicit removals, permitted reuse and authentication setup. Never invent an OLX partner endpoint or assume account-scoped APIs expose the whole marketplace.

5. Keep secrets in environment variables/ignored files, redact URLs with query secrets, and stop on 401/403/challenge. Preserve manual HTML import as a separate operator path.

6. Generate a short operator checklist that T29 can execute after access is actually supplied; prepare tests entirely with fake HTTP responses.

## Acceptance criteria

- **T06-AC01:** Offline preflight works with no OLX credentials and performs zero outbound requests.

- **T06-AC02:** Missing configuration, invalid host and absent token are reported without leaking values.

- **T06-AC03:** A mock valid feed and a mock public page both map to existing RawListing contracts.

- **T06-AC04:** A network denial returns blocked_access and leaves OLX disabled.

- **T06-AC05:** The live_sample_verified state requires actual successful fetch-and-parse evidence, never only configuration validation.

- **T06-AC06:** The onboarding report distinguishes automated collection from manual snapshot import.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T06-TC01 — covers T06-AC01

**Given:** Disabled default OLX configuration.

**When:** Run offline preflight with network mocked to raise.

**Then:** Report not_configured/ready_offline accurately; no request occurs.

### T06-TC02 — covers T06-AC02

**Given:** Private-host URL, credential-bearing URL and missing secret variable.

**When:** Run validation.

**Then:** Invalid inputs rejected; secret canary absent from output.

### T06-TC03 — covers T06-AC03

**Given:** Mock authorized feed and known portal fixture.

**When:** Run bounded sample mapping.

**Then:** Canonical source identity and required fields validate.

### T06-TC04 — covers T06-AC04

**Given:** 403 robots or challenge response.

**When:** Run --network preflight with fake transport.

**Then:** blocked_access; no retry storm, no enable/config write.

### T06-TC05 — covers T06-AC05

**Given:** Valid config but no actual network sample.

**When:** Generate report.

**Then:** State is ready_offline, never live_sample_verified.

### T06-TC06 — covers T06-AC06

**Given:** Operator-imported snapshot only.

**When:** Summarize source status.

**Then:** Report explicitly labels manual import and unresolved automated transport.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_source_preflight.py backend/tests/test_olx.py -q`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Preflight command, sample feed contract and operator handoff
- Offline test evidence
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not create/login to accounts, accept terms, bypass challenges or purchase access.
- Live OLX verification belongs to conditional task T29.
