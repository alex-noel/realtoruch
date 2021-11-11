# T29 — Validate an actually available OLX access path without bypassing access controls

**User instruction:** I want OLX collection enabled only when we can demonstrate a working, authorized, bounded source path, with honest status when it remains unavailable.

| Field | Instruction |
| --- | --- |
| Tier / priority | CONDITIONAL / P1 |
| Active effort estimate | 4 hours |
| Proposed window | D8–D10 (2026-11-23–2026-11-25) |
| Worker slot | UNALLOCATED |
| Dependencies | [T06](T06-olx-onboarding.md), [T07](T07-collection-soak.md) |
| Required review | strong: source evidence and data minimization |
| External gates | G01 |
| Shared merge/contract locks | source-config, portal-contracts |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Automatic OLX currently returns 403; one manually imported item is not evidence of an operational scraper. A user account is not assumed to fix the block or provide a bulk listing API.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T29/<run-id>/`; commit sanitized reports only.

## Read first

- `docs/source-connectors.md`
- `scripts/source_preflight.py (from T06)`
- `backend/realtoruch/connectors.py`
- `backend/realtoruch/portals.py`
- `backend/tests/test_olx.py`
- `docs/verification/collection-soak.md (from T07)`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `docs/verification/olx-access.md (new)`
- `backend/realtoruch/connectors.py (verified adapter corrections only)`
- `backend/realtoruch/portals.py (verified payload corrections only)`
- `backend/tests/fixtures/portals/* (sanitized additions only)`
- `backend/tests/test_olx.py`
- `.env.example (placeholders only, if new settings are needed)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Require G01: a documented usable portal/feed path and any needed credentials supplied privately, plus authorization for the bounded test. Read current provider conditions using primary sources if an integration assumption depends on them. Do not create accounts, accept terms or assume account login bypasses 403.

2. Run T06 preflight using configured host allowlists, robots/access behavior and budgets. At most one search page and three detail/recheck requests in the first sample, further restricted by existing provider limits. Keep host pacing global across cities and stop on access-blocked states.

3. In an isolated catalog, ingest a small real sample and recheck only those same records after the allowed interval. Verify stable source IDs, rent/area/city/owner interpretation and canonical/outbox outcomes. Separate genuinely observed changes from fixture-driven repricing/delisting tests.

4. Never use residential proxies, CAPTCHA solving, copied browser session secrets, randomized evasion or unapproved private endpoints. If a provider only exposes owner-authorized account ads rather than public search, document that capability and do not label it a whole-market feed.

5. Store credentials only in ignored local env/secret files and redact network artifacts. Commit only minimally sufficient sanitized fixtures with provenance and the observed schema; do not commit contact numbers, session cookies or a raw portal dump.

6. Mark the adapter live_sample_verified only after actual search/detail/recheck evidence. Enable collection config only for the demonstrated scope and budget. Otherwise keep automatic OLX disabled/blocked and list the exact provider input needed; passing offline tests is not live access.

## Acceptance criteria

- **T29-AC01:** The available access method and scope are documented without assuming login solves access denial.

- **T29-AC02:** Live requests stay within approved host/access/pacing and sample budgets.

- **T29-AC03:** A real isolated sample ingests and rechecks with correct source/canonical state.

- **T29-AC04:** Secrets and raw personal data never enter Git or shared evidence.

- **T29-AC05:** Capability/status accurately distinguishes portal/feed/manual import and blocked/live-verified access.

- **T29-AC06:** Offline parser/collector regressions remain green after any adapter correction.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T29-TC01 — covers T29-AC01, T29-AC05

**Given:** G01 absent or provider returns 403.

**When:** Run preflight.

**Then:** Task is BLOCKED_EXTERNAL; no evasion or misleading enabled status occurs.

### T29-TC02 — covers T29-AC02, T29-AC03

**Given:** Verified usable source path with a tiny approved sample.

**When:** Collect one page and at most three details/rechecks.

**Then:** Request counts/timing and real ingested IDs match recorded evidence.

### T29-TC03 — covers T29-AC03

**Given:** Same real sample after a permitted interval.

**When:** Recheck and compare source/canonical snapshots.

**Then:** Unchanged records do not duplicate logical notifications; observed changes are labelled as real or absent.

### T29-TC04 — covers T29-AC01, T29-AC05

**Given:** Provider access supports only a seller's own offers.

**When:** Inspect capability contract.

**Then:** Documentation does not advertise marketplace-wide discovery.

### T29-TC05 — covers T29-AC04

**Given:** Credential-bearing local config and captured payloads.

**When:** Review sanitized fixture/report diff.

**Then:** No token, cookie, phone number or unnecessary source HTML is committed.

### T29-TC06 — covers T29-AC06

**Given:** Corrected parser and historical offline fixtures.

**When:** Run source/collection regressions.

**Then:** Existing cases still pass, including fail-closed challenge handling.


## Verification commands and checks

- `python3 scripts/source_preflight.py --help, then explicit bounded OLX network profile`
- Run focused OLX/parser/collection tests
- Inspect git diff for sensitive fixture/config content

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Verified live-access report or exact blocker report
- Only evidence-backed adapter/config corrections
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not promise that an OLX account unblocks 403.
- Do not create an account or bypass access restrictions to satisfy the acceptance gate.
