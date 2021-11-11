# Core implementation execution log

Actual implementation started: 2026-11-11T20:00:52.148920+00:00. The earlier calendar is a planning estimate; tasks start as dependencies clear.

Integration branch: `codex/core-sprint-2026-11`. Baseline plan commit: `2d9a22d`.

The user authorized four worker assignments and the parent integrator/reviewer. This session permits three concurrent child workers plus the parent; the fourth assignment rotates into an available slot. A/B/C start T01/T05/T09; D is assigned T13 after T01 acceptance. No worker may bypass a dependency because a slot is free.

Models/reasoning are selected per task: lighter models for bounded fixtures/configuration, coding models with high or extra-high reasoning for transactions, identity, auth and migration changes. The integrator independently reviews evidence and sensitive changes.

Cloud deployment, paid resources and external emails remain outside this core execution. The user subsequently authorized GitHub source pushes; that exception does not authorize deployment. Every new commit uses the repository backdating helper. Test evidence uses actual dates.

## Task status

| Task | Status | Model | Reasoning | Dependencies |
| --- | --- | --- | --- | --- |
| T01 | VERIFIED | gpt-6.1-terra | high | None |
| T02 | VERIFIED | gpt-6.1-sol | medium | T01 |
| T03 | VERIFIED | gpt-6.1-terra | high | T01 |
| T04 | VERIFIED | gpt-6.1-sol | high | T03 |
| T05 | VERIFIED | gpt-6.1-sol | medium | None |
| T06 | VERIFIED | gpt-6-luna | medium | T05 |
| T07 | LIVE_SOAK_RUNNING | gpt-6.1-sol | high | T03, T04, T05 |
| T08 | VERIFIED | gpt-6.1-terra | xhigh | T01 |
| T09 | VERIFIED | gpt-6-luna | high | None |
| T10 | VERIFIED | gpt-6.1-terra | xhigh | T08, T09 |
| T11 | VERIFIED | gpt-6.1-terra | high | T10 |
| T12 | VERIFIED | gpt-6.1-sol | high | T08, T11 |
| T13 | VERIFIED | gpt-6.1-terra | xhigh | T01 |
| T14 | VERIFIED | gpt-6.1-terra | high | T01 |
| T15 | VERIFIED | gpt-6.1-terra | xhigh | T10, T13, T14 |
| T16 | VERIFIED | gpt-6.1-sol | high | T10 |
| T17 | VERIFIED | gpt-6.1-sol | high | T14, T16 |
| T18 | VERIFIED | gpt-6.1-terra | high | T01, T14, T02 |
| T19 | VERIFIED | gpt-6.1-sol | high | T03, T14 |
| T20 | VERIFIED | gpt-6.1-sol | high | T17, T19, T18 |
| T21 | VERIFIED | gpt-6.1-sol | high | T14 |
| T25 | VERIFIED | gpt-6.1-terra | high | T08, T11, T12 |
| T26 | VERIFIED | gpt-6.1-sol | medium | T03, T08, T13 |
| T27 | VERIFIED | gpt-6.1-sol | high | T11, T15 |
| T28 | VERIFIED | gpt-6.1-terra | high | T02, T08, T13, T15, T26 |
| T32 | LOCAL_PARTIAL | parent integrator | independent review | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T25, T26, T27, T28 |

## Integration decisions

- Prepared separate worktrees for T01, T05, T09 and T13; workers must not edit the integrator checkout.
- Accepted T01 registry direction: ordered rental/auth migrations with checksums and separate SQLite upgrade hooks; final implementation still requires review.
- Approved T05 bounded parser-code/non-rental diagnostics in connectors.py as a targeted scope extension for testable production-path behavior.
- Existing Node 24.6.0 is available locally; no global toolchain changes are needed.

## Evidence

T05 is accepted and integrated as `c4d6062`: 88 targeted tests independently repeated by the parent, plus the worker’s 169-pass offline regression (5 optional service skips). Live provider access remains unverified. T06 starts from this reviewed dependency.

T01 is accepted at `a74ca26`, including SQL packaging and clean-install/cleanup fixes: the parent independently repeated 9 real-service tests with zero skips. T09 is accepted after notification-sequence and fixture-validation review; its synthetic corpus remains frozen and surfaces 20 ambiguous automatic merges for T10. T03 is accepted at `ef7788d` after 9 targeted and 11 real-service tests, with durable robots pacing assigned to T04. T06 is receiving network-boundary review corrections; T08 and T13 are running. See per-task handoffs and `execution.json` for exact state.

T06 is accepted at `9d8c816` after network-boundary corrections and 29 targeted tests. T08 is integrated at `e257706` and accepted as a functional dependency after 14 real-service tests; its specified hardware benchmark remains unverified (LOCAL_PARTIAL). T13 is undergoing integrated delivery/migration review. T02, T04 and T14 are active; T10 is ready for the next slot.

T13 is accepted at `4e6f00b` after parent security/concurrency review, 82 combined real-service/race passes and 41 targeted regression passes. Account closure with concurrent new writes remains T15 scope.

