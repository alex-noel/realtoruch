# Delegating the app quality plan

Dispatch one task packet at a time to an implementer, with this guide, a reviewed base revision and an isolated checkout. The goal is small reviewable changes to the existing app. Workers do not need the entire old sprint or all 40 packets in their context.

## Model roles and dispatch

An **economy** implementer receives a concrete packet and implements its bounded change. The integrator supplies design or API decisions where specified, reviews the diff and rejects scope expansion that is unrelated to the task. An **experienced** implementer owns Q32, Q33 and Q40 because they combine upload security, lifecycle races or final evidence review. A packet marked **strong review** needs an independent reviewer familiar with the affected boundary; it does not automatically require expensive implementation.

Start with three implementers and one reviewer if capacity permits. Q02, Q09 and Q27 are a useful initial batch with separate files. Keep at most one unreviewed change per sensitive state machine. Do not select model names or reasoning settings based on assumed current pricing; choose the cheaper capable model available at dispatch time and keep the stronger reviewer on the marked boundaries.

Use this dispatch prompt, filling every bracket:

> Implement [Qxx and task path] in [assigned checkout] on branch [codex/qxx-name], starting from reviewed base [commit]. Read this plan's DELEGATION.md and the full packet. Dependencies [IDs and reviewed commits] are integrated. Your merge slot covers [files or sections]. Follow the packet's acceptance criteria without expanding scope or weakening checks. Preserve unrelated changes. Use the existing verification harness and return HANDOFF_TEMPLATE.md with actual commands and results. Do not execute another task, push, deploy or send external messages. If committing, use python3 scripts/commit.py --task Qxx for every commit with the assigned task ID. Report a specific blocker and continue independent work when possible.

A worker may start only when dependency contracts/code are reviewed, the assigned base contains them, its required local fixtures are available and overlapping shared-file ownership is resolved. Preparing tests against an explicitly agreed fixture contract is allowed, but does not count as integrated acceptance.

On ambiguity, inspect the current producer and tests first. Give the integrator one concrete question with the smallest supported alternatives. After two failed approaches to the same blocker or scope expanding beyond the packet's estimate, report the reproduction and attempted fixes instead of repeatedly rewriting the feature. A time estimate never overrides an acceptance criterion.

## Shared files and integration

Use one worktree/checkout and `codex/` branch per active task. Use run-owned databases, synthetic accounts and unique verification IDs; never edit the old live soak checkout or reuse the user's catalogs. Separate worktrees prevent filesystem collisions but not incompatible changes.

The manifest's `merge_locks` are minimum coordination hints. The **actual file scope always wins**: serialize overlapping edits or agree exact sections and integrate sequentially. Locks do not require a runtime lock service.

| Shared area | Tasks | Rule |
| --- | --- | --- |
| `theme.ts`, `UI.tsx`, `web.css` | Q01, Q02, Q04, Q24 | Q01/Q02 interfaces reviewed before consumers; no parallel whole-file formatting. |
| `App.tsx` | Q04–Q10, Q14, Q18–Q21 | One integration owner; focused component/hooks extraction only where the packet needs it. Q18 private state before dependent collection work. |
| `Dialogs.tsx` | Q06, Q07, Q10, Q12–Q14, Q17, Q24 | Assign named dialog sections. Integrate shared DetailDialog changes in order: Q10, then Q12/Q13, then Q14; history change must preserve their layout. |
| `api.ts` and session tests | Q03, Q21, Q26 | Publish safe error/cursor/export interfaces before consumers; preserve refresh, cancellation and session fences. |
| `NotificationInbox.tsx` | Q21–Q23 | Integrate cursor and preference changes sequentially; do not replace each other's state. |
| Map adapters | Q15, Q16 | Recovery first, then marker grouping. Keep polygon/coordinate behavior. |
| `MarketplaceDialog.tsx` | Q27, Q29, Q37 | Q27 extraction first if it is in flight. One close-handler owner integrates owner and message dirty-state guards together; account reset always clears private content. |
| Extracted owner components | Q28–Q31, Q34, Q35 | Q28 validation → Q29 dirty guard → Q30 conflicts → Q31 preview; Q34/Q35 integrate on the reviewed result. |
| Message state and rendering | Q36, Q37 | Presentation and draft changes can develop separately but final review checks displayed-message acknowledgements and retry IDs together. |
| `marketplace.py`, models, erasure, grants | Q32, Q33, Q35 | Media contract and lifecycle review before integration; appeal projection is separate and owner-only. |
| Package files and lockfiles | Q26, Q32, Q34, Q39 | One integrator owns dependency updates. Use existing compatible packages before adding one; preserve locked installs. |

Avoid resolving conflicts by choosing entire ours/theirs files. Review both behaviors and rerun the checks covering their interaction. Do not broaden a small change into framework migration, routing replacement or whole-file lint cleanup.

## Product invariants

