# T09 synthetic duplicate matching baseline

## Identity and outcome

- Task: T09 — labelled duplicate identity evaluation
- Status: VERIFIED (local implementation and fixture evaluation)
- Base revision: `2d9a22db7277b16e694dc29bf4e3d72e5df3ac1b`
- Initial result commit: `1ac33e99800672c2c0540056930390a0899fed9b`. Review follow-up commit: `37852d51f5a95ad063d4b5df2e04a95d61d7e1d4` (both created with `python3 scripts/commit.py`)
- Git metadata: both initial commits and review follow-up have matching author and committer dates five calendar years before their respective commit times in Europe/Warsaw; review follow-up date `2021-11-11T21:11:44+01:00`.
- Actual verification date: 2026-11-11, Europe/Warsaw (CET, UTC+01:00)
- Outcome: added a frozen, synthetic-only labelled dataset and deterministic evaluator that calls the existing production matcher and ingestion path. No production behavior or matching thresholds were changed.

## Dataset and baseline

The dataset contains 220 authored synthetic pairs: 80 same-home, 100 different-home and 40 ambiguous. Every record has a unique ID, a pair-specific rationale, family, fixed partition and synthetic provenance. It covers same-home reposts, Morizon–Gratka shared IDs, address/photo evidence, resized image URLs, shared agency contact, unit/floor conflicts, stock photos, missing address/location, conflicting cities, room/area boundaries, and buildings without a unit number. All contact evidence is deterministic synthetic keyed material; image URLs use `.test`; there are no portal captures or real phone numbers.

The fixed family split is enforced in code. Development and holdout each include positive, negative and ambiguous labels; no family or generated variant crosses the boundary. Holdout families are reserved for T10. Labels were authored from stated scenario truth before matcher execution, not inferred from matcher results. Generated synthetic repetitions increase scenario coverage but do not represent independently observed real listings.

The evaluator calls `realtoruch.dedupe.matching_property` on every pair. Current production behavior on this fixture yielded known-label counts TP=80, FP=0, TN=100, FN=0 (precision 1.0, recall 1.0). This is not evidence of live-market accuracy: cases are synthetic, deliberately bounded to implemented evidence patterns, and not representative of portal prevalence or messy source data. The meaningful baseline failure is that 20/40 ambiguous cases were automatically merged. All 20 are holdout `building_no_unit` cases (`T09-201`–`T09-220`), where exact building address plus shared synthetic contact/photo passes the matcher despite unknown unit identity. The other 20 ambiguous missing-address/location cases were not merged. Holdout known-label counts are TP=20, FP=0, TN=80, FN=0; holdout also has all 20 ambiguous cases auto-merged. These are descriptive fixture results only, not a tuning recommendation.

Production `ingest()` plus `process_alerts()` sequence mode used in-memory SQLite and a synthetic saved search. It ingested one source, two same-price reposts of that home, and two distinct apartments in the same building with known conflicting unit/floor evidence. The correct result is 3 canonical homes and exactly 3 logical `new_match` notifications, one per actual home. Baseline met those exact outcomes: reposts shared a canonical; both distinct units remained separate; notification kinds were `new_match: 3`; no notifications were lost or duplicated. This evaluates user-facing logical inbox notifications, not downstream email transport.

Fault-injection tests use the same production ingestion and alert code. A forced-match matcher collapses all three true homes into one canonical (3 false-merge pairs), emits one notification and loses two expected home notifications. A reject-all matcher creates 5 canonical rows instead of 3, including two duplicate canonical records for the reposted home, and emits 5 `new_match` notifications (2 extras). Thus sequence metrics reveal both false merges/lost notifications and duplicate canonicals/excess notifications; these injected results are diagnostic tests, not production baseline results.
Machine/runtime: macOS 15.6 Darwin arm64 (`uname -a`: Darwin 24.6.0, Apple T6041); Python 3.12.9; repository `.venv`; pytest from that locked environment. No cloud services, live portals or external mail were used. No schema or migration changes were required.

## Reproduction and artifacts

Run from the repository root:

```sh
PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/evaluate_dedupe.py
PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_dedupe_evaluation.py -q
PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/evaluate_dedupe.py --help
```

