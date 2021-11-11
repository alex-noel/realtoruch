# T10 — Fix duplicate identity errors and concurrent correction races

**User instruction:** I want you to make automatic and moderator-driven identity decisions conservative and transactionally safe, preserving users’ saved homes, seen prices and notification history.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 8 hours |
| Proposed window | D3–D4 (2026-11-16–2026-11-17) |
| Worker slot | C |
| Dependencies | [T08](T08-versioned-search-index.md), [T09](T09-dedupe-evaluation.md) |
| Required review | mandatory identity/concurrency review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | canonical-writes, marketplace-backend |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Use T09’s recorded failure cases as evidence. Merge/split code exists, but races among ingestion, published-advert edits, correction and alias resolution need explicit PostgreSQL coverage. Coordinate with T08’s revision contract.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T10/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/dedupe.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/identity_review.py`
- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/alerts.py`
- `backend/tests/test_identity_review.py`
- `docs/verification/dedupe-baseline.md (from T09)`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/dedupe.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/identity_review.py`
- `backend/realtoruch/marketplace.py (lock order only)`
- `backend/tests/test_identity_review.py`
- `backend/tests/test_service_integration.py`
- `docs/verification/dedupe-after.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. First reproduce each selected T09 failure. Require explicit unit/floor/location conflict rejection. Shared phone, generic photos or approximate location alone must not prove same-home identity; prefer a missed duplicate over a false merge.

2. Define one transaction lock order for city identity, canonical IDs and advert/source rows. Resolve aliases after acquiring the relevant lock and revalidate preconditions. Opposite-direction merges must not create cycles or self-aliases.

3. Preserve canonical aliases, observations, favorite price floors, seen prices, saved-search baselines, reports, pending genuine alerts and notification uniqueness through merge/split.

4. A correction must not manufacture a new-match or price-drop notification solely because identity changed. Preserve hidden state and update T08 revisions/tombstones for all affected homes.

5. Return a recoverable 409 for stale correction preconditions; do not swallow database errors or retry non-idempotent actions blindly. Audit the effective source/target IDs and reason in the committed transaction.

6. Run the frozen holdout once after development changes. Require zero false/ambiguous merges in the labelled dataset; target >=80% same-home recall but document any conservative exclusions. Do not relabel hard cases to pass.

## Acceptance criteria

- **T10-AC01:** All hard-negative and ambiguous evaluation cases avoid automatic merging.

- **T10-AC02:** Known positive recall is measured and >=80%, or the task reports the shortfall instead of claiming acceptance.

- **T10-AC03:** Concurrent ingestion/edit/correction cannot deadlock indefinitely, lose a source or form an alias cycle.

- **T10-AC04:** Merged/split favorites, seen state and price floors remain valid and old links resolve to the effective home.

- **T10-AC05:** Identity-only correction emits no new rental alert and preserves pending genuine changes.

- **T10-AC06:** Hidden state, audit records and search revisions remain consistent after commit or rollback.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T10-TC01 — covers T10-AC01, T10-AC02

**Given:** Frozen T09 development/holdout datasets.

**When:** Run evaluator before and after fix.

**Then:** Zero unsafe merges; recall and unchanged labels recorded.

### T10-TC02 — covers T10-AC03

**Given:** Two transactions merge A into B and B into A.

**When:** Release barriers concurrently.

**Then:** One valid result and one 409/serialized no-op; no cycle or indefinite wait.

### T10-TC03 — covers T10-AC03, T10-AC06

**Given:** Published advert edit overlaps merge/split.

**When:** Run on PostgreSQL with bounded lock timeout.

**Then:** Source ownership and revision order are consistent; any conflict is recoverable.

### T10-TC04 — covers T10-AC04, T10-AC05

**Given:** Seen/favorited duplicate with overlapping saved searches and queued genuine price change.

**When:** Merge, process alerts, then follow old ID.

**Then:** One saved canonical home, preserved seen/floor, no correction-only alert; genuine change retained.

### T10-TC05 — covers T10-AC04, T10-AC05

**Given:** A mistaken merged home is split.

**When:** Apply later updates to each source.

**Then:** Each source updates its intended home; shortlists retain both without a false new-match.

### T10-TC06 — covers T10-AC06

**Given:** Exception inserted immediately before correction commit.

**When:** Rollback and retry.

**Then:** No partial aliases, moved observations, missing favorites or orphan audit records.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_ingestion.py backend/tests/test_identity_review.py -q`
- `make verify-services`
- `.venv/bin/python scripts/evaluate_dedupe.py --help`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Targeted identity fixes with race reproductions
- Before/after evaluation with unchanged dataset hash
- Lock-order and conflict-response documentation
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No perceptual image matching or geocoder integration; those are stretch tasks.
- Do not delete historical observations to simplify corrections.
