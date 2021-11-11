# T24 — Build the cross-platform owner photo upload and ordering flow

**User instruction:** I want an owner to select, preview, upload, reorder and remove apartment photos on web and mobile before publishing an advertisement.

| Field | Instruction |
| --- | --- |
| Tier / priority | STRETCH / P2 |
| Active effort estimate | 8 hours |
| Proposed window | Unallocated; select only after core acceptance |
| Worker slot | UNALLOCATED |
| Dependencies | [T23](T23-owned-media-storage.md), [T17](T17-inbox-client.md) |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | marketplace-ui, frontend-dependencies |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

This optional task consumes the exact owned-media contract from T23. Do not build a second incompatible API or present local previews as successfully stored photographs.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T24/<run-id>/`; commit sanitized reports only.

## Read first

- `docs/contracts/media.md (from T23)`
- `apps/mobile/src/components/MarketplaceDialog.tsx`
- `apps/mobile/src/marketplaceApi.ts`
- `apps/mobile/src/types.ts`
- `apps/mobile/package.json`
- `apps/mobile/src/components/UI.tsx`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/components/PhotoUploader.tsx (new)`
- `apps/mobile/src/components/MarketplaceDialog.tsx (photo section)`
- `apps/mobile/src/marketplaceApi.ts`
- `apps/mobile/src/types.ts`
- `apps/mobile/package.json and package-lock.json (compatible picker only)`
- `apps/mobile/tests/photoUploader.test.ts (new)`
- `apps/mobile/e2e/owner-photos.spec.ts (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Use a pinned Expo-compatible image picker with web and native support. Request permissions only when the user chooses photos; denial must leave the form usable. Accept the same types, count and size bounds as T23, while retaining server validation as authoritative.

2. Show local preview plus explicit queued/uploading/ready/failed status, progress where the transport exposes it, cancel and retry. Limit concurrent uploads to three and preserve idempotency keys across transport retries. Do not invent progress percentages when the adapter cannot measure bytes.

3. Allow reorder and removal with accessible buttons on all platforms, with optional drag behavior on web. Persist the ordered list of ready opaque asset IDs in the owner's draft. Do not submit local file URLs, pending assets or assets from another owner.

4. Retain existing draft text across upload failures and auth refresh; recover a saved draft after closing/reopening. Handle advertisement optimistic-version conflict as an explicit reload/merge choice without overwriting newer data or silently discarding images.

5. Revoke local object URLs and cancel subscriptions on unmount. Use small thumbnails in the editor and listing cards, open larger renditions only when needed, and provide an editable meaningful image description with a safe fallback.

6. Add web automation using generated fixtures and native component/adapter tests. Physical picker behavior is verified under T22 only when available; otherwise report that gap. No personal device photos or external image services may be used as test artifacts.

## Acceptance criteria

- **T24-AC01:** Photo selection works through compatible web/native adapters and permission denial is recoverable.

- **T24-AC02:** Upload concurrency, retry and cancellation follow the server contract without duplicate assets.

- **T24-AC03:** Only ready owned asset IDs are saved in the correct user-selected order.

- **T24-AC04:** Draft text/photos survive recoverable failures and version conflicts are explicit.

- **T24-AC05:** The flow is accessible at 320 px and cleans up previews/listeners/resources.

- **T24-AC06:** Browser tests and native-adapter tests cover the complete flow with sanitized synthetic images.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T24-TC01 — covers T24-AC01

**Given:** Web file input and mocked native picker/permission denial.

**When:** Select valid and invalid image fixtures.

**Then:** Valid selections queue; denial/type/size errors remain recoverable without losing draft text.

### T24-TC02 — covers T24-AC02

**Given:** Six selected images with delayed responses.

**When:** Observe active requests, cancel one and retry a timed-out one.

**Then:** At most three uploads run; retry reuses identity and cancellation cannot attach a late completion.

### T24-TC03 — covers T24-AC03

**Given:** Mixed ready/pending/failed images.

**When:** Reorder, remove and save draft.

**Then:** Only ordered ready IDs persist; publish explains any unresolved upload.

### T24-TC04 — covers T24-AC04

**Given:** Draft text and several ready images with expired access token.

**When:** Refresh/retry, close and reopen saved draft.

**Then:** Content persists and no duplicate assets are created.

### T24-TC05 — covers T24-AC04

**Given:** Another session updates the same advertisement version.

**When:** Submit older draft.

**Then:** 409 is shown with a safe recovery choice; newer data is not overwritten.

### T24-TC06 — covers T24-AC05, T24-AC06

**Given:** Narrow viewport and keyboard-only interaction.

**When:** Reorder/remove, unmount and inspect resources.

**Then:** Controls remain labelled/reachable; object URLs and listeners are released.


## Verification commands and checks

- `cd apps/mobile && npm run typecheck`
- Run focused photo uploader tests
- `make verify-web`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Reusable cross-platform photo uploader
- Owner flow integration and browser/adapter regression tests
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not add image editing, paid storage, stock-photo search or background uploads after app termination.
- Do not make T32 core acceptance depend on this stretch feature unless the integrator explicitly selects it.
