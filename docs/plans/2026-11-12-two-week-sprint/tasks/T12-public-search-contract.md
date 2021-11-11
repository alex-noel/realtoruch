# T12 — Harden public API/search contracts and fallback behavior

**User instruction:** I want you to make anonymous rental reads predictable, bounded and safe when Elasticsearch fails or returns malformed/stale data.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D6–D7 (2026-11-19–2026-11-20) |
| Worker slot | A |
| Dependencies | [T08](T08-versioned-search-index.md), [T11](T11-history-storage.md) |
| Required review | API/data review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | query-model, public-api |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The REST endpoint forwards successful search-service JSON directly and falls back to SQL on HTTP errors. The services have different deep-page bounds. Preserve the free anonymous API and private Elasticsearch topology.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T12/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/api.py`
- `backend/realtoruch/search.py`
- `backend/realtoruch/query.py`
- `backend/realtoruch/schemas.py`
- `backend/realtoruch/security.py`
- `apps/mobile/src/types.ts`
- `backend/tests/test_api.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/api.py (public reads)`
- `backend/realtoruch/search.py`
- `backend/realtoruch/schemas.py`
- `backend/realtoruch/query.py`
- `backend/tests/test_public_contract.py (new)`
- `docs/public-api.md (new)`
- `apps/mobile/src/types.ts (additive metadata only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Define explicit public response models/allowlists for listings, search pages, history and source health. Exclude phone hashes, raw contacts, drafts, email addresses, private audit reasons and delivery/auth fields even if an upstream service returns them.

2. Validate successful upstream search responses before forwarding; malformed JSON/schema or service timeouts must produce a bounded SQL fallback with degraded=true, not a 500 or untrusted payload.

3. Apply consistent page_size 1–100 and offset/result-window limits across REST and search. Keep stable sort by selected field plus canonical ID and document keyword-relevance differences between engines.

4. For REST discovery, revalidate candidate IDs against current SQL visibility/status before returning them; fill a page using a bounded candidate scan or fall back to SQL. Never return a known-hidden/delisted home merely because the index is behind.

5. Keep the directly exposed search route explicitly eventually consistent with the measured T08 convergence target; add as_of/index-lag metadata if available without false precision. Do not claim immediate SQL guarantees for that route unless you implement them.

6. Publish pagination/filter/error examples, 429 Retry-After behavior, base-rent-versus-fees semantics and observed-data limitations. Endpoint availability is not a grant of third-party content redistribution rights.

## Acceptance criteria

- **T12-AC01:** Anonymous public reads return only the approved response fields.

- **T12-AC02:** Malformed/unavailable search uses SQL fallback and marks degradation consistently.

- **T12-AC03:** Invalid geometry, page sizes and deep pages return a documented 422 consistently.

- **T12-AC04:** REST discovery excludes a SQL-hidden/inactive home while its ES document is stale.

- **T12-AC05:** Pagination is deterministic on a static dataset and filtering agrees between SQL/ES for structured filters.

- **T12-AC06:** Documentation distinguishes guaranteed REST visibility, eventual direct-search visibility, public quotas and data-reuse prerequisites.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T12-TC01 — covers T12-AC01

**Given:** Search response containing private canary fields.

**When:** Fetch through REST/public serialization.

**Then:** Canaries are rejected/removed; no private field reaches the response.

### T12-TC02 — covers T12-AC02

**Given:** Timeout, HTTP 503, invalid JSON and wrong response shape.

**When:** Request listings.

**Then:** Bounded SQL fallback succeeds with degraded=true; no unhandled exception.

### T12-TC03 — covers T12-AC03

**Given:** Invalid polygon, page_size 101 and offset beyond supported window.

**When:** Call both read routes.

**Then:** Consistent documented 422 with no expensive query.

### T12-TC04 — covers T12-AC04

**Given:** Home indexed active but hidden/delisted in SQL before reindex.

**When:** Read REST discovery.

**Then:** Home is excluded immediately; page/count metadata is honest.

### T12-TC05 — covers T12-AC05

**Given:** Static dataset with equal prices and a polygon boundary home.

**When:** Fetch adjacent pages on both engines.

**Then:** Stable ID tie-break and no overlap/missing item on the static fixture; boundary semantics agree.

### T12-TC06 — covers T12-AC06

**Given:** SQL unavailable as well as search unavailable.

**When:** Request listings.

**Then:** 503/error contract is accurate; no fabricated empty successful catalog.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_public_contract.py backend/tests/test_api.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Public response models and fallback/visibility tests
- Free API guide with copyable curl examples and versioned field contracts
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No mandatory API accounts/paywall or arbitrary ES query exposure.
- No promise of zero-lag direct Elasticsearch reads without implementing canonical validation.
