# T05 — Expand portal contract fixtures and detect markup drift

**User instruction:** I want you to make the four portal parsers fail clearly when source pages change, without silently dropping valid rentals or turning parser failures into delistings.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D1 (2026-11-12) |
| Worker slot | B |
| Dependencies | None |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | portal-parsers |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Otodom, Gratka and Morizon have bounded live samples; OLX has one browser-verified detail and synthetic fixtures. Expand offline contracts first. Existing fixture provenance is in backend/tests/fixtures/portals/README.md.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T05/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/portals.py`
- `backend/realtoruch/connectors.py`
- `backend/realtoruch/schemas.py`
- `backend/tests/test_portals.py`
- `backend/tests/test_olx.py`
- `backend/tests/fixtures/portals/README.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/portals.py`
- `backend/tests/test_portals.py`
- `backend/tests/test_olx.py`
- `backend/tests/fixtures/portals/*`
- `docs/source-connectors.md`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Add a fixture matrix for each portal: active, changed rent, explicit unavailable, no results, pagination, sale/non-rental, missing required fields, consent/challenge page and structurally changed page.

2. Use sanitized synthetic or permitted reduced fixtures with provenance, source page type, inspected date and replaced fields. No live phone numbers, cookies, tokens or full copyrighted capture dumps in Git.

3. Define bounded parser error codes by stage and source. Distinguish a confirmed empty result list from an unrecognized page shape. Keep raw markup and content out of metrics/logs.

4. Preserve rental/PLN checks, Polish decimal parsing, district/city validation, unknown-fee semantics, advertiser assertions and stable external identities. A missing room count is not an inferred number.

5. Test explicit removal only when a previously valid source record exists. Parser/transport/challenge failures must leave previous active state and freshness semantics unchanged.

6. Record a source contract report with supported shapes and remaining uncertainty. Any optional fresh read must obey current source budgets; do not require network access for tests.

## Acceptance criteria

- **T05-AC01:** Every portal has the nine required scenario classes or an explicit unsupported case with a failing-safe test.

- **T05-AC02:** Valid known shapes still normalize the same identity, amounts and location.

- **T05-AC03:** Unrecognized/challenge markup produces a parser/access error, never an empty successful catalog.

- **T05-AC04:** Non-rental, non-PLN and incomplete mandatory fields do not enter ingestion.

- **T05-AC05:** Only explicit confirmed unavailability creates an inactive observation for a known listing.

- **T05-AC06:** Fixtures and failure artifacts contain no real contact secrets or unredacted session data.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T05-TC01 — covers T05-AC01, T05-AC02

**Given:** Each portal’s active/detail fixture.

**When:** Parse and compare the normalized contract.

**Then:** Exact source ID, rent, fees, area, rooms, advertiser and city match expected values.

### T05-TC02 — covers T05-AC01, T05-AC03

**Given:** Empty-result fixture versus changed DOM/challenge fixture.

**When:** Run discovery.

**Then:** Empty fixture succeeds with zero; changed/challenge fixture fails distinctly.

### T05-TC03 — covers T05-AC02, T05-AC04

**Given:** Decimal commas, nonbreaking spaces, unknown fees and price ranges.

**When:** Parse parameterized fixtures.

**Then:** PLN rounding is deterministic; ambiguity stays unknown or rejects required fields.

### T05-TC04 — covers T05-AC04

**Given:** Sale, foreign currency or missing room count.

**When:** Parse detail.

**Then:** No RawListing is emitted; reason is recorded.

### T05-TC05 — covers T05-AC05

**Given:** Known active listing followed by unavailable, 403, timeout and malformed page.

**When:** Run lifecycle adapter.

**Then:** Only unavailable creates inactive; other cases preserve state.

### T05-TC06 — covers T05-AC06

**Given:** Fixture/contact canaries and sanitizer audit.

**When:** Scan tracked fixtures and logs.

**Then:** No live number, authorization header, session token or full capture remains.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_portals.py backend/tests/test_olx.py backend/tests/test_connectors.py -q`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Fixture matrix and regression tests
- Source contract/provenance notes
- List of unsupported shapes with fail-safe behavior
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not enable OLX automated fetching.
- Do not expand cities or crawl scope in this task.
