# T36 — Add a separate opt-in email category for unread private messages

**User instruction:** I want users who explicitly opt in to receive a limited email reminder for unread private messages, without exposing message content or changing their rental-alert preferences.

| Field | Instruction |
| --- | --- |
| Tier / priority | STRETCH / P2 |
| Active effort estimate | 8 hours |
| Proposed window | Unallocated; select only after core acceptance |
| Worker slot | UNALLOCATED |
| Dependencies | [T13](T13-delivery-fencing.md), [T16](T16-message-read-cursors.md), [T17](T17-inbox-client.md), [T21](T21-native-links-and-lifecycle.md) |
| Required review | strong: private messaging and notification suppression |
| External gates | G02 (real email acceptance only) |
| Shared merge/contract locks | marketplace-backend, mail-dispatch, marketplace-ui, rental-models, rental-migrations |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The user chose email for rental alerts; that is not consent to enable another email category automatically. This optional feature defaults off and reuses the fenced delivery infrastructure and precise message read cursors.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T36/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/marketplace.py`
- `backend/realtoruch/email_alerts.py`
- `backend/realtoruch/models.py`
- `backend/realtoruch/auth_jobs.py`
- `apps/mobile/src/components/MarketplaceDialog.tsx`
- `apps/mobile/src/linking.ts (from T21)`
- `docs/contracts/messages.md (from T16)`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/marketplace.py (message notification events only)`
- `backend/realtoruch/email_alerts.py (category/template/suppression only)`
- `backend/realtoruch/models.py (preference/event fields only)`
- `infra/sql/014_message_email.sql (new)`
- `apps/mobile/src/components/MarketplaceDialog.tsx (opt-in setting only)`
- `backend/tests/test_message_email.py (new)`
- `docs/contracts/message-email.md (new)`
- `backend/realtoruch/migrations.py (additive SQLite upgrade for this task only)`
- `infra/sql/migrations.json (this task's reserved entry only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Reserve rental migration 014_message_email.sql. Add a separate, default-off unread-message email preference requiring a verified account/confirmed delivery address. Existing rental-alert and favorite-drop preferences must remain unchanged.

2. Create at most one eligible reminder per recipient/conversation per rolling ten-minute window. Aggregate multiple incoming unread messages into that event, use a stable logical idempotency key and preserve per-attempt fencing from T13. Sending one's own message must not trigger a reminder to oneself.

3. Before dispatch, recheck read watermark, participant permission, block status, preference, verification and account-closure state. If all relevant messages are now read, conversation is blocked or account is erased, cancel the reminder. Document the narrow unavoidable race after an SMTP send has already started.

4. Use a minimal template with sender display name safely escaped and a link to the conversation. Do not include private message bodies, email addresses, phone numbers or sensitive attachment content in email. Support text/HTML and per-category unsubscribe without disabling unrelated rental alerts.

5. Route the conversation link through T21's safe parser; logged-out users authenticate and resume the correct authorized conversation. Test another user's conversation ID and deleted/blocked conversation states without disclosing membership.

6. Verify all delivery behavior using local .eml files and fake clocks. Real email sending is a separate G02-authorized acceptance step, not implied by implementing this feature. Update account export/erasure and migration tests for new preference/event fields.

7. Implement fresh-schema and existing-database upgrades for both PostgreSQL and SQLite through T01's migration contract. Register only this task's reserved version(s), preserve applied migrations/checksums and prove existing rows retain their values. Coordinate the shared registry/upgrade file with the integrator.

## Acceptance criteria

- **T36-AC01:** Unread-message email is independently opted in and off for existing/new users by default.

- **T36-AC02:** Aggregation and idempotency enforce the ten-minute conversation/recipient window.

- **T36-AC03:** Read, block, unsubscribe and erasure state suppress eligible reminders before dispatch.

- **T36-AC04:** Email content is minimal, escaped and contains no private message body/contact information.

- **T36-AC05:** Conversation links preserve authorization and resume safely after login.

- **T36-AC06:** Local tests, exports/erasure and migrations pass; any real-delivery gap is explicitly stated.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T36-TC01 — covers T36-AC01

**Given:** Existing rental email subscriber and newly registered user.

**When:** Receive an incoming message without enabling message email.

**Then:** No reminder is queued/sent; rental settings are unchanged.

### T36-TC02 — covers T36-AC02

**Given:** Three unread incoming messages in one conversation within ten minutes.

**When:** Queue and drain twice with fake clock.

**Then:** At most one logical reminder exists; a later eligible window behaves as documented.

### T36-TC03 — covers T36-AC03

**Given:** Queued reminder followed by precise read acknowledgement, block or unsubscribe.

**When:** Dispatch after each transition.

**Then:** Reminder is cancelled; unrelated rental email preferences remain intact.

### T36-TC04 — covers T36-AC03, T36-AC06

**Given:** Account erasure racing a delivery claim.

**When:** Execute controlled claim/cancel/ack order.

**Then:** Closure and fencing prevent state resurrection; any already-started transport caveat is reported.

### T36-TC05 — covers T36-AC04

**Given:** Message body/contact canaries and HTML-like sender name.

**When:** Render text/HTML .eml.

**Then:** Content canaries are absent, sender is escaped and safe conversation link is present.

### T36-TC06 — covers T36-AC05, T36-AC06

**Given:** Logged-out recipient, unauthorized user and deleted conversation.

**When:** Open email conversation link.

**Then:** Recipient resumes after login; others receive safe denial and no membership disclosure.


## Verification commands and checks

- Run focused message-email, account and delivery tests
- `make verify-services`
- `make verify-web`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Separate opt-in reminder category and migration
- Suppression/privacy/deep-link tests and delivery caveat documentation
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not enable message email for users automatically or email private message bodies.
- Do not send real mail without G02 or add push/SMS/messenger channels.
