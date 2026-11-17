# App quality and completion plan

Forty bounded tasks to improve the current rental app, finish incomplete user journeys and prepare the work for lower-cost implementation models. The priority is clear, recoverable renter and owner flows with consistent UI. Preserve the existing React Native and FastAPI stack and the green, cream and square-corner visual identity.

Prepared **17 November 2026, Europe/Warsaw**, against `3bbe7b413c61e86095d1b5a6cce14c3c15bb9d83`. The original audit used source, existing tests, previous handoffs and checked-in previews. **Execution was subsequently authorized and is tracked in [execution.json](execution.json).** Packet headings retain the original planning state; implementation status, reviewed commits and current evidence are in the tracker and task handoffs. Earlier test passes are not acceptance of later changes.

Read [the delegation guide](DELEGATION.md), dispatch one linked task packet, then collect [a handoff](HANDOFF_TEMPLATE.md). [manifest.json](manifest.json) contains scopes, dependencies, checks and effort ranges; [execution.json](execution.json) records actual assignments, commits and acceptance.

## Priorities and effort

- **P1:** correctness, recovery and completion gaps to address before the associated journey is accepted.
- **P2:** presentation and interaction improvements after their dependencies. P2 does not mean optional in this selected 40-task plan.
- **37 tasks** are suitable for an economy implementer with the stated review. **Q32, Q33 and Q40** should use an experienced implementer/integrator. Security or concurrency review is required on additional packets even when implementation is delegated cheaply.
- Estimated active work: **115–173 hours**, plus approximately **25% integration/rework reserve**. These are planning ranges, not model runtime, a fixed sprint commitment or a delivery date. External waits and installed-device/provider acceptance are excluded.

Start with **Q02, Q09 and Q27** in separate lanes, with a reviewer available. They unlock field usability, fix map pagination and reduce owner-editor file conflicts. Next: Q03, Q06, Q11 and Q18. Q01 and Q32 can start independently when their reviewer and shared-file slots are available. Do not run every independent-looking task at once: dependencies and shared-file locks both matter.

## The 40 tasks

| Task | Outcome | Priority | Hours | Depends on | Executor |
| --- | --- | --- | ---: | --- | --- |
| [Q01](tasks/Q01-visual-foundations.md) | Unify visual tokens and control states | P2 | 2–3 | — | economy |
| [Q02](tasks/Q02-field-semantics.md) | Complete shared field semantics and inline errors | P1 | 2–3 | — | economy |
| [Q03](tasks/Q03-actionable-api-errors.md) | Preserve safe actionable API errors | P1 | 3–4 | — | economy |
| [Q04](tasks/Q04-scoped-feedback.md) | Make success and failure feedback visible and accessible | P2 | 2–4 | Q01 | economy |
| [Q05](tasks/Q05-compact-discovery-shell.md) | Reduce discovery chrome and clarify mobile navigation | P2 | 3–4 | Q01 | economy |
| [Q06](tasks/Q06-filter-number-validation.md) | Fix decimal and range input in filters | P1 | 2–3 | Q02 | economy |
| [Q07](tasks/Q07-active-filter-summary.md) | Expose active filters and predictable reset actions | P1 | 2–3 | Q06 | economy |
| [Q08](tasks/Q08-explicit-sort.md) | Replace sort cycling with an explicit choice | P2 | 1–2 | — | economy |
| [Q09](tasks/Q09-map-pagination.md) | Make pagination work in list split and map views | P1 | 2–3 | — | economy |
| [Q10](tasks/Q10-detail-hydration.md) | Show detail loading and recover locally from failures | P1 | 2–4 | Q03, Q04 | economy |
| [Q11](tasks/Q11-broken-photo-fallback.md) | Handle broken listing photos across all screens | P1 | 1–2 | — | economy |
| [Q12](tasks/Q12-usable-photo-gallery.md) | Make listing galleries usable with many photos | P2 | 2–3 | Q11 | economy |
| [Q13](tasks/Q13-listing-hierarchy.md) | Clarify listing costs and bring primary actions forward | P2 | 3–4 | Q01, Q10 | economy |
| [Q14](tasks/Q14-comparison-editing.md) | Improve mobile comparison and selection management | P2 | 3–4 | Q11, Q13 | economy |
| [Q15](tasks/Q15-map-failure-recovery.md) | Recover from map loading and tile failures | P1 | 3–4 | — | economy |
| [Q16](tasks/Q16-overlapping-map-homes.md) | Expose every home when map markers overlap | P2 | 4–6 | Q09, Q15 | economy |
| [Q17](tasks/Q17-readable-rent-history.md) | Improve rent history and insights on small screens | P2 | 2–3 | — | economy |
| [Q18](tasks/Q18-private-section-loading.md) | Load saved homes searches and inbox independently | P1 | 3–5 | — | economy |
| [Q19](tasks/Q19-saved-search-completion.md) | Resume saving after sign in and clarify saved searches | P1 | 3–4 | Q07, Q18 | economy |
| [Q20](tasks/Q20-saved-home-feedback.md) | Make saved homes and favorite mutations predictable | P1 | 2–3 | Q04, Q18, Q13 | economy |
| [Q21](tasks/Q21-notification-pagination.md) | Make notification pagination and read actions reliable | P1 | 4–6 | Q03, Q18 | economy |
| [Q22](tasks/Q22-email-preference-recovery.md) | Show truthful email preference loading and recovery | P1 | 2–3 | Q18 | economy |
| [Q23](tasks/Q23-push-capability.md) | Check push capability before requesting permission | P1 | 3–4 | Q22 | economy |
| [Q24](tasks/Q24-auth-form-usability.md) | Finish sign in and password form interactions | P1 | 2–3 | Q02, Q03 | economy |
| [Q25](tasks/Q25-account-panel-recovery.md) | Make account and device management recoverable | P1 | 2–4 | Q03, Q24 | economy |
| [Q26](tasks/Q26-account-export.md) | Expose the existing account data export | P1 | 4–6 | Q03, Q25 | economy |
| [Q27](tasks/Q27-rental-desk-boundaries.md) | Extract rental desk components for safe delegation | P1 | 2–3 | — | economy |
| [Q28](tasks/Q28-owner-form-validation.md) | Organize owner fields and match server validation | P1 | 4–5 | Q02, Q03, Q06, Q27 | economy |
| [Q29](tasks/Q29-unsaved-owner-edits.md) | Protect unsaved advert and profile changes | P1 | 3–4 | Q27, Q28 | economy |
| [Q30](tasks/Q30-owner-conflict-recovery.md) | Recover safely from concurrent advert edits | P1 | 3–5 | Q03, Q29 | economy |
| [Q31](tasks/Q31-owner-publish-preview.md) | Add a clear review step before publishing changes | P2 | 3–4 | Q13, Q28, Q29, Q30 | economy |
| [Q32](tasks/Q32-owned-media-producer.md) | Implement bounded owned image upload and storage | P1 | 6–9 | — | experienced |
| [Q33](tasks/Q33-owned-media-lifecycle.md) | Integrate media attachment privacy and erasure | P1 | 6–9 | Q32 | experienced |
| [Q34](tasks/Q34-owner-photo-uploader.md) | Finish photo picking upload ordering and retry | P1 | 5–7 | Q11, Q29, Q30, Q31, Q33 | economy |
| [Q35](tasks/Q35-owner-dashboard-status.md) | Clarify advert status and appeal progress | P1 | 3–5 | Q03, Q25, Q27, Q31 | economy |
| [Q36](tasks/Q36-conversation-presentation.md) | Improve conversation overview and reading context | P2 | 3–4 | Q01, Q04 | economy |
| [Q37](tasks/Q37-message-draft-exit.md) | Protect message drafts and describe their lifetime honestly | P1 | 2–4 | Q27, Q29 | economy |
| [Q38](tasks/Q38-moderation-review-context.md) | Make moderation decisions contextual and deliberate | P1 | 3–5 | Q03, Q27 | economy |
| [Q39](tasks/Q39-visual-browser-regressions.md) | Add focused visual and cross-browser quality coverage | P1 | 4–6 | Q01–Q38 | economy |
| [Q40](tasks/Q40-integrated-quality-candidate.md) | Verify the integrated app and reconcile remaining gates | P1 | 4–6 | Q39 | experienced |