T02 is integrated at `fbbd6d9` with hosted CI still unrun. T10 corrections are at `87cfd34`; combined testing subsequently required building evidence for the contact/photo fallback (`b56f0f8`, `e7eeb88`). T32 will repeat the frozen corpus without tuning. T14 is integrated at `edf5e59` after independent session-race and dependency-audit corrections; actual browser evidence remains T18. T04 is accepted at `1049292` after 95 real-service passes and the checked-only T10 gate integration. T11 is accepted at `79fc5b7` after SQL/methodology review and 101 real-service passes. Current workers: T18 browser, T16 message cursors, T15 account lifecycle. T26 operational changes are in parent review; T12 and T07 are dependency-ready.

T26 is accepted after independent privacy/operations review,105 real-service passes,6 SQLite/Helm passes and12 API regression passes. Hosted/cloud readiness is not claimed; T28 owns scraper authentication and probe wiring.

T15 is accepted at `ade29cb` after independent privacy/concurrency review and 152 combined real-service passes. T16 is accepted at `7cf3994`; its tuple cursors and account guards are integrated. Parent session fixes `3fbab65` and `64b949a` passed targeted actual-browser regressions, with the complete integrated T18 suite still pending.

T07 is integrated at `dcd5768`; 141 combined local tests passed without skips. The live run uses the immutable `b3782cc` detached checkout, beginning 2026-11-11 21:27:38 UTC with a fixed target end of 2026-11-14 21:27:38 UTC. The first cycle obtained four observations from Otodom/Morizon, while Gratka discovery parsing failed. No live removal or long-duration reliability is claimed. T12, T17 and T18 are active; T19, T21, T27 and T28 are dependency-ready.

T12 is accepted after public-contract review and 188 combined real-service passes. Parent T26 correction `b4ae272` aligns queue diagnostics with indexer eligibility even when creation timestamps are ahead. T17 is integrated at `2b69e8a`, and T18 at `3bec9db`: the complete root browser run passed 12 tests without skips, covering the integrated owner inbox and both account/session cases. All 33 frontend unit tests passed after separating unit and browser discovery. This closes T14’s remaining local browser gate. T25 and T19 are active, while T28 is receiving grant and network-boundary corrections. T07 remains time-gated, with one eligible completed cycle and no runner gaps through 2026-11-11 21:58:20 UTC.

T28 is integrated at `a2f53d5`; root verification passed 189 real-service tests without skips. Further review found missing retention-job write permissions on the shared indexer identity, so a real-role regression and narrow grants remain under review. T19 is integrated at `84dfdc1`, with 64 integrated frontend unit passes and a pending browser check. T25’s first five-minute 20-client window returned 4,405 successful responses but exceeded SQL/history latency targets; the matched optimization run and investigation continue. Worker B is implementing T21 in a separate checkout, and worker D is verifying T27 recovery. Heavy checks are coordinated to avoid contaminating the measured capacity windows.

T19 is accepted at `7c8894b`: the broad browser run passed 14 cases and exposed a missing expansion attribute in two narrow-screen cases; the correction passed both focused cases. T28 is accepted at `eceb19d` after an actual-role retention regression verified its narrow maintenance grants. T27 is integrated at `ac23172` after ownership, recovery and erasure review; its combined worker profile passed 190 real-service tests without skips. T20 and T21 are active. T25 now uses equally analyzed fresh catalogs: baseline search targets pass, while history remains over target; the matched aggregate optimization is being measured. Final integration will repeat the complete profiles on the combined candidate.

T08’s remaining reference gate passed on clean `a30d1d5`: all test work ran inside a measured four-CPU/eight-GiB container budget, and 100 changed homes converged in 0.431287 seconds. T21 is integrated at that commit with 118 combined frontend unit passes; worker D is correcting reproduced cold-link/session and slow-link/navigation races before final acceptance. T20’s timed browser budget passes; its final accessibility regression continues. T25 history remains above target and is receiving measured SQL-plan improvements.

The user explicitly authorized GitHub push; `cf7b146` now matches `origin/codex/core-sprint-2026-11`. Hosted run `43115090311` passed real services, web and native bundle jobs, but the offline job found one T08 test fixture made obsolete by T12 title sanitization. A test-only correction is pending its focused check. T20 is locally accepted after all 28 worker browser cases; T21 integration races passed 122 units and eight browser cases. The Gratka mixed-route compatibility fix is integrated at `3db8927` after private-capture replay and 110 portal/connector tests; current pinned soak evidence remains on the earlier parser. T25 final native matched capacity validation is in progress.


## Final integration — 12 November 2026

Code candidate `a17cf16f4e6c3c33d629684fd6a75685eb147b53` passed 392 offline Python tests (115 explicit service-only skips), 240 real-service tests with zero skips, TypeScript, 122 frontend units and 36 browser cases with zero skips. All four [hosted jobs](https://github.com/alex-noel/realtoruch/actions/runs/43119698856) passed. Independent review found and closed moderator-hidden Favorites and correction-only price-drop regressions. T25 native capacity passed; earlier emulated history failure remains explicit. The frozen synthetic corpus remains unchanged. [Release readiness](../../release-readiness.md) and the [complete AC/test index](../../verification/core-acceptance.json) supersede historical pending notes above. Overall LOCAL_PARTIAL: T07's real-duration/provider/final-version gate is still open, and no cloud deployment occurred.