Evaluation run ID: `T09-20261111T201127Z`; report generated `2026-11-11T20:11:27.414041+00:00` (20:11:27 UTC / 21:11:27 Europe/Warsaw). Dataset SHA-256: `511c5f6c7ef1e4a16bffb706ddd94e30a18e8c13423ea37eea0bd541da40940c`. Evaluator SHA-256: `ef3d597e005ada243e2630ab24a969c5b760631b93718392ab8a78ef1a27ae64`. Production matching source Git SHA: `ae893a6adba99617fe883bb9e81967566616124b`; combined source path SHA-256: `f1212025ff84175d858357afa8e54f89de173f3d9c471e1cc8ee10f171f73854`. Workspace Git SHA captured at run: `7184752495b4f9257812550958f6d542bc309c10`. No random seed is used. Full per-label, per-family metrics and ordered failure IDs are in [dedupe-baseline.json](dedupe-baseline.json); source dataset is `backend/tests/fixtures/dedupe/pairs.jsonl`.

### Acceptance criteria

| AC | Status | Evidence |
| --- | --- | --- |
| T09-AC01 | PASS | Dataset validator plus malformed duplicate-ID and missing-rationale cases in T09-TC01. |
| T09-AC02 | PASS | 220 rows, 80 positives, 100 negatives, 40 ambiguous; required scenario families and synthetic-only contact/image checks; T09-TC02. |
| T09-AC03 | PASS | Deterministic production-matcher evaluation, per-label/per-family metrics and sorted failures; T09-TC03. |
| T09-AC04 | PASS | Enforced family-level development/holdout manifest and variant leak test; T09-TC04. Holdout remains frozen for T10. |
| T09-AC05 | PASS | SQLite-backed production `ingest()` + `process_alerts()` sequence asserts 3 canonical homes and exactly 3 logical notifications; forced-match and reject-all injections expose lost/excess notifications and false merges/duplicates; T09-TC05. |
| T09-AC06 | PASS | Synthetic-only limitation in this report; reject-all matcher gives recall 0 and precision null; T09-TC06. |

### Test cases

| Test case | Result | Evidence |
| --- | --- | --- |
| T09-TC01 | PASS | Valid dataset succeeds; duplicate ID, empty rationale, nested raw phone/email fields and empty provenance fail with pair ID and reason. |
| T09-TC02 | PASS | Shared-agency-phone, unit/floor and stock-photo negatives plus ambiguous cases explicitly labelled and evaluated. |
| T09-TC03 | PASS | Two evaluations over same fixed rows produce identical metric object and ordered failure IDs. |
| T09-TC04 | PASS | Fixed family split validator rejects a moved variant; all families occupy exactly one partition. |
| T09-TC05 | PASS | Production ingestion + `process_alerts()` confirms exact three logical notifications for three true homes. Forced-merge injection yields 3 false-merge pairs and 2 lost notifications; reject-all injection yields 2 duplicate canonicals and 2 extra notifications. |
| T09-TC06 | PASS | Injected reject-all matcher gives TP=0, recall=0.0 and undefined precision (`null`), without a spurious perfect score. |

## Executed verification

| Command | Result | Counts / artifact |
| --- | --- | --- |
| `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_dedupe_evaluation.py -q` | Exit 0 | 9 passed, 0 failed, 0 skipped. |
| `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/evaluate_dedupe.py --help` | Exit 0 | CLI help rendered. |
| `PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/evaluate_dedupe.py --output docs/verification/dedupe-baseline.json` | Exit 0 | 220 pair report, fixed hash and metrics in JSON artifact. |

## Remaining limits and review

This is a synthetic behavioral baseline, not a market estimate. The generated cases are authored around known matcher conditions and omit capture noise, real portal drift, geography distribution and measured prevalence. The holdout explicitly surfaces unsafe ambiguity merges; do not hide these rows or describe the known-label 1.0 scores without the ambiguity counts and synthetic limitation. Independent data review should inspect the 20 unit-unknown false merges before T10 uses this holdout. No public contract, schema, migration, alert delivery behavior or production matching behavior was altered. Recovery is removal of the new fixture/evaluator/report files; no data migration is involved.

Recursive validation rejects raw phone/email field names anywhere in candidate, incoming, source, and other nested fields; provenance must be nonempty text. The report includes per-partition prediction coverage (`predicted == expected`); an evaluator exception aborts instead of silently removing a pair from metric denominators. Final report coverage was 220/220 overall, 100/100 development, and 120/120 holdout. Precision is represented as JSON `null` when there are zero positive predictions.

Initial verification attempts: the first pytest invocation used a nonexistent worktree-relative `.venv/bin/pytest` (exit 127); it was corrected to the repository environment Python `-m pytest`. An intermediate syntax error while adding partition metrics caused one collection failure; fixed before final run. Final commands listed above were rerun successfully.
