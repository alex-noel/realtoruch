# Q40 media merge safeguard review

Reviewed merge `966f417` against root baseline `4cb5503` on 17 November 2026. This is a bounded merge review and photo-journey adaptation, not final Q40 acceptance. No product source was changed in this follow-up.

## Safeguards

The shared authenticated binary transport retains refresh retry, account-generation fencing, cancellation and private preview authorization. Media decoding, storage conditional writes, idempotency, per-account attachment/cleanup fences, erasure tombstones and no-store retrieval remain present. The integrated public projection check is stricter: both the canonical listing and this owner's own published source must reference the asset. Previously published withdrawn projections remain available intentionally; hidden, erased and unpublished draft assets remain denied. The additive owner appeal projection and bounded export metadata expose no storage/idempotency keys or digests.

The merge preserves Compose's persistent media volume and cleanup worker, separate demo/live/journey storage directories, cloud configuration examples, migration 011, Helm cleanup resources and historical T23/T24 evidence. Defaults remain disabled; local and cloud upload storage require explicit opt-in. The deployment guide correctly distinguishes retained withdrawal photos from moderation/erasure denial. No blocking safeguard regression found in this comparison.

## Adapted browser coverage

`owner-photos.spec.ts` now follows the reviewed Q34 rule: unfinished uploads block saving; it asserts no advert POST before cancellation/retry completes. It preserves generated PNG fixtures, keyboard selection/reorder/cancel, invalid/oversized rejection before transport, a real session refresh after synthetic upload401, stable idempotency keys across401 and503, ready-only ordered IDs, asset descriptions, private401 checks,320px containment, object-URL/input cleanup, second-session conflict isolation, delayed mutation until successful advert write, saved removal and owner-card thumbnail projection.

Q30 conflict recovery now chooses each differing field explicitly. The test selects the latest whole media list, proves its remote photo survives and the rejected local upload is cancelled, then separately removes a saved photo after a confirmed update. Published changes require Q31 preview confirmation. Q35 withdrawal names the target, cancellation sends no request, confirmation sends one, and public previously published thumbnail access remains available while private management stays401 anonymously. All browser traffic is restricted to harness loopback ports or local data/blob URLs.

## Actual checks

Runtime: Node24.6.0, Python3.12.9, macOS arm64. Final browser run completed approximately16:03UTC on17 November2026. Commands run from this checkout with Node24 and its linked `.venv/bin` on PATH:

- `npm run typecheck --prefix apps/mobile`: passed.
- From `apps/mobile`, `VERIFY_RUN_ID=q40-photo-merge-03 npm run test:e2e -- owner-photos.spec.ts`: **2 passed,0 failed,0 skipped**; desktop10.4s and320px mobile9.4s,20.5s suite. Tests exercised current application source at966f417 plus this test-only follow-up.
- `npm run test:unit --prefix apps/mobile -- tests/session.test.ts`: **45 passed**.
- `PYTHONPATH=$PWD/backend .venv/bin/pytest backend/tests/test_media.py -o addopts='' -q --junitxml=.local/verification/Q40/media-merge-local.xml`: **22 passed,19 skipped,0 failed**; PostgreSQL-dependent cases intentionally require the final isolated service profile. This supplemental run is not service acceptance.
- `git diff --check`: passed.
- `scripts/web_budget.py` against the first owned export: **FAIL**,651720bytes against650000. Integrator owns the pending lazy-chunk correction and must verify the final candidate export.

Preliminary browser run01 passed2/2 before the additional withdrawal checks. Run02 failed2/2 because a new cleanup assertion inspected the asset before asynchronous post-save finalization completed; run03 uses bounded polling and passed. An initial supplemental pytest invocation omitted PYTHONPATH and resolved the shared editable root package; its result is invalid for this checkout and was replaced by the explicit-PYTHONPATH result above. No failed final release gate is waived. Raw run directories, logs, mail, XML, storage, screenshots and traces remain ignored and are not committed.

## Remaining acceptance

Final clean integrated revision still requires full offline/service/web profiles, Q39 visual/cross-browser profiles, entry and warm-action budgets, native JavaScript exports and the external gate ledger. No external request, collection, provider send, deployment or push occurred in this task.
