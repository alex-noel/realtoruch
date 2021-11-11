# T16 — Use message high-water marks for read state and stable inbox pagination

**User instruction:** I want you to make inbox read status reflect the messages actually displayed, including simultaneous arrivals, and make conversation/message pagination stable.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D5–D6 (2026-11-18–2026-11-19) |
| Worker slot | A |
| Dependencies | [T10](T10-identity-correctness.md) |
| Required review | API/concurrency review |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | marketplace-backend |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The read endpoint currently records server now(), which can mark a message arriving between fetch and acknowledgement as read. Conversation lists are capped at 100, while message pages already use IDs/timestamps.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T16/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/models.py`
- `backend/tests/test_marketplace.py`
- `apps/mobile/src/marketplaceApi.ts`
- `apps/mobile/src/components/MarketplaceDialog.tsx`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/marketplace.py (conversation routes)`
- `backend/realtoruch/models.py (read cursor fields)`
- `infra/sql/010_message_read_cursors.sql (new)`
- `infra/sql/migrations.json`
- `backend/tests/test_message_cursors.py (new)`
- `docs/contracts/messages.md (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Define additive read acknowledgement body {last_message_id}. Validate that the message belongs to the participant’s conversation and advance only monotonically to that displayed message’s (created_at,id) boundary.

2. Support existing empty-body clients temporarily with explicitly documented legacy semantics; new frontend T17 must use the precise cursor. Do not silently break a v1 caller while frontend/backend tasks are separate.

3. Compute unread counts using the same tuple ordering, including equal timestamps. Sending your own message must not mark unseen incoming messages as read.

4. Add bounded conversation pagination with opaque validated cursor and limit <=50, ordered by updated_at plus ID. Keep message pagination ordered by created_at plus ID; document the effect of conversations moving when new replies arrive.

5. Preserve participant isolation, one conversation per advert/renter, client-message-id deduplication, blocking and per-user send limits. Ensure retries with the same client ID and different body return a documented 409 instead of silently substituting text.

6. Batch unread counts/profile/title reads; add query-count assertions with 50 conversations. Coordinate migrations and response fields with T17 before coding UI changes.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

8. Keep route paths unchanged: PUT /v1/me/conversations/{conversation_id}/read receives the new body; GET /v1/me/conversations adds cursor/limit fields additively. Document exact cursor encoding and response keys in docs/contracts/messages.md before T17 consumes them.

## Acceptance criteria

- **T16-AC01:** Read acknowledgement cannot consume a message that was not included in the displayed cursor.

- **T16-AC02:** Read state is monotonic and equal-timestamp messages are ordered consistently.

- **T16-AC03:** Invalid/cross-conversation read cursors are rejected without modifying state.

- **T16-AC04:** Conversation/message pagination is bounded and deterministic for a static dataset.

- **T16-AC05:** Retries are idempotent; conflicting body reuse is rejected; blocking/authorization still apply.

- **T16-AC06:** The API contract and query-count evidence are ready for T17 without a mandatory frontend change in this commit.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T16-TC01 — covers T16-AC01

**Given:** Client fetches M1 and M2, then M3 arrives.

**When:** Acknowledge M2.

**Then:** M3 remains unread.

### T16-TC02 — covers T16-AC02

**Given:** M1/M2 share timestamp with ordered IDs; M2 already read.

**When:** Acknowledge older M1.

**Then:** Read cursor does not move backward; unread count stays correct.

### T16-TC03 — covers T16-AC03

**Given:** Message cursor from another conversation/account.

**When:** Submit read acknowledgement.

**Then:** 404/422 per documented contract; no read-state change.

### T16-TC04 — covers T16-AC04

**Given:** 120 conversations and 130 messages with timestamp ties.

**When:** Traverse all pages without mutation.

**Then:** No duplicate/omitted row; limits and cursor validation hold.

### T16-TC05 — covers T16-AC05

**Given:** Same client ID sent twice with same body, then different body.

**When:** Retry send.

**Then:** One message for identical retry; conflicting body returns 409.

### T16-TC06 — covers T16-AC05, T16-AC06

**Given:** Blocked conversation and 50 visible threads.

**When:** Attempt reply and list inbox with query counter.

**Then:** Reply denied; bounded constant query count rather than per-thread queries.


## Verification commands and checks

- `.venv/bin/pytest backend/tests/test_message_cursors.py backend/tests/test_marketplace.py -q`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Cursor API/migration and backward-compatibility contract
- Read-arrival race and pagination tests
- Measured query count
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- No WebSocket service, message attachments or email notifications.
- Do not expose participant login emails.