- Rent limits retain the strict exclusive ceiling; area minimum is inclusive. Declared direct advertiser and known zero commission remain independent. Unknown fees are never converted to zero or advertised as a known total.
- Canonical identity, saved/seen state, quiet same-price reposts, genuine favorite price-drop alerts, silent saved-search baselines and retained delisted favorites remain intact. Hidden homes retain existing visibility restrictions.
- Imported contacts lead to the original portal; first-party private messages keep authorization, retry deduplication, blocking and displayed-incoming-message read cursors.
- Session rotation, private account generation guards, export reauthentication and erasure fences remain authoritative. Account changes clear old private UI and drafts even when ordinary navigation preserves them.
- Keep existing modal focus behavior, keyboard polygon entry, lazy web map/marketplace chunks and 320/390/768/1440 px plus 200% text support.
- Keep UI copy in the existing English style with Polish places, PLN and documented comma/dot numeric handling. Do not introduce a translation framework or invent provider coverage, verified owner identity or exact location precision.

## Producer contracts and migrations

Q03 publishes safe client error categories. Q21 publishes additive notification cursor semantics and compatibility. Q26 consumes the existing session-bound export contract. Q32 publishes upload, state, identity, retry and visibility contracts; Q33 completes attachment, retrieval and erasure; Q34 must not guess those DTOs.

Q32 owns the previously reserved rental migration **011_media_assets.sql**, registry entry and corresponding additive SQLite hook. Check the current registry at dispatch time. Q32/Q33 must agree all schema fields before finalizing 011; after it is applied, use a new integrator-assigned forward migration rather than changing its checksum. Existing reservations 012 (location), 013 (phone keys) and 014 (message email) remain reserved for the deferred old-plan scopes. No task independently takes the next number. Q21 should use existing notification fields and indexes unless measured evidence justifies an additive index migration.

Schema work requires fresh and existing-data upgrades on SQLite and PostgreSQL, repeated-start safety, real role tests and a recovery note. Preserve all applied SQL and local-hook checksums. Do not claim service acceptance from skipped cases. Media remains disabled until attachment, cleanup, visibility and frontend behavior are integrated and reviewed.

## Verification without duplicated effort

Read [the current testing guide](../../testing.md) and the packet. The repository already has unit, isolated browser and real-service harnesses. Do not add tests merely to mirror styles or a behavior-preserving move. Add meaningful regression tests for actual failure cases and use screenshots for visual review.

From the assigned checkout root, frontend commands can be run as:

```sh
cd apps/mobile
npm run typecheck
npm run test:unit -- tests/session.test.ts
```

Replace the test path with the existing/new focused test named by the packet. For a browser spec, activate the checkout's Python 3.12 environment first, then use the existing owned-service runner:

```sh
source .venv/bin/activate
cd apps/mobile
VERIFY_RUN_ID=q09-review-unique npm run test:e2e -- boundaries.spec.ts
```

Every run ID must be unique. The runner builds the web export and uses disposable loopback services, local fixtures and file mail. Pass a focused spec/project/grep as supported; never run tests against a user's live database. New filenames in packets are proposed outputs, not claims that those tests already exist.

Backend-focused tests use the checkout environment and repository fixtures. When the affected invariant depends on transactions, migrations or grants, run the real-service profile:

```sh
make verify-services ARGS='--run-id q33-review-unique'
```

Q40 runs the combined final profiles once the integrated code is stable. Re-run only affected checks after later fixes, plus whatever combined checks their interaction justifies. The existing entry-JavaScript budget is 650,000 uncompressed bytes and the documented warm-action p95 budget is 200 ms; preserve the existing benchmark method when comparing results.

Store raw test data in ignored `.local/verification/Qxx/<run-id>/` or the existing harness-owned directories. Handoffs should contain sanitized aggregate results and synthetic screenshots only. Do not commit tokens, mail, databases, storage state, raw traces, passwords or private exports. Record current wall-clock dates for evidence.

## Commit and external action rules

The user authorized execution of all 40 packets on 17 November 2026. The integrator assigns dependency-ready work; local implementation, review and checks are authorized. Do not push, deploy, provision cloud services, start live collection, send email/messages, or publish apps as a side effect. No packet needs real external delivery to complete its local implementation. Missing external inputs are recorded in Q40's gate ledger rather than invented or bypassed.

If commits are part of the assignment, stage only intended changes and use:

```sh
python3 scripts/commit.py --task Q09 -m "Q09 Describe the concrete change"
```

Use the helper for amendments. Do not push without an explicit instruction.

## Handoff and acceptance states

All tasks begin `PLANNED`. The integrator updates [execution.json](execution.json); workers return the handoff, rather than racing to rewrite the shared tracker or acceptance criteria.

- `IN_PROGRESS`: assigned and active.
- `IMPLEMENTED_LOCAL`: code exists, but one or more required local checks/reviews are outstanding.
- `VERIFIED_LOCAL`: every packet criterion passes with current local evidence and required review.
- `BLOCKED`: a named prerequisite prevents acceptance; record independent completed work and the exact unblock condition.
- `CHANGES_REQUESTED`: reviewer found a defect or unsupported claim.

An external check may remain `NOT_RUN_EXTERNAL` alongside a locally verified task where the packet explicitly excludes it. Never translate missing tools, skipped tests or an unobserved device behavior into pass. Q40's local candidate classification and external gate ledger remain separate.
