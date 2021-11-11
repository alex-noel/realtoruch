# T02 handoff · CI quality gates

## Identity and outcome

- Status: IMPLEMENTED_LOCAL. Hosted run and required-check settings remain pending G07.
- Reviewed base: `0882aeff04ac55bef504448c6bd512b8d2c216c6`.
- Implementation: `b7230d7252abf17cee9317c9ac666a45ab26b098` and `db3481762ec888108eef4f1c949f0aafd0bf1ec7`, created with `python3 scripts/commit.py`. Author and committer times match on both commits.
- Actual verification date: 2026-11-11 Europe/Warsaw, approximately 21:31–21:43 CET.
- Pull requests and integration/default-branch pushes declare separate Python/TypeScript, PostgreSQL/Elasticsearch, web export, and Android/iOS JavaScript bundle validation jobs.

## Changed files and contracts

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml` | Four independent Ubuntu jobs, locked installs, immutable action pins, read-only access, timeouts, sanitized seven-day artifacts and conditional browser verification. |
| `scripts/ci_checks.py` | Comparison-base resolution, whitespace and secret-boundary checks, report field allowlist, OSV runtime advisory delta and exception enforcement. |
| `config/ci-audit-exceptions.json` | Empty initial set of exceptions. |
| `scripts/verify.py` | Integrator-approved environment-only edit for the disabled source file, run-owned file mail and Expo dotenv isolation. Service selection and cleanup logic are unchanged. |
| `docs/testing.md` | Local equivalents, audit and exception policy, pin ownership, artifact selection and T18 hookup. |

The changes add no migrations or application/API/DTO changes. No dependency lock changes were needed. T14 can add `test:unit` through the existing T01 hook. T18 owns `test:e2e`, the real `make verify-web` profile, and staging synthetic screenshots and traces in the dedicated optional output directory.

## Acceptance evidence

| Acceptance | Status | Test case | Local evidence |
| --- | --- | --- | --- |
| T02-AC01 | PASS locally · hosted pending | TC01, TC02 | Workflow passes actionlint and structural assertions. Offline Python and TypeScript, disposable services, web export and both native exports succeeded locally. |
| T02-AC02 | PASS | TC01, TC02 | Temporary parametrized Python assertion and TypeScript type mismatch each caused `make verify` to exit 2. Both fixtures were removed. |
| T02-AC03 | PASS | TC03 | Real PostgreSQL 16.15 and Elasticsearch 8.19.6 run had 11 pass, 0 fail, 0 skips. Docker denial shim caused the required service job equivalent to fail before running tests. |
| T02-AC04 | PASS locally | TC04 | Empty credential environment, disabled sources, file mail, Python loopback-only socket sentinel and Node network sentinels. No listing portal, mail provider or cloud application request was observed. |
| T02-AC05 | PASS for configured selection · hosted upload pending | TC05 | Actual failed assertion report plus injected canary, private DB, raw capture and mail paths were filtered. Only failure status, counts and code identifiers remained. Workflow selects named reports and future synthetic browser artifacts in isolated directories. |
| T02-AC06 | PASS | TC06 | Android and iOS each emitted one Hermes bytecode bundle and metadata. Static review found no signing, deployment or publishing step. |

## Verification

Commands ran from the assigned worktree root unless marked otherwise. Platform was macOS 15.7.7 arm64, Python 3.12.9, pip 25.0, Node 24.6.0, npm 11.5.1, Docker 29.8.0 and Compose v5.5.1. The service runner used cached `postgres:16-alpine` and `docker.elastic.co/elasticsearch/elasticsearch:8.19.6` and removed both run-owned containers. Logs and intentionally contaminated fixtures remain under ignored `.local/verification/T02/evidence/`. The T01 runner writes its own isolated JSON reports under `.local/verification/T01/<run-id>/report.json`.

| Exact command or test invocation | Result |
| --- | --- |
| `python3.12 -m venv .local/verification/T02/python-env` and `.local/verification/T02/python-env/bin/python -m pip --disable-pip-version-check install --no-deps -r backend/requirements-dev.lock` | 0. Installed the 62 pinned dependencies in an owned environment. `.venv` was a local symlink to that environment. |
| `.venv/bin/python -m pip check` | 0. No broken requirements. |
| `npm ci --prefix apps/mobile --ignore-scripts --no-audit --no-fund` | 0. 527 packages installed. |
| `.venv/bin/python -m ruff check --select E9,F63,F7,F82 backend scripts` | 0. |
| `.local/verification/T02/tools/actionlint .github/workflows/ci.yml` | 0 on the final workflow, using v1.7.12. Initial lint identified a workflow-level `runner.temp` expression that was moved to a supported context. |
| `python3 -` with PyYAML BaseLoader workflow assertions | 0. Verified PR/push branches, four named independent jobs, Ubuntu/timeouts, action SHAs, nonpersisted credentials, contents-only access, exact artifact paths and retention, native export labels and absence of publish/deploy/privileged commands. |
| `BASE=$(git rev-parse origin/master)`, `.venv/bin/python scripts/ci_checks.py base "$BASE" master`, `.venv/bin/python scripts/ci_checks.py base 0000000000000000000000000000000000000000 master`, and `.venv/bin/python scripts/ci_checks.py boundary "$BASE"` | 0 for both base cases and the actual comparison diff. |
| `docker compose config --quiet` | 0. |
| `env -i HOME="$HOME" PATH="$PATH" LANG=en_US.UTF-8 make verify ARGS='--run-id t02-first-offline'` | 0. 185 pass, 0 fail, 11 service-only skips. TypeScript passed. |
| `env -i HOME="$HOME" PATH="$PATH" LANG=en_US.UTF-8 make verify-services ARGS='--run-id t02-first-services'` | 0. 11 pass, 0 fail, 0 skips. |
| **TC01** `make verify ARGS='--run-id t02-python-negative'` with temporary `test_t02_ci_canary.py` | 2 from make, 1 from pytest. 185 pass, 1 deliberate failure, 11 service-only skips. Report identifies `tests.test_t02_ci_canary::test_intentional_failure`. |
| **TC02** `npm run typecheck --prefix apps/mobile`, then `make verify ARGS='--run-id t02-ts-negative'` with a temporary `number` assigned a string | 2 for both. TypeScript diagnostic TS2322. Backend 185 pass, 0 fail, 11 service-only skips before the TypeScript failure. |
| **TC03** `PATH="/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PWD/.local/verification/T02/evidence/bin:$PATH" make verify-services ARGS='--run-id t02-no-services'` | 2 from make, 42 from the Docker shim. 0 pass, 0 fail, 0 skip because test execution did not start. Run status FAIL. |
| **TC04** `env -i HOME="$HOME" PATH="$PATH" PYTHONPATH="$PWD/backend" LANG=en_US.UTF-8 make verify ARGS='--run-id t02-sentinel-offline'` and matching `make verify-services ARGS='--run-id t02-sentinel-services'` | Both 0. Offline 185 pass, 0 fail, 11 service-only skips and TypeScript passed. Real services 11 pass, 0 fail, 0 skips. Temporary `sitecustomize.py` trapped Python socket DNS/connect attempts to non-loopback addresses, with zero hits. It was removed afterward. |
| **TC04/TC06** `make web-build`, then from `apps/mobile` `npm exec --offline -- expo export --platform android --output-dir "$RUNNER_TEMP/realtoruch-android"` and `npm exec --offline -- expo export --platform ios --output-dir "$RUNNER_TEMP/realtoruch-ios"` | All 0 under the final clean environment and Node sentinel described below. Web emitted five bundle/CSS files plus HTML and metadata. Android and iOS each emitted one `.hbc` plus metadata. |
| **TC05** `.venv/bin/python scripts/ci_checks.py report offline .local/verification/T02/evidence/polluted-report.json .local/verification/T02/evidence/realtoruch-ci/offline.json` | 0. Python assertions verified the artifact directory contained only `offline.json` and the file omitted the synthetic secret, parametrized canary, auth DB, capture, env and mail paths. |
| `.venv/bin/python scripts/ci_checks.py audit "$BASE" .local/verification/T02/tools/osv-scanner .local/verification/T02/evidence/runtime-audit.json` | 0 using OSV-Scanner v2.7.1 and the public advisory API. Two existing moderate npm advisories were reported: `glob@13.0.7` GHSA-3g3m-2fjr-6pw4 and `minimatch@10.2.6` GHSA-g3hv-75wg-m249. Zero new high/critical runtime findings in this comparison. |
| `.venv/bin/python -` calling `audit_locks`, `compare_findings` and `audit_exceptions` against actual advisory data and a temporary replacement Python lock containing `requests==2.19.0` | 0 for the assertions. The gate marked the introduced high finding under both GHSA-x84v-xcm2-53pg and its PYSEC-2018-28 alias, and allowed the same findings when already present in the base. An exact current exception allowed one ID. The same exception failed after expiry. No exception was added to the repository. |

The local export environment used `env -i HOME="$HOME" PATH="$PATH" RUNNER_TEMP="$RUNNER_TEMP" CI=true EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 EXPO_UNSTABLE_HEADLESS=1 NODE_OPTIONS="--require=$RUNNER_TEMP/network-guard.cjs"` with `RUNNER_TEMP="$PWD/.local/verification/T02/evidence"` from the root. The Node sentinel intercepted DNS, TCP and UDP route connects. Initial instrumentation found Expo LAN discovery using wildcard socket binds. After permitting wildcard binds, blocking its route probe forced an optional DHCP fallback. The final headless setting disabled that fallback. Three Expo UDP route-discovery probes to 1.1.1.1 were blocked in the guarded runs, and no other non-loopback attempt was recorded. An unguarded web export also passed and emitted three pre-existing Leaflet CSS local-resource warnings. T18 browser validation is pending.

## Reproduction and review

- Reproduce the profiles with the commands in [local verification](../testing.md) and the run IDs above. For TC01 inject a parametrized failing assertion and use its parameter as the report canary. For TC02 add a temporary `.ts` under `apps/mobile/src` with `export const value: number = 'intentional';`. For TC03 put a `docker` shim that exits 42 first on PATH. Remove both temporary source files and the shim from the active PATH after testing.
- Review audit exceptions and action updates as repository maintainer. Hosted execution still needs to verify GitHub runner/cache behavior and actual uploads. Advisory availability can change independently of the code. No live security finding is inferred for dependencies absent from the public advisory database.
- Reverting the implementation commits removes the workflow and CI helpers and restores the prior verification environment. Disposable test data requires no migration or data rollback.

## Blockers and next action

G07 is pending. Hosted run URL and result are unset. The maintainer can authorize a future integration/default-branch push or PR run and configure the four required status checks after reviewing the hosted result. T14 unit tests, T18 browser execution and browser artifact uploads were not run because their entry points had not landed in this base. No cloud resources, real mail, listing-portal requests, pushes, deployments or publications were used.

## Integrator acceptance

Parent reviewed workflow permissions, pins, triggers, artifact allowlists and audit comparison behavior, then independently ran actionlint, fatal Python lint and Compose validation. Combined runner environment passed242 offline tests (50 explicit service-only skips), TypeScript, and82 real-service/race tests with zero skips on2026-11-11. Reports: `.local/verification/T01/integrated-t02-offline/report.json` and `integrated-t02-services/report.json`. Hosted G07 remains unrun; no push was performed.
