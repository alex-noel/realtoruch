# T32 — Integrate the sprint and produce a truthful local release-candidate report

**User instruction:** I want one integrated, tested local release candidate with a precise statement of which user journeys work, which external gates remain and what must happen before any deployment.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 8 hours |
| Proposed window | D9–D10 (2026-11-24–2026-11-25) |
| Worker slot | A with independent integrator review |
| Dependencies | [T01](T01-isolated-verification.md), [T02](T02-ci-quality-gates.md), [T03](T03-collector-leases.md), [T04](T04-conditional-fetching.md), [T05](T05-parser-contracts.md), [T06](T06-olx-onboarding.md), [T07](T07-collection-soak.md), [T08](T08-versioned-search-index.md), [T09](T09-dedupe-evaluation.md), [T10](T10-identity-correctness.md), [T11](T11-history-storage.md), [T12](T12-public-search-contract.md), [T13](T13-delivery-fencing.md), [T14](T14-session-resilience.md), [T15](T15-account-data-lifecycle.md), [T16](T16-message-read-cursors.md), [T17](T17-inbox-client.md), [T18](T18-browser-regression-suite.md), [T19](T19-source-status-and-request-lifecycle.md), [T20](T20-web-accessibility-and-performance.md), [T21](T21-native-links-and-lifecycle.md), [T25](T25-load-and-query-budgets.md), [T26](T26-operational-metrics-and-runbooks.md), [T27](T27-restore-and-erasure-recovery.md), [T28](T28-infrastructure-config-alignment.md) |
| Required review | strong: independent integration review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | integration-branch, release-evidence |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Individual worker completion is insufficient when identity, outbox, auth, UI and infrastructure contracts interact. This task runs after the core changes are integrated and uses current evidence; it cannot inherit a pass from the old 132-test baseline.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T32/<run-id>/`; commit sanitized reports only.

## Read first

- `docs/plans/2026-11-12-two-week-sprint/README.md`
- `docs/verification.md`
- `docs/feature-status.md`
- `docs/testing.md (from T01)`
- `docs/operations/* (from sprint tasks)`
- `docs/verification/* (from sprint tasks)`
- `infra/sql/migrations.json (from T01)`
- `scripts/commit.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `docs/verification.md (current dated verification section)`
- `docs/feature-status.md (evidence-backed status updates)`
- `docs/release-readiness.md (new)`
- `docs/deployment.md (verified prerequisites only)`
- `Minimal integration fixes with the owning task's review`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Integrate only reviewed task branches using the shared-file/migration order. Reconcile DTOs, configs and test harnesses before running the full suite. Every newly created commit, including merge/amend commits, must use scripts/commit.py with both required backdated timestamps; do not push or deploy.

2. Verify clean fresh-schema startup and upgrade from a synthetic baseline using rental migrations 001–004 and auth migrations 001/004. Run required SQLite, real PostgreSQL/Elasticsearch, frontend typecheck, web production build/browser suite, native JS exports, backup/restore and configuration checks without silently skipping required services.

3. Run the eight-step Kraków journey from an empty account/search baseline, plus two-user publishing/messages and auth/erasure scenarios. Exercise collection overlap, stale index versions, late delivery acknowledgement, identity correction and restored pending erasure using deterministic tests.

4. Audit each task's numbered ACs against actual test results and artifact links. Record exact current commit/runtime/schema versions and real wall-clock test times; backdated Git metadata is not the date of verification. Review at least the identity, auth, account erasure, outbox and public-private boundaries independently of their implementing worker.

5. Require the >=72-hour soak evidence for full local operational verification. If G04 is unavailable or the run contains an uninvestigated correctness failure, label the result LOCAL_PARTIAL. Distinguish LOCAL_VERIFIED, EXTERNAL_BLOCKED and NO_GO: external SMTP/installed mobile/OLX/map gates remain named and do not become green because fixtures passed.

6. Close no release with an unresolved P0 privacy/data-loss/identity/notification regression. Use reserved buffer for corrections and focused rechecks, not new features. Update the feature ledger honestly: three demonstrated providers do not equal four live scrapers, local verification is not deployment/SLA, and original Otodom-wide parity remains a separate backlog.

## Acceptance criteria

- **T32-AC01:** All integrated core ACs have a current evidence/status record with no hidden skipped prerequisite.

- **T32-AC02:** Fresh install and baseline-to-current migrations pass against both supported SQL modes and real service tests.

- **T32-AC03:** The complete rental/account/owner-message journey passes on the integrated web candidate.

- **T32-AC04:** Concurrency, erasure, indexing and delivery regressions have no unresolved P0 findings.

- **T32-AC05:** Soak/load/restore/config evidence is current and any unmet target is explicitly reported.

- **T32-AC06:** The release-readiness report separates local verification, external blockers and deployment readiness without provisioning/pushing anything.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T32-TC01 — covers T32-AC01, T32-AC02

**Given:** Clean checkout of integrated candidate and fresh isolated services.

**When:** Run the full declared verification matrix.

**Then:** All required profiles execute; absent services cause failure/blocked status, not a green skip.

### T32-TC02 — covers T32-AC02

**Given:** Synthetic pre-sprint schema/data for both databases.

**When:** Apply manifest migrations and execute lifecycle reads/writes.

**Then:** Upgrade preserves old state and fresh-install results agree.

### T32-TC03 — covers T32-AC03

**Given:** Two users and a clean Kraków catalog.

**When:** Run browser journey, owner publication/messages and account erasure.

**Then:** Exact logical alerts, seen/favorite states, privacy and map/list visibility agree.

### T32-TC04 — covers T32-AC04

**Given:** Forced collection/index/delivery/identity/erasure races.

**When:** Run deterministic concurrency suite.

**Then:** No stale ownership commit, stale index resurrection, duplicate logical event or private-data resurrection occurs.

### T32-TC05 — covers T32-AC05

**Given:** Soak, benchmark and restore reports tied to current compatible commits.

**When:** Reconcile targets, duration, failures and schema versions.

**Then:** Missing/failed evidence remains explicit; no old result is silently reused as a fresh pass.

### T32-TC06 — covers T32-AC01, T32-AC06

**Given:** Conditional tasks blocked or only partly verified.

**When:** Produce release-readiness matrix.

**Then:** LOCAL_VERIFIED/LOCAL_PARTIAL and external blockers are stated separately; no cloud or production claim is made.


## Verification commands and checks

- `make verify`
- `make verify-services`
- `make verify-web`
- Run documented native JS export, soak-report, load and restore profiles
- Run T28 config-only validation
- `git diff --check and inspect actual commit dates via git log`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Integrated local candidate and evidence-linked release-readiness report
- Updated feature ledger, remaining blockers and next decision list
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not push, deploy, publish apps, create cloud resources or declare full Otodom feature parity.
- Do not broaden the sprint with stretch work during the final integration window.
