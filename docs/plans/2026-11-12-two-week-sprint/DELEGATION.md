# Delegation, ownership and integration instructions

## Dispatch one bounded prompt

Give a worker the complete `tasks/Txx-*.md` file, this repository, its assigned worktree and reviewed dependency commits. The file is written as your instruction to that worker. It contains its own constraints and completion format; the worker does not need to read all 36 tasks.

A ready task requires:
- Dependencies listed in the manifest have reviewed code/contracts available on the assigned base.
- Required local tools and fixture inputs exist, or missing setup can be completed inside that task.
- The integrator has assigned the relevant shared-file merge slots.
- A required external gate is satisfied before dependent live actions. Independent offline preparation can proceed while it is missing.

Do not dispatch a dependent implementation against a guessed response/schema. A draft consumer may use an agreed fixture contract while waiting, but it cannot claim integration acceptance until the real producer is tested.

Every task begins PLANNED. Use IN_PROGRESS, IMPLEMENTED_LOCAL, VERIFIED, BLOCKED_EXTERNAL or FAILED_REVIEW in handoffs. Never convert not-run into passed. The shared task files are specifications; do not silently edit their ACs to match implementation.

## Worker isolation and commits

Use one isolated Git worktree/checkout per active task, with branches such as `codex/t08-versioned-search-index`. The integrator supplies the base revision. Do not let multiple workers edit the same checkout, developer database, ports or running collector.

At the beginning, inspect `git status`, `AGENTS.md`, the assigned task and relevant code. Preserve unrelated changes. Use `rg` for targeted discovery. Stay within the named file/function scope; explain any necessary scope expansion to the integrator.

Commit only intended task changes. Every newly created commit must use:

```sh
python3 scripts/commit.py -m "Describe the concrete change"
```

The helper sets both author and committer dates to the same timestamp five calendar years before actual commit time in Europe/Warsaw, with the documented February 29 fallback. Do not run plain `git commit`. Do not backdate test reports, source observations, application data or file timestamps. Do not push.

Avoid Git operations that manufacture a commit without the helper. The integrator can apply a reviewed patch with `git apply --index`, or prepare a cherry-pick with `git cherry-pick --no-commit`, then create the resulting commit with the helper. For a merge, prepare with `git merge --no-commit --no-ff`, resolve/review, then use the helper. Do not rewrite unrelated shared history or blindly cherry-pick an entire stack containing already integrated dependency commits. If rebasing would create new commits, use a reviewed patch-based integration path instead.

Private test data, credentials, source captures, mail files and database dumps belong in ignored run directories. Only sanitized aggregates/fixtures should be committed.

## Shared-file ownership and merge locks

Separate worktrees prevent filesystem collisions; they do not prevent semantic conflicts. A “lock” in a task means the integrator serializes **contract changes and merge review** for that area, not that everyone must wait to write isolated tests. Publish a short contract before consumers begin.

| Hotspot | Primary tasks | Coordination rule |
| --- | --- | --- |
| `worker.py` | T03, T04, T08, T26 | Collector hooks first; T08 extracts indexing; T26 adds logging only. No broad formatting. |
| `models.py`, local upgrades, migration registry | T04, T08, T11, T13, T15, T16; stretch owners | Each task owns only its added fields/table/version. Integrator combines entries and checks every database. |
| `ingest.py` / identity | T08, T10, T25; T33/T35 optional | Revision hook → identity correction → measured query optimization. Review the final transaction/lock order together. |
| `api.py` | T08, T11, T12, T15, T26 | Scope by route/helper; extract focused modules where it reduces conflicts. Preserve auth/visibility checks. |
| `marketplace.py` | T08, T10, T15, T16 | Revision/lock hooks before closure/read-cursor integrations; T15 and T16 can develop separately but must be reviewed together. |
| `auth.py` / `auth_jobs.py` | T13, T14, T15, T26 | Separate claim/session/export/metrics sections; never replace a dependency's code wholesale. |
| `email_alerts.py` | T13, T15; T30/T36 optional | Fencing first, closure hook second, template/config changes last. |
| `App.tsx` / `api.ts` | T14, T19, T21 | Prefer small session/link/search hooks. Integrator serializes root hooks; test latest-query and latest-session races together. |
| `MarketplaceDialog.tsx` | T17, T20; T24/T36 optional | Extract inbox/uploader sections where useful. Keep a single owner per overlapping UI section. |
| Package locks / frontend test tooling | T14, T18; T24 optional | One unit-test runner (T14), one browser runner (T18). Rebase dependency changes onto the latest lock and run locked install. |
| Shared service integration tests | T01, T03, T08, T10, T13, T15 | Use namespaced fixtures; prefer task-specific test modules to a large shared append-only file. |
| Infra/grants | T28 | Collect schema/identity needs from all producers before final render/role tests. |

Do not “resolve” conflicts by choosing ours/theirs for whole files. Compare both intended behaviors and rerun tests that exercise their interaction.

## Database migration reservations

T01 owns the migration registry and upgrade convention. Rental/auth numbering are separate namespaces; auth has its own existing 001 and 004 history. Do not assume every database contains every numeric prefix.

