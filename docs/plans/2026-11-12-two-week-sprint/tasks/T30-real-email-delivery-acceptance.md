# T30 — Verify real email delivery and suppression with an explicitly authorized test inbox

**User instruction:** I want the selected email notification channel proven with a real sender and an authorized test inbox, including confirmation, unsubscribe and favorite price-drop delivery.

| Field | Instruction |
| --- | --- |
| Tier / priority | CONDITIONAL / P0 |
| Active effort estimate | 6 hours |
| Proposed window | D8–D10 (2026-11-23–2026-11-25) |
| Worker slot | UNALLOCATED |
| Dependencies | [T13](T13-delivery-fencing.md), [T14](T14-session-resilience.md), [T18](T18-browser-regression-suite.md) |
| Required review | strong: external sending and account links |
| External gates | G02 |
| Shared merge/contract locks | mail-config |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

SMTP behavior has local tests, but no configured provider or real-inbox acceptance exists. Do all configuration and local validation before the gated send. G02 must include both sender credentials/configuration and explicit permission to send the named test messages to the designated inbox.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T30/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/email_alerts.py`
- `backend/realtoruch/auth_jobs.py`
- `backend/realtoruch/settings.py`
- `docs/deployment.md`
- `backend/tests/test_email_alerts.py`
- `backend/tests/test_accounts.py`
- `docs/testing.md (from T01)`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `docs/verification/email-delivery.md (new)`
- `docs/operations/email.md (new)`
- `backend/realtoruch/email_alerts.py (provider-compatible fixes only)`
- `backend/realtoruch/auth_jobs.py (provider-compatible fixes only)`
- `.env.example (placeholder settings only)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Require G02: selected SMTP/provider connection settings, verified sender identity/domain, a named test recipient controlled/authorized by the user and explicit approval of test sends. Prepare all local templates and preview messages first; never send to imported portal contacts or unrelated users.

2. Consult current primary documentation for the selected provider's TLS/auth/rate limits and sender-domain requirements. Record relevant DNS verification results (SPF/DKIM/DMARC where supported) without modifying DNS or choosing/purchasing a provider. Credentials stay in ignored local secrets.

3. Use at most six intentionally triggered messages: account verification, password reset, alert opt-in confirmation, one new-match alert, one favorite-price-drop alert and one delivery retry case if needed. Record logical event IDs and redacted Message-IDs; do not include passwords or live tokens in the report.

4. Verify reception in the designated inbox with available authorized mailbox access or user confirmation. SMTP 250 alone is transport acceptance, not inbox delivery. Test link destinations and one-use/expiry behavior using synthetic accounts and the configured app URLs.

5. Confirm same-price repost silence, unsubscribe suppression, preference changes and account erasure cancellation before the next dispatch. Distinguish logical deduplication from the unavoidable possibility of duplicate physical delivery after ambiguous SMTP acceptance.

6. If the chosen provider exposes bounces/complaints, document its supported behavior and add a signed authenticated handler only as a separately reviewed follow-up; do not invent a generic unauthenticated webhook during this bounded task. Missing credentials/domain/inbox confirmation keep the relevant ACs blocked, while local preparation can be completed.

## Acceptance criteria

- **T30-AC01:** Sender/recipient configuration and sending authorization are explicit and private.

- **T30-AC02:** The named message categories reach the designated inbox and have valid safe links.

- **T30-AC03:** New-match and favorite-drop emails correspond to exactly the intended logical events.

- **T30-AC04:** Same-price repost, unsubscribe and erased-account cases suppress subsequent sends.

- **T30-AC05:** Retries/ambiguous acceptance are documented honestly with no false exactly-once promise.

- **T30-AC06:** A redacted report distinguishes local preparation, SMTP acceptance and actual inbox reception.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T30-TC01 — covers T30-AC01

**Given:** Missing sender, recipient or send authorization.

**When:** Run local preflight/preview only.

**Then:** No network email is sent and G02 remains blocked with exact missing inputs.

### T30-TC02 — covers T30-AC02, T30-AC03

**Given:** Configured sender and approved test inbox.

**When:** Trigger the specified verification/confirmation/new/drop messages.

**Then:** Each expected message is observed in the inbox and links resolve to the correct synthetic account/listing action.

### T30-TC03 — covers T30-AC02

**Given:** Used/expired verification or reset link.

**When:** Open it a second time.

**Then:** A safe expired/used state appears without exposing secrets or changing another account.

### T30-TC04 — covers T30-AC03, T30-AC04

**Given:** Seen home reposted at the same price and an unsubscribed saved search.

**When:** Run collection/dispatch.

**Then:** No additional logical event or email is sent.

### T30-TC05 — covers T30-AC04

**Given:** Queued alert followed by account erasure before claim.

**When:** Run delivery worker.

**Then:** Queued delivery is cancelled and no message reaches the inbox.

### T30-TC06 — covers T30-AC05, T30-AC06

**Given:** Controlled retry/uncertain transport outcome.

**When:** Inspect logical IDs, transport status and mailbox evidence.

**Then:** Report separates event uniqueness from physical-delivery uncertainty and does not conceal duplicates.


## Verification commands and checks

- Run local account/email/journey regressions before external sending
- Execute only the bounded authorized SMTP acceptance sequence
- Review redacted inbox/transport evidence and settings diff

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Real-delivery acceptance matrix or exact external-blocker report
- Provider-specific operational notes with primary documentation links
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not create a provider account, purchase service, modify DNS or send to anyone beyond the authorized test inbox.
- Do not claim successful delivery from a unit test, .eml file or SMTP acknowledgement alone.
