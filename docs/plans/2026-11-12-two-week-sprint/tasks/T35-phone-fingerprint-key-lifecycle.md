# T35 — Define and test phone fingerprint key rotation and retention

**User instruction:** I want private phone fingerprints to support controlled key rotation and retention without exposing numbers, duplicating agent counts or silently breaking matching.

| Field | Instruction |
| --- | --- |
| Tier / priority | STRETCH / P2 |
| Active effort estimate | 8 hours |
| Proposed window | Unallocated; select only after core acceptance |
| Worker slot | UNALLOCATED |
| Dependencies | [T15](T15-account-data-lifecycle.md), [T26](T26-operational-metrics-and-runbooks.md) |
| Required review | strong: cryptographic identity and erasure |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | rental-models, ingest-backend, phone-identity, rental-migrations |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Phone-derived identity signals help detect repeated advertiser behavior. A stored one-way HMAC cannot be transformed to a new key without seeing the original number again; the migration plan must acknowledge that limitation.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T35/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/normalization.py`
- `backend/realtoruch/dedupe.py`
- `backend/realtoruch/ingest.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/pipeline.py`
- `backend/realtoruch/settings.py`
- `docs/architecture.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/phone_identity.py (new)`
- `backend/realtoruch/normalization.py (fingerprint delegation only)`
- `backend/realtoruch/models.py (versioned fingerprint records only)`
- `backend/realtoruch/ingest.py (bounded identity changes only)`
- `backend/realtoruch/pipeline.py (backward-compatible envelope fields only)`
- `infra/sql/013_phone_fingerprint_lifecycle.sql (new)`
- `backend/tests/test_phone_identity.py (new)`
- `docs/operations/phone-fingerprints.md (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`
- `infra/sql/migrations.json (this task's reserved entry only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Reserve rental migration 013_phone_fingerprint_lifecycle.sql. Model a nonsecret key ID, HMAC fingerprint, last observed time and lifecycle state separately from public listing DTOs. Keep raw phone numbers transient in normalization only; inspect Bigtable/Pub/Sub/log serialization so raw contacts are not newly retained.

2. Support an active key and a bounded previous-key overlap configuration. On fresh phone observation compute both fingerprints during the overlap and create private linkage evidence; do not pretend old hashes can be rehashed into new-key hashes without original input.

3. Use explicit key-ID lookup, fail safely on unknown/missing keys and document the operational sequence: configure overlap, observe/rebuild only from authorized fresh source data, measure coverage, retire old key and expire stale evidence. Never rotate actual production secrets in this task.

4. Use a proposed 90-day stale-fingerprint retention setting with explicit project-owner review required before production adoption. Expiry must distinguish deleting private identity evidence from deleting canonical price history. Account erasure follows T15's rules even if fingerprint retention is longer.

5. Count distinct canonical properties for phone-based agency indicators, avoiding double counting across source crossposts or two key versions linked to the same number. Missing/expired identity evidence must mean insufficient evidence, not proof an agency advertiser is a direct owner. Preserve existing declared seller type separately.

6. Version event envelopes additively and test old queued payloads/replays with fake Bigtable/Pub/Sub clients. No key, raw phone or fingerprint may enter public search, metrics labels, user exports or log messages. Document residual linkage limitations during/after rotation.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

## Acceptance criteria

- **T35-AC01:** Versioned private fingerprints support old data and explicit key IDs without raw phone persistence.

- **T35-AC02:** Dual-key observation links identities correctly without impossible hash conversion.

- **T35-AC03:** Missing/retired keys and stale data fail safely with truthful insufficient-evidence states.

- **T35-AC04:** Retention/account-erasure behavior is configurable, tested and separated from price history.

- **T35-AC05:** Crossposts and overlapping key versions do not inflate agency property counts.

- **T35-AC06:** Public APIs, exports, logs and fake cloud envelopes satisfy the documented privacy contract.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T35-TC01 — covers T35-AC01, T35-AC02

**Given:** Same fresh phone observed with old and new active keys during overlap.

**When:** Normalize and ingest duplicate source ads.

**Then:** Private linkage agrees and canonical property counts do not double.

### T35-TC02 — covers T35-AC02, T35-AC03

**Given:** Only an old stored HMAC with no raw phone available.

**When:** Attempt key migration.

**Then:** No fabricated new-key hash is produced; coverage gap is explicit.

### T35-TC03 — covers T35-AC03

**Given:** Unknown/retired key ID and expired evidence.

**When:** Classify advertiser and reprocess event.

**Then:** Classification remains insufficient where required; no unhandled crash or false direct-owner guarantee occurs.

### T35-TC04 — covers T35-AC04

**Given:** Evidence older than configured retention and an account erasure request.

**When:** Run cleanup twice.

**Then:** Private evidence is removed according to policy; retained aggregate/history rules remain correct.

### T35-TC05 — covers T35-AC05

**Given:** Multiple crossposts and two linked key epochs for one canonical home.

**When:** Compute agency-count indicators.

**Then:** One property contributes one count, with separate declared-vs-inferred evidence.

### T35-TC06 — covers T35-AC01, T35-AC06

**Given:** Legacy/new fake cloud events plus canary phone/key/hash values.

**When:** Replay and inspect public/search/export/log outputs.

**Then:** Backward compatibility holds and private canaries never appear in forbidden outputs.


## Verification commands and checks

- Run focused phone/normalization/ingestion/cloud-envelope tests
- `make verify-services`
- Review public DTO/export/log privacy tests

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Versioned fingerprint lifecycle implementation and migration
- Rotation/retention runbook with coverage limitations
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not rotate production keys, recover raw numbers from hashes or introduce a public phone directory.
- Do not claim legal compliance from this engineering retention proposal.
