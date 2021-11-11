# Local verification

Requirements: Python 3.12, Node 24 (24.3 or newer), npm, and for the service profile Docker with cached `postgres:16-alpine` and `docker.elastic.co/elasticsearch/elasticsearch:8.19.6` images, working loopback port publishing and enough RAM for two 512 MiB Elasticsearch heaps when running concurrently. Image acquisition is a separate operator action; verification never pulls images. A compatible Elasticsearch kernel/seccomp implementation is required. The commands do not contact real portals, mail or cloud services.

From a clean checkout, install the committed Python and npm locks once with `make install`. Then run `make verify` for Python and TypeScript, or `make verify-services` for real disposable PostgreSQL and Elasticsearch. Both generate a unique run ID unless supplied as `ARGS='--run-id worker-a-1'`. IDs are exclusive: reusing one fails instead of overwriting evidence. Reports are in ignored `.local/verification/T01/<run-id>/report.json`; they contain only test counts and failed test identifiers, not captured test output or XML, which might contain secrets. Record reproducible safe inputs separately. Commands use the worktree's Python and backend; do not point editable installs at another checkout.

The service profile creates uniquely named containers and uses Docker-assigned loopback ports, separate PostgreSQL instances/schemas and ES index namespaces. It waits up to 120 seconds and deletes only containers it successfully created. Service skips are failures. Ctrl-C or SIGTERM cleans up those resources; interruption by SIGKILL or a host crash requires manually inspecting and removing only names printed in the run report. Never use a system-wide prune. Services use synthetic credentials and disposable data.

`make verify` also invokes `npm run test:unit` when T14 adds that shared script; its absence is explicitly reported as NOT_IMPLEMENTED. `make verify-web` builds a production web export and runs the local Chromium suite with one worker. It fails on any failed or skipped browser case.

## CI

