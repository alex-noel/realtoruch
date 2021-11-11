# T05 portal parser handoff

- Status is `IMPLEMENTED_LOCAL` pending integrator review.
- Base revision is `2d9a22d`. The result is the commit containing this report on `codex/core-t05`, created with `python3 scripts/commit.py -m "Detect portal parser drift and protect listing observations"`.
- Actual test date is 11 November 2026 in Europe/Warsaw, around 21:09 CET. The Git commit uses the separate five-calendar-year date convention.
- Run ID is `20261111T2110-CET`.
- Confirmed empty results, access interstitials, parser drift and verified removals have distinct behavior in the normal collection path.
- The integrator approved the narrow `connectors.py` change for bounded report diagnostics and non-rental skip reasons.

## Changed files and contracts

- `backend/realtoruch/portals.py` validates the search envelope, result entries and pagination before accepting an empty result. It emits bounded parser codes and checks access-page markers before reading embedded state. Detail parsing validates required amounts, exact rooms, location and explicit removal identity.
- `backend/realtoruch/connectors.py` attaches `errors[].code` to portal parser failures and counts `skip_reasons.not_rental` alongside the existing skip total. It checks embedded removal IDs against the prior stored record. An unrecognized or failed response preserves the prior observation.
- `backend/tests/test_portals.py` and `backend/tests/test_olx.py` exercise the normalized contract, discovery and detail adapter outcomes, SQLite observation state, and diagnostics.
- `backend/tests/fixtures/portals/` contains the four existing search and detail pairs, eight synthetic empty/drift pages, two shared interstitials and the [provenance matrix](../../backend/tests/fixtures/portals/README.md). Two baseline phone canaries were replaced with a non-dialable all-zero value. Other test variants are generated from reduced baseline detail pages in memory.
- [Source connector documentation](../source-connectors.md) records recognized shapes, failure codes and unsupported cases.
- No migrations, configuration changes, public DTO changes or new dependencies. Existing source identities, collection budgets, totals and explicit HTTP 404/410 behavior are preserved. The new diagnostic keys are additive and OLX scheduled transport stays disabled.

## Acceptance evidence

| AC | Result | Cases | Run and evidence |
| --- | --- | --- | --- |
| T05-AC01 | PASS | TC01–TC05 | All four providers have the nine scenario classes in the fixture matrix. OLX empty markup is explicitly unsupported and the collector rejects the fixture. |
| T05-AC02 | PASS | TC01, TC03 | Exact external IDs, URLs, rent, fees, deposit, area, rooms, advertiser and location match the reduced baselines. A rent update preserves other normalized fields. |
| T05-AC03 | PASS | TC02, TC05 | Supported empty pages succeed with zero. Drift and both interstitials fail discovery with distinct bounded codes. Challenge markup enclosing removal state fails detail parsing. |
| T05-AC04 | PASS | TC03, TC04 | Sale is a counted non-rental skip. Foreign currency, missing rooms and a required rent range emit no record. Optional ambiguous fees stay unknown. |
| T05-AC05 | PASS | TC05 | In each provider case, absent prior record produces no inactive observation. After seeding a prior valid record, 403, timeout, malformed markup, wrong ID, missing URL evidence and challenge preserve status and timestamp. Only confirmed removal adds the inactive observation. |
| T05-AC06 | PASS | TC05, TC06 | The fixtures pass the reduced-size, credential and phone-canary scan. Captured collector logs omit body, URL, exception-message and contact canaries. |

| Test case | Result | Coverage |
| --- | --- | --- |
| T05-TC01 | PASS | Four exact active-detail and changed-rent cases. |
| T05-TC02 | PASS | Four provider discovery cases with next links, empty behavior, structural drift, challenge and consent responses. |
| T05-TC03 | PASS | Twelve rounding cases and four required-range/unknown-fee cases, including nonbreaking and narrow nonbreaking spaces. |
| T05-TC04 | PASS | Twelve collector detail cases for sale, foreign currency and absent rooms, with bounded reasons and zero emitted records. |
| T05-TC05 | PASS | Four SQLite collector lifecycle cases, plus the existing multi-source HTTP 410 regression. The lifecycle cases check removal without a prior row, seed one active observation, advance the fake collector clock past each persisted retry window, verify unchanged state after each injected failure, then apply the explicit removal. |
| T05-TC06 | PASS | Scan of all 18 reduced HTML fixtures and the four lifecycle log captures. The public API regression also checks that the stored contact canary and private evidence fields stay out of listing responses. |

## Verification

Commands ran from `/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t05`. Runtime was macOS 15.7.7 arm64, Python 3.12.9, SQLite 3.50.2, pytest 8.4.2, Ruff 0.17.4, SQLAlchemy 2.1.8, Pydantic 2.14.3, Beautiful Soup 4.15.0 and HTTPX 0.28.1. Tests used the T05 worktree package, the existing local dependency environment, temporary SQLite and mocked transport.

```sh
set -o pipefail
env -u TEST_POSTGRES_URL -u TEST_ELASTICSEARCH_URL PYTHONPATH="$PWD/backend" /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_portals.py backend/tests/test_olx.py backend/tests/test_connectors.py -q -o addopts= | tee .local/verification/T05/20261111T2110-CET/targeted.log
env -u TEST_POSTGRES_URL -u TEST_ELASTICSEARCH_URL PYTHONPATH="$PWD/backend" /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests -q -o addopts= -rs | tee .local/verification/T05/20261111T2110-CET/regression.log
/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/ruff check backend/realtoruch/portals.py backend/realtoruch/connectors.py backend/tests/test_portals.py backend/tests/test_olx.py
/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/ruff format --check backend/realtoruch/portals.py backend/realtoruch/connectors.py backend/tests/test_portals.py backend/tests/test_olx.py
git diff --check
```

- Targeted pytest exited 0 with 88 passed, 0 failed and 0 skipped. The broader backend run exited 0 with 169 passed, 0 failed and 5 skipped. The skipped tests require opt-in PostgreSQL and Elasticsearch. Those services were outside this task's offline parser acceptance. Both runs emitted one existing Starlette TestClient deprecation warning.
- Ruff and the whitespace check exited 0. Raw test summaries are in the ignored run directory above.
- Earlier targeted iterations surfaced a legacy OLX test that lacked URL identity and a lifecycle fixture that immediately retried during real collector backoff. The final assertions cover unsupported URL evidence and use the fake clock described above.

## Review and recovery

- The discovery regression reproduces drift by replacing the required search envelope field or listing URL shape and returning HTTP 200 through the mocked collector transport.
- The fixture matrix does not establish live empty, removal or challenge page shapes. OLX empty discovery fails closed and the positive OLX removal case is synthetic. Other unrecognized interstitials can appear as ordinary parser errors while still preserving listing state.
- The change has no schema or persistent configuration dependency. A code rollback restores prior parsing and reporting behavior without rewriting existing observations.
- No live provider requests, cloud resources, real email, push or deployment were used. No external blocker remains for the offline task.
