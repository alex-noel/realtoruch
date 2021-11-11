# T09 — Create a labelled duplicate-identity evaluation dataset

**User instruction:** I want you to measure duplicate matching against explicit positive, negative and ambiguous examples before anyone changes matching thresholds.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D1 (2026-11-12) |
| Worker slot | C |
| Dependencies | None |
| Required review | data review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | dedupe-evaluation |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Current matching uses address/size/rooms plus contact or image evidence, and special Morizon–Gratka/repost rules. Existing tests are useful but do not provide a labelled evaluation baseline. This task measures behavior; it must not weaken matching to make scores look better.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T09/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/dedupe.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/normalization.py`
- `backend/tests/test_ingestion.py`
- `backend/tests/test_identity_review.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/tests/fixtures/dedupe/pairs.jsonl (new)`
- `backend/tests/fixtures/dedupe/README.md (new)`
- `scripts/evaluate_dedupe.py (new)`
- `backend/tests/test_dedupe_evaluation.py (new)`
- `docs/verification/dedupe-baseline.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Create at least 200 labelled pairs: >=80 same-home, >=80 different-home and >=40 ambiguous/do-not-auto-merge. Labels must have a short rationale, scenario family and provenance; synthetic variations are not represented as 200 independently observed real cases.

2. Cover shared agency phone across multiple flats, building without unit number, different units/floors, stock/reused photos, resized URL variants, missing address/coordinates, same-price reposts, Morizon–Gratka shared IDs, conflicting cities and room/area boundaries.

3. Keep contact evidence synthetic/keyed and images local or synthetic URLs. Do not crawl/download private photos or use actual phone numbers for this dataset.

4. Split development and holdout scenario families with fixed IDs; prevent near-identical generated variants crossing the split. Freeze the holdout before T10 changes thresholds.

5. Output confusion counts, precision/recall on known labels, ambiguous auto-merge count and per-scenario failures. Treat ambiguous automatic merges as unsafe; report zero-division honestly.

6. Include an ingestion-level mode showing canonical counts and alert suppression on sequences, not only pair-function booleans. Save exact dataset hash, code SHA and parameters in the report.

## Acceptance criteria

- **T09-AC01:** Dataset schema validates and each pair has a unique ID, label, rationale and scenario family.

- **T09-AC02:** Required pair counts and all scenario classes exist without private-data leakage.

- **T09-AC03:** Evaluation is deterministic and reports per-label/per-scenario results and failures.

- **T09-AC04:** Holdout families are separated and frozen before matcher tuning.

- **T09-AC05:** Sequence evaluation reveals both duplicate canonical homes and false same-home merges.

- **T09-AC06:** The baseline report distinguishes synthetic fixture accuracy from real-market accuracy and does not fabricate a performance claim.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T09-TC01 — covers T09-AC01, T09-AC02

**Given:** Valid dataset plus copies with duplicate IDs/missing rationale.

**When:** Run validation.

**Then:** Valid dataset passes; malformed copies fail with pair ID and reason.

### T09-TC02 — covers T09-AC02

**Given:** Shared-phone/different-unit and stock-photo examples.

**When:** Inspect labels and run matching.

**Then:** Hard negatives and ambiguity are represented explicitly, regardless of current matcher outcome.

### T09-TC03 — covers T09-AC03

**Given:** Same code, dataset hash and seed.

**When:** Run evaluation twice.

**Then:** Metrics and ordered failure IDs are identical.

### T09-TC04 — covers T09-AC04

**Given:** Near-identical variants from the same scenario family.

**When:** Validate split.

**Then:** No family leaks across development and holdout partitions.

### T09-TC05 — covers T09-AC05

**Given:** One home reposted twice and two genuinely distinct units.

**When:** Run sequence mode.

**Then:** Report shows expected canonical counts and any incorrect notifications/merges.

### T09-TC06 — covers T09-AC06

**Given:** A matcher that rejects every pair.

**When:** Evaluate.

**Then:** Recall is zero, undefined precision handled explicitly; no misleading perfect score.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_dedupe_evaluation.py -q`
- `.venv/bin/python scripts/evaluate_dedupe.py --help`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Versioned labelled dataset, validator and deterministic evaluator
- Frozen baseline report with failure IDs for T10
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No automatic matcher threshold changes in this task.
- No claim that a small synthetic dataset establishes live-market precision.
