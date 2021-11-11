# T27 — Prove backup restoration preserves rental state and resumes account erasure safely

**User instruction:** I want repeatable backup-and-restore evidence that favorites, history, notifications and pending account erasure remain correct after a local database recovery.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D6–D7 (2026-11-19–2026-11-20) |
| Worker slot | C |
| Dependencies | [T11](T11-history-storage.md), [T15](T15-account-data-lifecycle.md) |
| Required review | strong: data lifecycle and recovery |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | backup-harness |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

SQLite and PostgreSQL backup checks already passed on an earlier baseline. The new lifecycle fences and migrations require richer restore fixtures and a reproducible verification manifest. This does not execute cloud disaster recovery.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T27/<run-id>/`; commit sanitized reports only.

## Read first

- `scripts/backup_check.py`
- `scripts/postgres_backup_check.py`
- `backend/realtoruch/migrations.py`
- `backend/realtoruch/auth_jobs.py`
- `backend/realtoruch/api.py`
- `infra/sql/migrations.json (from T01)`
- `docs/deployment.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `scripts/backup_check.py`
- `scripts/postgres_backup_check.py`
- `scripts/restore_manifest.py (new, if shared helpers are needed)`
- `backend/tests/test_restore_contract.py (new)`
- `docs/operations/backup-restore.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Build isolated SQLite and PostgreSQL fixtures with two accounts, owned and imported ads, canonical aliases, seen/favorites, delisted favorites, historical prices, unread messages, pending search/email outbox entries and an account deletion accepted before its erasure job runs.

2. Back up rentals and auth consistently with a documented quiescence or snapshot procedure. Record schema versions, commit, database identifiers, row counts, file digests, backup start/end and restore destination in a manifest. Do not copy real credentials or the user's live catalog into tracked artifacts.

3. Restore into new namespaced databases and run application-level assertions, not just row counts. Verify account isolation, canonical routes, history, unread state, saved delisted homes and pending outbox delivery using a file mail sink.

4. Resume the pre-existing erasure job after restore and prove closure fences prevent restored credentials or in-flight writes from recreating private data. Re-running cleanup and outbox drain must be idempotent, preserving only the documented minimum retained records.

5. Fail safely for corrupt/truncated dumps, version mismatch, unwritable destinations and interrupted restore. Never drop or overwrite an unrecognized database. Cleanup must require its own run manifest/namespace, preserving unrelated resources.

6. Document measured backup/restore duration and the snapshot's recovery-point limit, local encryption/access/retention responsibilities and any gaps in multi-database consistency. Report RPO/RTO measurements for this test only; do not claim a production recovery guarantee or rewrite cloud backup policy without approval.

## Acceptance criteria

- **T27-AC01:** Both SQLite and PostgreSQL restoration use isolated destinations with validated manifests.

- **T27-AC02:** Restored application behavior includes favorites, historical prices, aliases, messages and private-account separation.

- **T27-AC03:** Pending erasure completes after restore without private-data resurrection.

- **T27-AC04:** Outbox and cleanup replay preserve logical idempotency and send only to a local file sink.

- **T27-AC05:** Corrupt/incompatible/interrupted restores fail without damaging unrelated data.

- **T27-AC06:** The runbook records actual recovery times, snapshot consistency limits and safe operator commands.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T27-TC01 — covers T27-AC01, T27-AC02

**Given:** Synthetic rentals/auth snapshot with known lifecycle state.

**When:** Restore to a new SQLite namespace and exercise APIs.

**Then:** Expected states and account boundaries match the manifest and assertions.

### T27-TC02 — covers T27-AC01, T27-AC02

**Given:** Equivalent PostgreSQL fixture.

**When:** Backup and restore with roles/schema checks.

**Then:** Application-level assertions and migrations match; counts alone are not treated as sufficient.

### T27-TC03 — covers T27-AC03, T27-AC04

**Given:** Accepted deletion and pending auth erasure job at snapshot time.

**When:** Restore, attempt account writes, then drain jobs twice.

**Then:** Writes remain denied; erasure completes once and retained rows follow documented policy.

### T27-TC04 — covers T27-AC04

**Given:** Pending logical email/search events in backup.

**When:** Drain restored outboxes twice using file transport.

**Then:** One logical notification state persists and no external message is sent.

### T27-TC05 — covers T27-AC05

**Given:** Truncated dump, wrong digest/version and unwritable destination.

**When:** Attempt each restore.

**Then:** Each returns nonzero before replacing data; unrelated sentinel database remains unchanged.

### T27-TC06 — covers T27-AC05, T27-AC06

**Given:** Interrupted restore with owned and unrelated resources.

**When:** Resume/clean using manifest and inspect timings.

**Then:** Only owned resources change; report includes measured duration and consistency caveats.


## Verification commands and checks

- `python3 scripts/backup_check.py --help, then documented isolated profile`
- `python3 scripts/postgres_backup_check.py --help, then documented isolated profile`
- Run focused restore/account lifecycle tests

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Expanded restore scripts and manifests
- Reproducible SQLite/PostgreSQL recovery evidence and runbook
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not restore into the user's live database or a cloud instance.
- Do not add homemade cryptography or commit database dumps.
