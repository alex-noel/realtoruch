# T02 — Add CI gates for Python, TypeScript, builds and isolated service tests

**User instruction:** I want you to add a CI pipeline that catches regressions automatically before workers’ changes are integrated.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D2 (2026-11-13) |
| Worker slot | A |
| Dependencies | [T01](T01-isolated-verification.md) |
| Required review | standard |
| External gates | G07 (hosted run only; local implementation is ungated) |
| Shared merge/contract locks | build-tooling, ci |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

There is currently no tracked CI workflow. Use T01’s isolated runner rather than inventing a second service setup. CI configuration is in scope; deploying, publishing packages and triggering paid native/cloud builds are not.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T02/<run-id>/`; commit sanitized reports only.

## Read first

- `docs/testing.md (from T01)`
- `scripts/verify.py (from T01)`
- `Makefile`
- `backend/requirements-runtime.lock`
- `backend/requirements-dev.lock`
- `apps/mobile/package-lock.json`
- `infra/helm/realtoruch`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `.github/workflows/ci.yml (new)`
- `scripts/ci_checks.py (new, if needed)`
- `docs/testing.md`
- `dependency policy/config files only if necessary`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Run on pull requests and pushes to the integration/default branches using read-only repository permissions. Pin supported action releases to reviewed immutable SHAs; document update ownership.

2. Create independent Linux jobs for Python/TypeScript, PostgreSQL/Elasticsearch integration, web export and native JavaScript exports. Never describe JS exports as signed mobile builds.

3. Use locked installs, explicit Python/Node versions, bounded timeouts and cache keys including lockfiles and platform. Avoid installing unbounded latest packages.

4. Set all connectors disabled and mail transport to file/mock during CI. No portal credentials, SMTP credentials or cloud identity should be required by default.

5. Run fatal Python lint checks and diff/secret-boundary checks without introducing thousands of unrelated formatting changes. Add dependency audit reporting; fail on newly introduced high/critical runtime findings, and record owner/expiry for accepted exceptions.

6. Upload sanitized failure reports and synthetic screenshots/traces for seven days. Add an optional browser-test hook activated when T18 lands. Fork PRs must not access secrets or execute privileged workflow contexts.

7. Hosted GitHub execution is external gate G07 and is not authorized by this task. Validate triggers/permissions/artifact selection statically and run equivalent commands locally; leave hosted-run URL/result unset instead of marking a nonexistent run green.

## Acceptance criteria

- **T02-AC01:** The workflow declares required PR/push checks for all four categories, and their local equivalents pass; hosted execution is reported separately as pending until an authorized push.

- **T02-AC02:** A deliberately failing backend assertion or TypeScript error causes the corresponding job to fail.

- **T02-AC03:** The service job executes required real PostgreSQL/Elasticsearch tests with zero required skips.

- **T02-AC04:** CI succeeds without external service credentials and does not contact listing portals.

- **T02-AC05:** Artifact uploads exclude credentials, real listing captures and private developer databases.

- **T02-AC06:** Native export output is labelled bundle validation; no image/package/app-store publishing step exists.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T02-TC01 — covers T02-AC01, T02-AC02

**Given:** A test branch with a temporary intentional Python failure.

**When:** Run the equivalent CI command/job.

**Then:** Python job fails with useful report; revert the failure before handoff.

### T02-TC02 — covers T02-AC01, T02-AC02

**Given:** A temporary TypeScript type error.

**When:** Run the TypeScript job.

**Then:** Nonzero exit; no misleading overall pass.

### T02-TC03 — covers T02-AC03

**Given:** Service containers disabled or unreachable.

**When:** Run service profile.

**Then:** Job fails, rather than falling back to skipped service tests.

### T02-TC04 — covers T02-AC04

**Given:** Empty secret store and outbound portal calls replaced with failing sentinels.

**When:** Run default jobs.

**Then:** Default jobs pass; no portal/mail/cloud connection attempted.

### T02-TC05 — covers T02-AC05

**Given:** Synthetic credential canary in a failure fixture.

**When:** Inspect uploaded artifact selection.

**Then:** Canary and local auth databases are excluded or redacted.

### T02-TC06 — covers T02-AC06

**Given:** Rendered workflow and native-export logs.

**When:** Review all steps.

**Then:** No push/deploy/signing/publishing command; bundles labelled accurately.


## Verification commands and checks

- `make verify`
- `make verify-services`
- `docker compose config --quiet`
- Review rendered workflow with the repository’s YAML tooling

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- CI workflow and reproducible local equivalents
- Sanitized validation log; record CI execution as pending if not yet authorized/pushed
- Dependency finding policy with no invented clean audit
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not push just to trigger CI; hand the commit to the integrator.
- Do not enable macOS/EAS paid build jobs or cloud credentials.
