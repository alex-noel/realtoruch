# T34 — Evaluate photo similarity as review evidence without changing automatic identity

**User instruction:** I want a measured experiment showing whether photo similarity can help human duplicate review, without automatically merging unrelated apartments.

| Field | Instruction |
| --- | --- |
| Tier / priority | STRETCH / P2 |
| Active effort estimate | 8 hours |
| Proposed window | Unallocated; select only after core acceptance |
| Worker slot | UNALLOCATED |
| Dependencies | [T09](T09-dedupe-evaluation.md) |
| Required review | strong: false-positive assessment |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | dedupe-evaluation |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Text/phone/location identity already exists and T09 supplies an evaluation framework. Reused stock photos, agency watermarks and similar interiors make image similarity insufficient proof of a shared property.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T34/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/dedupe.py`
- `backend/realtoruch/identity_review.py`
- `scripts/evaluate_dedupe.py (from T09)`
- `backend/tests/fixtures/dedupe/* (from T09)`
- `docs/feature-status.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `scripts/evaluate_photo_similarity.py (new)`
- `backend/realtoruch/photo_similarity.py (new, offline/private utility)`
- `backend/tests/fixtures/photo_similarity/* (new synthetic/owned fixtures only)`
- `backend/tests/test_photo_similarity.py (new)`
- `docs/evaluation/photo-similarity.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Create a labelled corpus of at least 60 image pairs covering resize/recompression, brightness, crop, watermark, stock-photo reuse, same building/different units and unrelated similar interiors. Use generated or user-owned/licensed local fixtures with provenance; do not download portal images without permission.

2. Implement a bounded offline perceptual-hash or similarly lightweight baseline with pinned dependencies, explicit decoded-size/memory limits and deterministic outputs. Keep source images/derived hashes private and do not transmit them to external AI/image services.

3. Split development/evaluation by original-image/property family, preventing transformed copies from leaking across the split. Freeze the split/hash and report precision/recall, false positives, false negatives and threshold sensitivity separately for obvious variants and difficult negatives.

4. Produce candidate evidence for manual review only: score, pair IDs and explanation of limitations. Do not change canonical identities, risk labels, notifications, publication status or automatic merge decisions based on photo scores in this task.

5. Test reused stock photos from unrelated properties and near-identical interiors explicitly. A perfect synthetic result is not a real-market accuracy claim. Record sample count, provenance limitations and a recommendation to proceed/reject/further-evaluate with concrete reasons.

6. Document a future integration contract that could consume T23's validated derivatives or another authorized local source, with cleanup/account-erasure expectations. Do not make the experiment depend on optional media uploads or add a background downloader.

## Acceptance criteria

- **T34-AC01:** The labelled corpus contains the specified positive/negative families with provenance.

- **T34-AC02:** The utility is deterministic, offline and bounded against oversized/corrupt images.

- **T34-AC03:** Evaluation has a frozen family-separated split and inspectable error examples.

- **T34-AC04:** No automatic identity, notification or moderation behavior changes.

- **T34-AC05:** Private images/hashes are absent from public APIs and external services.

- **T34-AC06:** The report distinguishes measured synthetic performance from unknown market performance and states the next decision.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T34-TC01 — covers T34-AC01, T34-AC03

**Given:** Corpus with transformations from shared originals.

**When:** Validate split membership.

**Then:** No original/property family spans development and evaluation; counts/classes meet the contract.

### T34-TC02 — covers T34-AC02

**Given:** Repeated identical inputs and corrupt/oversized fixtures.

**When:** Run utility under fixed limits.

**Then:** Scores repeat exactly; invalid inputs fail safely without excess resource use.

### T34-TC03 — covers T34-AC03

**Given:** Frozen evaluation set and several thresholds.

**When:** Generate metrics and examples.

**Then:** Precision/recall/counts agree with manually checked sample calculations.

### T34-TC04 — covers T34-AC04

**Given:** High-similarity pair from two unrelated homes.

**When:** Run existing ingestion and the experiment.

**Then:** Canonical IDs, risk state and alert counts remain unchanged.

### T34-TC05 — covers T34-AC04, T34-AC05

**Given:** Stock-photo reuse and agency watermarks.

**When:** Inspect candidate output and public API responses.

**Then:** Evidence is review-only; no hash/image metadata leaks publicly or leaves the machine.

### T34-TC06 — covers T34-AC06

**Given:** Synthetic-only dataset.

**When:** Read recommendation and artifact provenance.

**Then:** Report explicitly limits conclusions and does not claim production dedupe accuracy.


## Verification commands and checks

- Run focused photo-similarity tests
- `python3 scripts/evaluate_photo_similarity.py (new, documented offline arguments)`
- Run existing identity regression tests

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Offline experiment, labelled fixtures and evaluation report
- A bounded future integration recommendation
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not auto-merge homes, accuse agents or download/copy portal photos.
- Do not add an external vision model or cloud inference service.