## Execution sequence

These are overlapping work streams, not dates. Start a task as soon as its reviewed dependencies and merge slot are available.

1. **Foundations and quick fixes:** Q01–Q04, Q06, Q08, Q09, Q11, Q18 and Q27. Publish the Q32 media contract early if the photos work stream starts.
2. **Discovery quality:** Q05, Q07, Q10, Q12–Q17 and Q20. Finish actual browsing defects before spending time on visual refinements.
3. **Saved searches, alerts and accounts:** Q19 and Q21–Q26. Q21 needs a reviewed cursor contract; Q26 reuses the existing export boundary.
4. **Owner and moderation flows:** Q28–Q31, Q35 and Q38. Q27 separates their files; Q29/Q37 still share the rental-desk exit handling and must integrate sequentially.
5. **Photos and messages:** Q32–Q34 and Q36–Q37. Q32/Q33 are one coordinated producer/lifecycle chain; Q34 consumes the reviewed result.
6. **Acceptance:** Q39 then Q40. Q39 can prepare fixtures earlier, but final screenshot approval and cross-browser acceptance wait for the screen changes.

## Current evidence that changes the priorities

The previous sprint already implemented session rotation, erasure, message retries/read cursors, identity preservation, source status, search race fencing, keyboard dialogs and polygon entry. Existing accessibility checks cover four widths and 200% text. This plan preserves that work and targets specific gaps.

The most concrete problems are map-only pagination hidden with the list, comma-decimal filter corruption, missing account-export UI, generic business-error messages, all-or-nothing private collection loading and missing owned-photo uploads. Visual work improves density, controls, cost hierarchy, galleries, comparisons, history and conversation context.

The older T23/T24 media stretch requirements are selected here as Q32–Q34, with current code and lifecycle review. The old plan remains historical and is not overwritten. Q40 reconciles the incomplete T07 evidence: the inspected local manifest covered about 8.45 hours with 2 of 12 intervals complete on old pin `b3782cc`, through 12 November 2026 at 05:54:21 UTC. Gratka still failed on that pin. Calendar time passing the target is not a completed run or evidence for the current parser.

## Boundaries and remaining acceptance

Keep this plan focused on the present rental app. Full Polish translation, saved-search rename/pause APIs, shareable search URLs, geocoding/location enrichment, photo-similarity matching, phone-fingerprint key rotation, optional unread-message email, billing and broader property categories are deliberately deferred. They are not extra tasks hidden inside the 40 packets.

Real sender/inbox and push delivery, selected map-provider/domain credentials, installed iOS/Android checks, a real screen reader, corrected-parser live validation and a fresh eligible soak, permitted OLX access, and cloud deployment remain separate acceptance gates. Q40 records exact missing inputs and completed independent work. It does not execute those external operations or treat mocked tests as live evidence.

Execution was authorized on 17 November 2026. Work proceeds on codex/app-quality-2026-11 in an isolated integration checkout. The integrator assigns dependency-ready packets and reviews every change. Push, deployment and external messaging remain excluded.
