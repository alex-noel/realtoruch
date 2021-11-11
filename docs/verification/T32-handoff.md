# T32 integration handoff

- Status: **LOCAL_PARTIAL**; code candidate `a17cf16f4e6c3c33d629684fd6a75685eb147b53`. The final documentation commit records compatible evidence without changing application code.
- Actual verification: 12 November 2026 Europe/Warsaw; exact UTC times below. Every commit used `scripts/commit.py`, five calendar years back for both dates.
- User-visible result: the eight-step Kraków journey, account/owner messaging and reviewed correction behavior pass in the integrated candidate. The live operational gate remains open.
- Scope exception: the user explicitly authorized GitHub push after the original plan's no-push instruction. [Hosted run](https://github.com/alex-noel/realtoruch/actions/runs/43119698856) passed on application-identical `d56ae2313f34c574877e16050ea3affd67b064b6`; the follow-up only changes grants, their regression and documentation. Cloud deployment remains excluded.

## Acceptance and required cases

| AC | Status | Cases and evidence |
| --- | --- | --- |
| T32-AC01 | PASS reporting | TC01/TC06: [all 157 ACs and 162 cases](core-acceptance.json), current evidence and explicit gates. Historical task rows are superseded only where the acceptance index names later evidence. |
| T32-AC02 | PASS locally | TC01/TC02: fresh locked hosted install, SQLite upgrades and real registry-based PostgreSQL startup/upgrade, preserved rows, immutable checksums and actual role tests. |
| T32-AC03 | PASS locally | TC03: full 36-case web run; real local auth/API and isolated SQLite/file mail, canonical seen/favorite/relist/delist, two-user publishing/messages and erasure. |
| T32-AC04 | PASS for reviewed paths | TC04: real-service and deterministic races plus independent P1 reproductions/fixes. No unresolved P0/P1 found; bounded review is not exhaustive proof. |
| T32-AC05 | PASS honest reconciliation; soak INCOMPLETE | TC05: native load target pass, emulated history target fail, paired local restore and config evidence; T07 duration/provider/version gap explicitly open. |
| T32-AC06 | PASS reporting; overall LOCAL_PARTIAL | TC06: [release readiness](../release-readiness.md) separates local, external and deployment gates. Authorized source push is the only change to the original external-action exclusion. |

All six T32 test cases pass for the specified checks/reporting; this does not mark T07-AC02/AC03 complete.

## Exact profiles and results

Working directory: repository root. Python 3.12.9, Node 24.6.0, macOS 15.7.7 arm64; disposable PostgreSQL 16.15/Elasticsearch 8.19.6. Each command exited 0. The runner records clean worktrees and exact SHAs: offline/web at `d56ae2313f34c574877e16050ea3affd67b064b6`, final services at `a17cf16f4e6c3c33d629684fd6a75685eb147b53`. Backend application/frontend files are unchanged between these revisions.

```sh
PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t26/.local/verification/T26/tools/darwin-arm64:$PATH make verify ARGS='--run-id t32-release-offline'
PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify-services ARGS='--run-id t32-roles-services'
PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/Users/alexnoel/Library/Caches/ms-playwright make verify-web ARGS='--run-id t32-release-web'
```

| Profile | Actual UTC interval | Passed / failed / skipped | Private aggregate artifact |
| --- | --- | --- | --- |
| `offline` | `2026-11-11T23:21:48.648195+00:00`–`2026-11-11T23:22:27.149194+00:00` | 392 / 0 / 115 | `.local/verification/T01/t32-release-offline/report.json` |
| `services` | `2026-11-11T23:32:32.917131+00:00`–`2026-11-11T23:34:38.737368+00:00` | 240 / 0 / 0 | `.local/verification/T01/t32-roles-services/report.json` |
| `web` | `2026-11-11T23:21:48.648198+00:00`–`2026-11-11T23:24:32.966207+00:00` | 36 / 0 / 0 | `.local/verification/T01/t32-release-web/report.json` |

TypeScript and all 122 frontend unit tests also passed. The hosted native job uses the same unchanged frontend files; iOS/Android output is JS/Hermes bundle validation. Configuration-only commands and exact arguments are in `.local/verification/T32/config-final/report.json` (13 passed, zero failed/skipped). `ruff check --select E9,F63,F7,F82`, the CI boundary checker with a full comparison SHA, migration registry validation, plan/link checks and whitespace checks passed. A first boundary invocation with a short SHA was rejected and corrected; it did not inspect or mutate data.

Earlier clean `71c0a07` profiles passed 378 offline tests (100 explicit service-only skips), 211 real-service tests and 36 browser cases. The broader profiles were repeated because independent review then required the identity-alert correction. Initial hosted `cf7b146` passed services/web/native but failed one outdated oversized-title fixture; `b88bc5d` made the fixture exercise a valid public description under a small test byte budget, preserving production sanitizer and index limits.

## Review, compatibility and recovery

The two P1 fixes and their precise semantics are in [release readiness](../release-readiness.md). Worker A's correction suite passed 61 lifecycle/regression cases, 26 delivery/concurrency cases and 29 final correction cases with no skips. Worker D independently reproduced false merge/split/hidden-restore drops and verified rollback of a notification, its queued email, floor and event acknowledgements. The favorite-visibility case passed both SQL engines. The parent inspected the final changes and reran the complete matrix.

No additional migration was needed for T25/T32. Registered rentals versions are 001–006, 008–010; auth 001, 004, 005. The final grant follow-up allows the API to insert notifications and push deliveries during a merge; the actual-role regression independently reproduced each missing privilege and passed with both grants, while denying unrelated roles. Reapply `infra/sql/grants.sql` before updating an existing API deployment. The current candidate supports the documented tracked-baseline upgrades; untracked persistent schemas require reviewed adoption, not automatic metadata insertion. Restore uses paired quiesced snapshots; see [T27](T27-handoff.md). Reverting code does not undo committed moderator identity decisions or baseline changes; restore a verified backup or use an audited forward correction for data recovery.

The frozen corpus SHA is `511c5f6c7ef1e4a16bffb706ddd94e30a18e8c13423ea37eea0bd541da40940c`. Formal metrics were recorded on `a775a776885ce6c4269f209ad99aaf82138cd647`, whose matcher and candidate-selection code are unchanged in this candidate. Regression suites also execute these rows; no pristine statistical holdout claim is made. The production sequence and adversarial injected matchers run in the final offline suite.

T25/T08 timings and T28 configuration measurements are compatible earlier-revision evidence, not newly rerun performance samples. Final services re-exercise current history/filter/candidate/revision/alert semantics and both restore engines. Raw databases, captures, mail, logs and browser state remain ignored; committed reports are sanitized aggregates.

## Outstanding gates

T07 remains incomplete on immutable `b3782cc`, with final-version coverage also missing. Automatic OLX, actual external mail/push, installed mobile, map/domain inputs and every cloud deployment/SLA/PITR claim remain open as detailed in [release readiness](../release-readiness.md). The pinned runner was observed through `2026-11-11T23:34:20.875698Z`; no OS scheduler or app automation was installed. No resource provisioning, external mail, cloud image push or app publication was performed.
