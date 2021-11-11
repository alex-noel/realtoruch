# T01 handoff

## Identity and outcome

- Task: T01; status: IMPLEMENTED_LOCAL (some acceptance remains unverified).
- Base: `2d9a22db7277b16e694dc29bf4e3d72e5df3ac1b`. Result: the commit containing this handoff, created using `python3 scripts/commit.py`.
- Verification: 2026-11-11 21:00–21:06 Europe/Warsaw (UTC+1).
- Isolated offline and real-service profiles now produce sanitized reports; real services pass in parallel. T14/T18 hooks remain explicitly unimplemented.
- Scope expansion: integrator authorized targeted PostgreSQL routing changes in `db.py` and `auth.py`, required to avoid invoking SQLite upgrades on PostgreSQL. Added a focused registry test module.

## Changed files and contracts

`Makefile`, `scripts/verify.py`, and `docs/testing.md` provide profiles, ownership, reports and reproduction. `infra/sql/migrations.json` separates rental 001–004 and auth 001/004; original SQL bytes are unchanged. `backend/realtoruch/migrations.py` validates order/checksums, applies PostgreSQL SQL under the caller's transaction (stripping only the existing transaction-wrapper lines from execution), and provides versioned, checksum-checked, idempotent SQLite callbacks. `db.py` and `auth.py` route PostgreSQL to the registry and SQLite to local hooks. Service fixtures use the registry and per-run index. `test_migration_registry.py` and service tests cover duplicate/order, checksum and PostgreSQL rollback. Recovery: back up first and restore or apply a reviewed forward fix; existing PostgreSQL schemas without metadata are not silently adopted. No public API changes.

## Acceptance evidence

| ID | Status | Test | Evidence |
| --- | --- | --- | --- |
| T01-AC01 | NOT_RUN (clean locked install) | TC01 | `offline5` passed using an isolated venv that referenced preinstalled parent site packages and linked npm dependencies; this is not a clean lock install. |
| T01-AC02 | PASS | TC02 | `svc7` and `svc8` overlapped from 20:05:08 UTC; each 7 passed, no skips, distinct PostgreSQL ports 57591/57590, ES 57593/57592, databases and index namespaces. |
| T01-AC03 | PARTIAL | TC03 | `interrupt-check` interrupted while both run-owned containers existed; both removed and separately started sentinel remained running. `skip-check` failed and removed its own resources. Existing catalog checksum comparison was not recorded. |
| T01-AC04 | PASS | TC04 | `skip-check` deliberately skipped all six then-existing service tests: runner exit 1, 0 passed/6 skipped. |
| T01-AC05 | PARTIAL | TC05 | `svc7`/`svc8` apply both registries to fresh schemas and exercise checksum rejection and PostgreSQL transaction rollback. Duplicate/order tests pass on SQLite profile. A real untracked schema with an existing row was rejected and the row retained (`svc10`); a supported tracked baseline-to-future migration with rows was not demonstrated. |
| T01-AC06 | PARTIAL | TC06 | `secret-failure`: synthetic failing parametrized request-like fixture: 129 passed, 1 failed, 6 skipped; report excludes injected synthetic token and retains test identity and failure exit. Full corpus/privacy audit not performed. |

## Verification

Working directory for all commands: assigned T01 worktree. Runtime Python 3.12.9, Node 24.6.0, Docker 29.8.0, PostgreSQL 16 Alpine, Elasticsearch 8.19.6 native arm64, macOS 15.7.7 arm64. `PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH make verify ARGS='--run-id offline5'` exited 0: 129 passed, 0 failed, 7 real-service skips; TypeScript exit 0. Concurrent same-prefix `make verify-services ARGS='--run-id svc7'` and `svc8` each exited 0: 7 passed, 0 failed/skipped. Reports are in ignored `.local/verification/T01/<run-id>/report.json`; reports refer to base revision with dirty worktree because tests preceded the result commit.

`svc1`/`svc2` used an amd64 cached ES image on arm64 and were interrupted after ES exited due to seccomp under emulation; `svc3`/`svc4` also failed before readiness. `docker pull --platform linux/arm64 docker.elastic.co/elasticsearch/elasticsearch:8.19.6` acquired the native image; `svc5`/`svc6` then passed 6/6 before the rollback test was added. `skip-check` temporarily added a skip marker (removed afterward) and exited nonzero as above. `interrupt-check` received Ctrl-C, exited nonzero and removed its containers; `docker inspect` showed the unrelated sentinel running before its deliberate removal. `secret-failure` temporarily added a failing parametrized fixture (removed afterward), exited nonzero; its report did not contain the synthetic token. `offline6` repeated the offline profile after runner reporting changes (129 passed, 7 skipped); `svc9` passed 7/7, and `svc10` passed 8/8 after adding the real untracked-schema rejection check. `make verify-web ARGS='--run-id web1'` exited nonzero and reported NOT_IMPLEMENTED. The profile's ignored working directories can contain raw pytest scratch files; only the JSON report is a sanitized artifact.

## Reproduction and review

Use `make install`, then `make verify` or `make verify-services` as documented. Ensure native Docker images and platform compatibility. Check checksum drift with `backend/tests/test_migration_registry.py`; real service checks include rollback and checksum rejection. Review immutable SQLite hook convention and baseline adoption before integrating further schema changes. No down-migration or automatic recreation of persistent catalogs is provided. T14 owns `npm run test:unit`, T18 owns `npm run test:e2e` and `verify-web`. The registry and local upgrade hooks are shared merge points for schema owners.

## Blockers and next action

The integrator should run a fresh lock install and repeat the offline profile in a clean checkout, compare the developer catalog before/after failure checks, and test a supported persistent baseline-to-integrated schema upgrade with retained rows. No cloud resources, real email, or live provider requests were used; one native Elasticsearch container image was pulled from the image registry. No push or deployment was performed.