The four job names are **Python and TypeScript**, **PostgreSQL and Elasticsearch**, **Web export**, and **Android and iOS JavaScript bundle validation**. CI runs on pull requests and pushes to `master`, `codex/core-sprint-2026-11`, and `codex/krakow-rental-journey`. The repository maintainer owns required-check configuration and action updates. Review upstream release notes and the commit behind each release before replacing an action SHA. The initial pins correspond to [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-python v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0), [setup-node v7.1.0](https://github.com/actions/setup-node/releases/tag/v7.1.0), and [upload-artifact v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1).

From the repository root, install the CI lock inputs with Python 3.12 and Node 24.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip --disable-pip-version-check install --no-deps -r backend/requirements-dev.lock
.venv/bin/python -m pip check
npm ci --prefix apps/mobile --ignore-scripts --no-audit --no-fund
```

Use the full comparison commit SHA for the target branch or previous push tip. A new branch push uses its fork point with the default branch. The boundary check covers whitespace, credential patterns, private file types, and the disabled source config.

```sh
.venv/bin/python scripts/ci_checks.py boundary "$BASE"
.venv/bin/python -m ruff check --select E9,F63,F7,F82 backend scripts
make verify
docker compose config --quiet
make verify-services
CI=true EXPO_NO_DOTENV=1 EXPO_UNSTABLE_HEADLESS=1 make web-build
```

Run the native bundle equivalents from `apps/mobile`, using an owned temporary output directory. The output consists of Metro JavaScript bundles or Hermes bytecode and export metadata.

```sh
export CI=true EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 EXPO_UNSTABLE_HEADLESS=1
output="$(mktemp -d)"
npm exec --offline -- expo export --platform android --output-dir "$output/android"
npm exec --offline -- expo export --platform ios --output-dir "$output/ios"
```

CI installs packages from public registries and pulls the public service test images before invoking T01's isolated profile. Verification uses the disabled source config, file mail in the run-owned directory, and synthetic fixtures. PR jobs use read-only repository permissions and checkout does not persist Git credentials. Failure artifacts are restricted to selected fields from test reports and the browser paths below. The audit report is available on successful and failed audits. Artifact retention is seven days.

The browser hook starts when T18 adds `test:e2e` and implements `make verify-web`. It expects Chromium via the locked Playwright CLI. T18 can pass the optional `VERIFY_BROWSER_ARTIFACTS_DIR` through the runner and stage synthetic failure screenshots at `screenshots/*.png` and synthetic traces at `traces/*.zip`. These files must come from isolated fixtures with synthetic credentials and data. Keep mail, databases, browser storage state, unfiltered network captures and raw test output outside those directories.

### Runtime dependency audit

Use the workflow-pinned [OSV-Scanner v2.7.1 release](https://github.com/google/osv-scanner/releases/tag/v2.7.1) for the local audit. Download the asset for your platform, verify its SHA-256 against the upstream release, and pass its executable path to the helper.

```sh
.venv/bin/python scripts/ci_checks.py audit "$BASE" "$OSV_SCANNER" "$AUDIT_REPORT"
```

The scanner queries public advisories for the committed Python runtime and npm locks at both comparison revisions. The gate excludes npm development-only entries and matches findings by ecosystem, package, resolved version and advisory ID. New findings with CVSS ≥7 or an advisory severity of high or critical fail the check. Existing findings and findings with lower or unknown severity remain visible in the report. A scan error fails the job. The audit is limited to advisories available from its database at scan time.

The repository maintainer reviews changes to `config/ci-audit-exceptions.json`. Each accepted exception names the exact `ecosystem`, `package`, `version`, and `advisory`, an accountable `owner`, an `expires` date in UTC (YYYY-MM-DD, inclusive), and a `reason`. An expired or invalid exception fails the audit. Remove exceptions after remediation. There are no approved exceptions at the introduction of this policy.

Hosted execution passed after the authorized integration push; see [T32](verification/T32-handoff.md) for the recorded run. Required-check/branch-protection settings remain a separate maintainer decision.

## Migrations

`PYTHONPATH=backend .venv/bin/python -m realtoruch.migrations validate` validates the same ordered registry used by service fixtures. For a fresh PostgreSQL database, set `MIGRATION_DATABASE_URL` and run `PYTHONPATH=backend .venv/bin/python -m realtoruch.migrations apply --database rentals` (or `auth`). Never pass credentials in the command line. Apply uses one transaction, checks every recorded checksum before running later files, and rejects duplicate/out-of-order versions. Rental and auth histories are separate. Existing untracked databases are not silently adopted: application stops with an untracked-schema error before recording a baseline. Stop writers and take and verify a backup; inventory the existing schema and migration history against the exact immutable registry files, and have an operator review a database-specific adoption or forward-migration plan before applying it. No automatic adoption procedure is supplied; do not insert checksum rows merely to bypass the error. Restore the verified backup if a reviewed change fails. Preserve 001–004 byte-for-byte. New SQL files must be registered in their reserved database/version order; SQLite upgrades use idempotent, immutable versioned Python hooks in `upgrade_local`, not PostgreSQL SQL. Hooks must tolerate a crash between execution and recording. Backup before an upgrade; restore a verified backup or use a reviewed forward fix if it fails. Arbitrary partially merged worker schemas are disposable and not supported upgrade bases.

The base container copies the registry and SQL to `/app/infra/sql` and sets `REALTORUCH_SQL_DIR` explicitly, so migration commands also work outside `/app`. For other installations, point this variable at a directory containing the matching registry and SQL files.

## Isolated browser suite

Install the locked Chromium binary with `npm exec --prefix apps/mobile -- playwright install chromium` (on Linux CI, use `playwright install --with-deps chromium`). Then run `make verify-web ARGS='--run-id unique-lowercase-id'`, or activate the project Python 3.12 virtualenv and run `npm run test:e2e --prefix apps/mobile`. Each run owns SQLite rental/auth catalogs, random credentials, local file mail, API/auth/alert processes, static export, and an opaque fixture token under ignored `.local/verification/T18/<run-id>/`. It uses dynamically selected loopback ports and a deterministic local map tile. Browser routing rejects non-loopback requests. The fixture is a child process, guarded by run token, local run path, database path and non-production environment; there is no fixture mutation API or production endpoint. It never runs collectors, SMTP, push, or cloud clients. Run IDs are exclusive and the runner terminates its processes. A host crash may require terminating only the run's remaining owned processes; never prune unrelated resources.

The suite runs desktop Chromium and responsive 390×844 Chromium, not installed iOS or Android. It uses synthetic accounts, mail and messages. The T01 report contains only aggregate counts and command statuses. Run-owned logs, database files, mail, browser error contexts and raw traces may contain tokens and must not be uploaded. On failure, synthetic screenshots and screened traces may be staged to `VERIFY_BROWSER_ARTIFACTS_DIR`; raw traces are deleted after processing. `trace-handling.json` counts retained and omitted traces. The journey test starts a trace only for the intentional fault after token-bearing links are consumed; ordinary journey failures provide screenshots and error context, without a trace. The controlled fault case can be run with `T18_FAULT_DUPLICATE=1` and `--project=desktop -g 'draw and save'` appended to `npm run test:e2e --prefix apps/mobile --`; it must exit nonzero. The runner screens traces with `apps/mobile/e2e/sanitize_fault.py`: it keeps only trace events and synthetic screenshots, rejects traces containing known token/header values or JWT-shaped strings, and omits network records, response/resource bodies, source files and stacks. It never stages a rejected trace. This screening is scoped to these synthetic fixtures, not arbitrary traces. Raw mail, databases, logs and browser error contexts stay private in the ignored run directory.
