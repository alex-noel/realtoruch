# Q33 Integrate media attachment privacy and erasure

Status: **PLANNED** · Priority: **P1** · Active effort: **6–9 hours**

Executor: **experienced** · Review: **strong: attachment transactions, visibility, erasure and least privilege**

Dependencies: **Q32** · Merge locks: **media-api, marketplace-backend, account-erasure, database-grants**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [backend/realtoruch/marketplace.py](../../../../backend/realtoruch/marketplace.py): Existing publish/edit/withdraw lifecycle has no owned-asset attachment.
- [backend/realtoruch/account_data.py](../../../../backend/realtoruch/account_data.py): Export and account-closure fencing cover current entities but no owned media.
- [backend/realtoruch/api.py](../../../../backend/realtoruch/api.py): erase_account_data is the rental-account erasure entry point that must remove owned media.

## Change

Attach only ready owned asset IDs, preserving order and existing HTTPS-link compatibility within a combined 30-image cap. Define private-draft preview and validated public derivative access, withdrawal/delisting/moderation behavior, deletion and 24-hour orphan cleanup. Extend export/erasure and role grants. Consume the complete schema and visibility contract frozen by Q32; if a new field is still needed, obtain an integrator-assigned forward migration and SQLite hook. Never edit applied migration 011.

## File scope

- `backend/realtoruch/media.py (from Q32)`
- `backend/realtoruch/media_storage.py (from Q32)`
- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/account_data.py`
- `backend/realtoruch/models.py (only agreed media relations)`
- `backend/realtoruch/worker.py (cleanup wiring)`
- `infra/sql (narrow role grants)`
- `backend/tests/test_media.py (from Q32)`
- `backend/tests/test_account_data.py`
- `docs/contracts/media.md (from Q32)`
- `backend/realtoruch/api.py (erase_account_data and media retrieval wiring only)`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q33-AC01:** Cross-owner/pending/deleted attachments fail atomically; public DTOs expose only authorized derivatives and no internal asset metadata.
- **Q33-AC02:** Deletion/closure racing upload or attach cannot resurrect media; repeated cleanup is safe and never removes an attached valid asset.
- **Q33-AC03:** Public, draft, withdrawn, saved-delisted and hidden visibility policies are explicit and tested; export/erasure and restricted-role PostgreSQL tests cover media.

## Verification

- New controlled-order media/closure tests, compatibility fixtures and actual-role service tests.
- make verify-services; relevant account/marketplace regressions; record migration and recovery implications.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

Do not rewrite canonical identity, retained saved-home semantics or existing image URLs; no cloud deployment.
