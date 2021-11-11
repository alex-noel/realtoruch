# T06 handoff — OLX source preflight

## Identity and outcome

- Task: T06
- Status: IMPLEMENTED_LOCAL
- Base revision: `c4d606215162006f469a90c106053c1b41f00fb7` (reviewed T05 dependency)
- Result commit: `HEAD` is this handoff commit; resolve with `git rev-parse HEAD`. Created with `python3 scripts/commit.py`.
- Actual work/test date and timezone: 2026-11-11 21:30 CET, Europe/Warsaw (UTC+01:00)
- Run ID: `T06-20261111-213057`
- Outcome: Added an offline-first OLX access and mapping preflight; the default profile reports missing feed authorization/configuration and leaves collection disabled.
- Scope changes approved by integrator: none.

## Changed files and contracts

- `scripts/source_preflight.py`: offline config checks, secret-variable presence reporting, query-free exact-host HTTPS checks, opt-in path-aware robots/discovery/feed/detail sample with configured plus robots crawl/request pacing and a three-request ceiling, response-size cap, no redirects/retries, sanitized malformed-config diagnostics, and the five required machine states. It reports configured `enabled` separately from preflight's always-false `collection_enabled` and never writes configuration.
- `config/sources.json`: records Kraków as the disabled OLX feed profile's city. `enabled` remains false; feed URL remains empty.
- `config/provider-feed.example.json`: disabled illustrative provider mapping, pagination/observation/removal/reuse/authentication guidance; explicitly makes no claim about OLX provider capabilities.
- `backend/tests/test_source_preflight.py`: offline, invalid/missing secret, RawListing mapping, 403/challenge/robots denial, detail path/cross-origin refusal, fake-clock pacing, wrong-city feed, redirect/private destination, malformed config/payload and mock successful sample coverage.
- `docs/source-connectors.md`: documents command behavior, limits, T29 handoff, provider feed caveats and manual HTML import distinction.
- No migration/API/DTO changes. No database compatibility or recovery work is applicable.

## Acceptance evidence

| AC ID | Result | Test case | Evidence |
| --- | --- | --- | --- |
| T06-AC01 | PASS | T06-TC01 | Offline default is `not_configured`, 0 requests; ready disabled profile remains offline. |
| T06-AC02 | PASS | T06-TC02 | Private/credential URL rejected; missing token named without value; canary absent from serialized report. |
| T06-AC03 | PASS | T06-TC03 | Mock feed and synthetic OLX detail fixture produce validated `RawListing` records. |
| T06-AC04 | PASS | T06-TC04 | Mock 403, HTML robots/login challenge, path denial, disallowed detail and cross-origin detail all stop at or before the 2nd request. |
| T06-AC05 | PASS | T06-TC05 | Configuration only yields `ready_offline`; mocked sample must fetch/parse and match Kraków. Wrong-city feed is rejected before detail fetch. |
| T06-AC06 | PASS | T06-TC06 | Generated checklist identifies `scripts/import_html.py` as manual-only and automated transport as unresolved. |

All required T06 test cases were run. Network behavior was exercised only through `httpx.MockTransport` fixtures. No live portal/provider request, account, email, cloud resource, or push occurred. Thus the implementation path is covered, but actual provider access and live OLX verification remain for T29.

## Verification

Run ID `T06-20261111-213057`; checkout `/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t06`; Python 3.12.9; pytest and Ruff from the repository root `.venv`.

1. `PYTHONPATH=backend ../../../.venv/bin/pytest backend/tests/test_source_preflight.py backend/tests/test_olx.py -q` — exit 0; 25 passed, 0 failed, 0 skipped. Includes the existing OLX parser fixture tests and new offline/mock HTTP behavioral tests.
2. `PYTHONPATH=backend ../../../.venv/bin/python scripts/source_preflight.py` — exit 0; machine report `not_configured`, 0 requests, collection disabled, with missing approved feed URL and `OLX_FEED_TOKEN`; no errors.
3. `python3 -m py_compile scripts/source_preflight.py backend/tests/test_source_preflight.py` — exit 0.
4. `git diff --check` — exit 0.
5. `../../../.venv/bin/ruff check --config backend/pyproject.toml scripts/source_preflight.py backend/tests/test_source_preflight.py` — exit 0; all checks passed.

An initial pytest invocation used a nonexistent worktree-local `.venv`; it did not execute tests. The subsequent root-venv invocation found an import-path issue in the new test module, fixed by adding the worktree root to `sys.path`. A later run exposed mismatched test expectations for request counting and token completeness; those were corrected. After integrator review, the final run added challenge/robots fail-closed behavior, detail-policy checks, cross-origin refusal, robots pacing, Kraków validation, sanitized config diagnostics, and corresponding mock tests. No raw private artifacts were created; all test data are committed synthetic fixtures.

## Reproduction and review

- Run offline: `PYTHONPATH=backend ../../../.venv/bin/python scripts/source_preflight.py`.
- Run tests: `PYTHONPATH=backend ../../../.venv/bin/pytest backend/tests/test_source_preflight.py backend/tests/test_olx.py -q`.
- Negative boundaries include private/credential-bearing URLs, missing token, HTTP 403 and HTML challenge, path-specific robots denial, disallowed detail, cross-origin detail with no third request, redirect/private DNS, wrong-city feed, malformed config/feed and configuration-only state.
- Parent/integrator review requested for security and capability boundaries, especially the network-mode state/report interpretation.
- Safe rollback: revert this task's commit; no persistent state, schema, credentials or external service was changed.
- Downstream: T29 may use the operator checklist after an authorized transport/profile is supplied. OLX remains disabled pending independent live evidence.

## Blockers and next action

- Gate/input: actual authorized feed or permitted automated public transport and its precise HTTPS hosts, city scope, mapping, rate/pagination/removal terms are not supplied.
- Independent work complete: implementation, synthetic fixture tests, and operator checklist.
- Next action: after the source/capability is supplied, T29 performs the separately authorized live verification and review. No push/deploy/publication was performed.

## Integrator review

Parent inspected the network boundaries and independently ran the targeted suite on 2026-11-11: 29 passed, 0 failed, 0 skipped. Added regressions for null/numeric/object host-list configuration and an optional null feed-token setting; these now return bounded diagnostics or proceed without credentials instead of raising a TypeError. Scoped Ruff checks pass. All HTTP evidence remains fake-transport evidence; automated OLX collection stays disabled and live access is unresolved.