| Database | Version | Owner | File | Condition |
| --- | --- | --- | --- | --- |
| rentals | 005 | T04 | `infra/sql/005_collection_fetch_state.sql` | If durable fetch validators need schema state |
| rentals | 006 | T08 | `infra/sql/006_search_revision.sql` | Core |
| rentals | 007 | T11 | `infra/sql/007_history_indexes.sql` | Only indexes justified by EXPLAIN |
| rentals | 008 | T13 | `infra/sql/008_delivery_leases.sql` | Core |
| auth | 005 | T13 | `infra/sql/005_delivery_leases_auth.sql` | Core; independent auth namespace |
| rentals | 009 | T15 | `infra/sql/009_account_closure.sql` | Core |
| rentals | 010 | T16 | `infra/sql/010_message_read_cursors.sql` | Core |
| rentals | 011 | T23 | `infra/sql/011_media_assets.sql` | Stretch only |
| rentals | 012 | T33 | `infra/sql/012_location_provenance.sql` | Stretch only |
| rentals | 013 | T35 | `infra/sql/013_phone_fingerprint_lifecycle.sql` | Stretch only |
| rentals | 014 | T36 | `infra/sql/014_message_email.sql` | Stretch only |

Preserve all applied baseline migrations. Register new files in numeric order **within the owning database**. Do not rename another task's reservation. If a conditional migration is unnecessary, leave it unregistered and document the unused reservation; gaps do not require fake no-op migrations.

Every schema task must support:
1. Fresh PostgreSQL installation through the registry.
2. Upgrade from the baseline PostgreSQL schema with existing rows.
3. Fresh SQLite creation and the corresponding additive existing-SQLite upgrade.
4. Repeat startup/migration without duplicate columns, lost values or unwanted notification baselining.
5. A safe recovery note. Prefer tested backup/restore or a forward fix over destructive automatic down-migrations.

Parallel worker databases are disposable, branch-specific schemas. They are **not** supported long-lived production upgrade paths between arbitrary half-merged task branches. Recreate an isolated test database when changing those branches; never recreate the user's live database. Integrate the full selected registry before applying it to any persistent developer catalog. Final acceptance tests upgrade the supported baseline to the integrated target and verify migration checksums.

If a new migration becomes necessary outside these reservations, the integrator assigns it before coding the DDL; no worker independently chooses “the next number.”

## Tests and evidence

T01 owns isolated commands/reports. T14 owns `npm run test:unit`. T18 owns `npm run test:e2e` and finishes `make verify-web`. Before a planned command exists, the prompt clearly marks it new; workers must implement/document it rather than claim it ran.

Use meaningful tests at these layers:
- **Pure/unit:** parsers, normalization, geometry, state machines, fake clocks.
- **SQLite:** compatibility and ordinary local API/lifecycle behavior.
- **PostgreSQL:** transactions, locks, fencing, isolation and role grants with separate sessions and deterministic barriers.
- **Elasticsearch:** actual bulk/version conflicts, visibility and rebuild alias behavior.
- **Browser:** actual production web controls and local services, not screenshots alone.
- **Native:** parser/adapter/export checks separately from installed iOS/Android acceptance.
- **External:** bounded named gates only; mock/preview results never substitute for live reception/access.

A new test should fail for the defect/invariant it is meant to catch. Use controlled failure injection where the task requests it, then remove the injected defect before handoff. Do not add tests that simply restate implementation constants without testing behavior. Do not introduce arbitrary sleeps to “fix” races.

Every report includes actual command and exit code, passed/failed/skipped counts, run ID, current code/config/schema version, real time, machine/runtime versions and sanitized artifact paths. For a concurrency test, include the controlled ordering and final invariant. For a benchmark, include dataset seed/counts, hardware, request mix, warm-up, duration, raw sample counts and percentile calculation.

Required service tests cannot be green by skipping. Missing prerequisites are BLOCKED, not “all passed.” An AC such as a p95 target is failed when the target is missed, even when the diagnostic report is excellent.

## Reviewer checks and escalation

The integrator reviews all tasks. A stronger independent reviewer must approve:
- Canonical merge/split rules and state preservation (T08–T10).
- Claim/ack races, lease fencing and idempotency (T03/T13).
- Auth/session/export/erasure boundaries (T14/T15).
- Public DTOs, upload authorization, phone identity and service grants (T12/T23/T28/T35).
- Evidence claims in T22/T29/T30/T32.

If scope or evidence is unclear, the worker should reproduce the ambiguity, write the smallest concrete question and continue independent authorized work. Do not ask the user to approve every reversible code edit. Escalate actual missing credentials, devices, provider capability or external sending permission through the integrator.

After roughly two productive hours with no progress on a blocker, report the failed approaches and exact missing condition; do not burn an entire day repeating attempts. Do not bypass a portal denial or weaken an AC just to complete a task.

## Integration checkpoints

- **D1:** contracts, fixtures, registry and run namespaces accepted.
- **D3–D4:** collector/index/delivery fencing and identity test evidence reviewed; live soak pinned and running.
- **D6–D7:** account/read-cursor/public-search contracts converge; first complete browser journey accepted.
- **D8:** feature freeze, conditional scope chosen, performance/config/recovery evidence ready.
- **D9–D10:** T32, independent review and fixes only.

Allow at most one unreviewed high-risk change in each shared state machine. If critical-path tasks slip, stop optional work and use buffer. Do not launch all 36 prompts at once. With extra workers, expand bounded fixture/test/review work; do not parallelize incompatible schema/UI changes without a contract and owner.

The final report must be self-contained, evidence-linked and explicit about remaining blockers. No push/deployment follows automatically from completion.
