# T23 — Add private, validated image uploads for owner advertisements

**User instruction:** I want an owner to upload their own apartment photos safely instead of relying only on externally hosted image URLs.

| Field | Instruction |
| --- | --- |
| Tier / priority | STRETCH / P2 |
| Active effort estimate | 10 hours |
| Proposed window | Unallocated; select only after core acceptance |
| Worker slot | UNALLOCATED |
| Dependencies | [T15](T15-account-data-lifecycle.md), [T08](T08-versioned-search-index.md) |
| Required review | strong: uploads, ownership and storage |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | rental-models, marketplace-backend, api-routes, rental-migrations |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

Owner publication already exists. This optional expansion must keep media ownership, validation and deletion consistent with accounts and canonical listings. It is not part of the committed two-week core capacity.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T23/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/api.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/security.py`
- `backend/realtoruch/settings.py`
- `infra/sql/migrations.json (from T01)`
- `docs/architecture.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/media.py (new)`
- `backend/realtoruch/media_storage.py (new)`
- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/api.py (owned-media routes and scoped body limit)`
- `backend/realtoruch/models.py (MediaAsset only)`
- `infra/sql/011_media_assets.sql (new)`
- `backend/tests/test_media.py (new)`
- `docs/contracts/media.md (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`
- `infra/sql/migrations.json (this task's reserved entry only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Define authenticated, verified-owner endpoints under /v1/me/media for upload/status/delete and use opaque asset IDs. Reserve rental migration 011_media_assets.sql. States are pending, ready, rejected and deleted; only ready assets owned by the publishing user may attach to an advertisement, maximum 30 images.

2. Accept JPEG, PNG and WebP only, maximum 10 MiB per upload and 20 megapixels decoded. Enforce a streaming byte cap even without Content-Length, reject mismatches, decode with a maintained pinned image library, normalize orientation, strip EXIF/location metadata and re-encode. Reject SVG, animations, archives and decompression bombs.

3. Generate immutable object keys on the server and serve only validated derivatives. Make a bounded thumbnail and a display rendition (maximum 2,048 px long edge); retain no original metadata-bearing object after successful processing. Do not trust filenames or browser Content-Type. Keep upload authorization separate from public derivative reads.

4. Implement a local filesystem adapter rooted in a run-specific directory and a fakeable GCS adapter/config contract. No cloud bucket is created. If the existing global 1 MiB HTTP guard conflicts, exempt only the explicit authenticated upload route and enforce its own stricter streaming limit.

5. Support idempotent upload requests, cancellation/deletion and cleanup of unattached assets after 24 hours. Check account-closure tombstones and ownership inside attachment/deletion transactions. Define what happens to already-public images on owner withdrawal and account erasure; remove owned files/derivatives when erasure completes.

6. Use local generated test images only. Never fetch arbitrary remote URLs on behalf of an upload, proxy credentials, overwrite another user's asset or publish pending files. Document response DTOs, error codes, size limits and rollback/cleanup behavior before T24 starts.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

## Acceptance criteria

- **T23-AC01:** Only authenticated verified owners can upload/manage their own assets.

- **T23-AC02:** All byte, type, dimension and metadata rules are enforced before public availability.

- **T23-AC03:** Publishing accepts only ready owned assets and enforces the 30-image limit.

- **T23-AC04:** Local storage and fake cloud contract tests work without network/cloud credentials.

- **T23-AC05:** Retries, orphan cleanup and account erasure are idempotent and cannot resurrect deleted media.

- **T23-AC06:** Public responses/paths expose no filesystem locations, original metadata or private processing information.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T23-TC01 — covers T23-AC01, T23-AC03

**Given:** Two users and pending/ready assets.

**When:** Cross-attach/delete another user's asset or publish 31 images.

**Then:** Requests fail with safe 403/422; ownership and listing version stay unchanged.

### T23-TC02 — covers T23-AC02

**Given:** Valid generated JPEG/PNG/WebP with orientation and GPS EXIF.

**When:** Upload and inspect public derivative.

**Then:** Image is correctly oriented, bounded and re-encoded with sensitive metadata removed.

### T23-TC03 — covers T23-AC02

**Given:** Spoofed MIME, animated image, oversized chunked body and decompression bomb.

**When:** Upload each fixture.

**Then:** Each is rejected within bounded memory/bytes and never becomes public.

### T23-TC04 — covers T23-AC03, T23-AC04

**Given:** Local adapter plus fake object storage.

**When:** Complete upload/status/attach lifecycle.

**Then:** Same DTO/state contract passes without external requests.

### T23-TC05 — covers T23-AC05

**Given:** Duplicate idempotency key, interrupted upload and 25-hour orphan.

**When:** Retry and run cleanup twice.

**Then:** No duplicate asset or orphan bytes remain; attached assets are preserved.

### T23-TC06 — covers T23-AC05, T23-AC06

**Given:** Account erasure racing upload completion.

**When:** Release both transactions in controlled order.

**Then:** Closure fence prevents attachment/resurrection and public paths reveal no private internals.


## Verification commands and checks

- Run focused media and account lifecycle tests
- `make verify-services`
- `make verify`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Media API/storage implementation and migration
- Documented media contract and security-focused tests
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not provision a bucket/CDN, copy portal photos or add arbitrary-URL image proxying.
- Do not expose original uploads or process unbounded files synchronously.

## Primary technical references

- [OWASP file upload validation and storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

Use these with the installed project versions; recheck current version-specific details before implementation.
