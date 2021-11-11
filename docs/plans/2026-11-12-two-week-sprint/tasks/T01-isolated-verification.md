# T01 — Make verification reproducible and isolated for parallel workers

**User instruction:** I want you to give every worker a reproducible, isolated way to run the existing app and test suites, so parallel workers cannot overwrite each other’s data, ports or evidence.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D1 (2026-11-12) |
| Worker slot | A |
| Dependencies | None |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | build-tooling |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The baseline has 132 recorded passing backend tests, but five service tests require manually started PostgreSQL/Elasticsearch instances. Local launchers use fixed ports and shared .local paths. There is no .github/workflows directory. Do not rebuild existing business features.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T01/<run-id>/`; commit sanitized reports only.

## Read first

- `Makefile`
- `scripts/local.py`
- `scripts/dev.py`
- `backend/tests/conftest.py`
- `backend/tests/test_service_integration.py`
- `scripts/postgres_backup_check.py`
- `backend/pyproject.toml`
- `apps/mobile/package.json`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `scripts/verify.py (new)`
- `scripts/local.py`
- `scripts/dev.py`
- `Makefile`
- `backend/tests/conftest.py`
- `backend/tests/test_service_integration.py`
- `docs/testing.md (new)`
- `infra/sql/migrations.json (new)`
- `backend/realtoruch/migrations.py (versioned SQLite upgrade hook and registry validation)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Add make verify for SQLite tests plus TypeScript, and make verify-services for disposable PostgreSQL 16 and Elasticsearch 8.19.6 tests. Use Python 3.12 and Node 24 from the repository’s existing lockfiles; do not upgrade the application framework.

2. Namespace temporary directories, Docker project/container names, databases, index namespaces and bound loopback ports by an explicit run ID. Start two independent runs without sharing mutable state. Keep the existing interactive defaults intact.

3. Own every process/container you start: record identifiers, wait for readiness with deadlines, and clean up only that run’s resources on success, failure and SIGINT. Never use docker system prune, broad pkill or the developer’s catalog.

4. Write a JSON report containing run ID, real UTC start/end, commands, exit codes, passed/failed/skipped counts, platform versions and sanitized artifact paths. A service profile must fail if its required tests are skipped.

5. Add an explicit migration registry separating rental and auth databases. Preserve 001–004 unchanged; reserve future numbers from the plan. Integration tests must use the same ordered registry as the operator validation command.

6. Document a single setup/run command per profile and machine requirements. Publish the frontend test-runner hook for T18 without silently declaring browser tests implemented.

7. Define verify as the offline Python/TypeScript/unit-test baseline, verify-services as required real PostgreSQL/Elasticsearch checks, and verify-web as a documented future hook completed by T18. Before that hook exists, absence must report NOT_IMPLEMENTED rather than a success. Expose the shared test command and env contract to T14/T18 without introducing competing frontend runners.

8. Separate PostgreSQL SQL-file migration ordering from SQLite's existing upgrade_local path. Keep explicit per-database applied-version/checksum metadata and reject duplicate versions or changed applied files. Define an additive local-upgrade hook for later tasks; PostgreSQL-only DDL must not be executed verbatim against SQLite.

## Acceptance criteria

- **T01-AC01:** A clean checkout can run the documented SQLite/TypeScript profile using the committed locks.

- **T01-AC02:** Two service profiles can run concurrently with disjoint ports, databases/indexes and output directories.

- **T01-AC03:** A forced setup/test failure returns nonzero, preserves diagnostics and removes only the owning run’s resources.

- **T01-AC04:** Required PostgreSQL/Elasticsearch tests cannot pass the service profile by skipping.

- **T01-AC05:** The migration registry applies 001–004 to the correct databases and detects duplicate/out-of-order version entries.

- **T01-AC06:** Reports contain enough information to reproduce the run and exclude tokens, real emails, phone fingerprints and source captures.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T01-TC01 — covers T01-AC01

**Given:** Fresh checkout with supported Python/Node.

**When:** Install locks and run make verify.

**Then:** Baseline tests and TypeScript pass; report records actual counts.

### T01-TC02 — covers T01-AC02

**Given:** Two unique run IDs and Docker available.

**When:** Launch service profiles concurrently.

**Then:** Both pass; no bound-port, database or Elasticsearch-index collision.

### T01-TC03 — covers T01-AC03

**Given:** An unrelated sentinel container and a running task profile.

**When:** Force a test failure and interrupt cleanup.

**Then:** Task resources stop; sentinel and existing .local catalogs remain unchanged.

### T01-TC04 — covers T01-AC04

**Given:** Service URLs missing or service tests deliberately skipped.

**When:** Run the service profile.

**Then:** Nonzero exit explicitly identifies required skipped tests.

### T01-TC05 — covers T01-AC05

**Given:** Fresh rental/auth databases and a copied registry with a duplicate version.

**When:** Apply the valid registry, then validate the invalid copy.

**Then:** Correct schemas succeed; duplicate version fails before applying SQL.

### T01-TC06 — covers T01-AC06

**Given:** Synthetic secrets placed in a failing request fixture.

**When:** Export report/log artifacts.

**Then:** Secret strings are absent; failure identity and exit code remain available.


## Verification commands and checks

- `make verify`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Runner, migration registry, Make targets and docs/testing.md
- One passing isolated SQLite report and two overlapping service-run reports
- Failure/cleanup evidence
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No CI workflow in this task; T02 owns it.
- No live portal fetch, external mail, deployment or dependency-major upgrade.
