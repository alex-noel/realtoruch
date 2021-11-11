# T33 — Track location precision and add an opt-in bounded geocoding adapter

**User instruction:** I want each map location to explain how precise it is, and I want missing coordinates enrichable without inventing exact addresses or generating false new-listing alerts.

| Field | Instruction |
| --- | --- |
| Tier / priority | STRETCH / P2 |
| Active effort estimate | 8 hours |
| Proposed window | Unallocated; select only after core acceptance |
| Worker slot | UNALLOCATED |
| Dependencies | [T05](T05-parser-contracts.md), [T12](T12-public-search-contract.md) |
| Required review | strong: data provenance and quiet backfill |
| External gates | G06 (live geocoding only) |
| Shared merge/contract locks | rental-models, ingest-backend, search-contract, map-components, rental-migrations |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Source coordinates can be exact, approximate or missing. The optional enrichment feature must preserve provenance and remain disabled for live lookups until a permitted provider is configured.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T33/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/normalization.py`
- `backend/realtoruch/portals.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/query.py`
- `backend/realtoruch/alerts.py`
- `apps/mobile/src/components/PropertyMap.tsx`
- `apps/mobile/src/components/PropertyMap.web.tsx`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/geocoding.py (new)`
- `backend/realtoruch/models.py (location provenance fields only)`
- `backend/realtoruch/schemas.py (additive location DTO fields)`
- `backend/realtoruch/ingest.py (enrichment hook only)`
- `infra/sql/012_location_provenance.sql (new)`
- `backend/tests/test_geocoding.py (new)`
- `apps/mobile/src/components/PropertyMap* (precision label only)`
- `docs/contracts/location.md (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`
- `infra/sql/migrations.json (this task's reserved entry only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Reserve rental migration 012_location_provenance.sql. Define precision as building, street, district, city or unknown, with provider/source, observation time and optional uncertainty radius. Existing unlabelled coordinates default to unknown, not building precision.

2. Do not overwrite source-provided valid coordinates automatically. Normalize addresses for lookup without exposing phone/user identifiers, and preserve the original source text privately where already permitted. Distinguish ambiguous multiple candidates from a confident result.

3. Implement a disabled-by-default geocoder interface, fake fixture adapter and provider configuration contract with allowlisted endpoints, request budgets, timeouts, cache keys and negative caching. Live requests require G06; do not use a public/community geocoder for bulk enrichment by default.

4. Keep canonical IDs stable. Apply accepted enrichment through the same transactional revision/outbox path as other public listing changes. Update map and index atomically/eventually according to the existing contract, with no hidden raw-provider data in public DTOs.

5. Treat enrichment of existing homes as a quiet correction: baseline matching saved searches for those homes in the same correction flow so gaining coordinates does not emit a 'new home' email. Subsequent genuine listing/price changes still use normal matching. New unseen homes with known coordinates follow normal alerts.

6. Define polygon filtering as testing the stored representative point, while displaying uncertainty/precision clearly. Do not claim the entire apartment/building lies inside a polygon from a district centroid. Validate coordinate ranges/order, failed lookups and repeat processing idempotency.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

## Acceptance criteria

- **T33-AC01:** Location precision/provenance are additive, truthful and backward compatible.

- **T33-AC02:** Explicit valid source coordinates are preserved and ambiguous lookups remain unresolved.

- **T33-AC03:** Offline adapters enforce budgets/cache/timeouts and live enrichment stays disabled without G06.

- **T33-AC04:** Enrichment preserves canonical identity and uses revisioned indexing without private data leakage.

- **T33-AC05:** Existing-home enrichment is quiet while future genuine matching/price alerts still work.

- **T33-AC06:** Map/filter copy and tests explain representative-point uncertainty accurately.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T33-TC01 — covers T33-AC01, T33-AC02

**Given:** Legacy unknown coordinates, valid explicit point and ambiguous address.

**When:** Run enrichment fixtures.

**Then:** Legacy precision stays unknown; explicit point is preserved; ambiguity does not become an exact location.

### T33-TC02 — covers T33-AC03

**Given:** Repeated positive/negative cache key and failing provider fixture.

**When:** Run bounded enrichment.

**Then:** Cache/timeout budgets hold and no external request occurs without the live gate.

### T33-TC03 — covers T33-AC04, T33-AC05

**Given:** Existing seen/favorited home outside saved search because coordinates are absent.

**When:** Add a qualifying location then drain outboxes.

**Then:** Canonical ID/favorite remain; index updates; no false new-listing alert is sent.

### T33-TC04 — covers T33-AC05

**Given:** Same corrected home later relisted at a genuinely lower price.

**When:** Ingest and match.

**Then:** Normal eligible favorite-price-drop behavior still occurs once.

### T33-TC05 — covers T33-AC04, T33-AC06

**Given:** District centroid near polygon edge and reversed/out-of-range coordinates.

**When:** Filter/render and validate.

**Then:** Representative-point rule and approximate label are explicit; invalid coordinates are rejected.

### T33-TC06 — covers T33-AC01, T33-AC03, T33-AC06

**Given:** Migration from old rows and missing G06.

**When:** Run fresh/upgrade tests and inspect report.

**Then:** Schema works offline; live provider acceptance remains unverified.


## Verification commands and checks

- Run focused location/alert/ingestion tests
- `make verify-services`
- `make verify-web`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Location provenance fields, adapter and quiet-enrichment tests
- Documented polygon precision contract
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not buy a geocoding service, bulk-query public endpoints or infer a precise apartment address.
- Do not alter identity matching thresholds as part of location enrichment.
