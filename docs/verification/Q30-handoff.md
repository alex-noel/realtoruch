# Q30 — Recover concurrent advert edits

Status: IMPLEMENTED_LOCAL; strong optimistic-concurrency/moderation review pending. Base Q29 commit 94ab2d7 on branch codex/q29-owner-guard. A version conflict keeps the local validated snapshot and raw editor values, fetches the latest owner advert, shows both values for every difference, and requires an explicit per-field choice before saving against the latest version. A failed/missing latest read is retryable. Reloading the server version requires explicit discard confirmation and resets the clean baseline. A second conflict repeats reconciliation rather than overwriting. Published, withdrawn and hidden state is shown; no publish or moderation rule is bypassed.

| Criterion | Evidence |
| --- | --- |
| Q30-AC01 | Real local API two-session test verifies the original server title remains unchanged until explicit reconciliation and checks the resulting submitted fields. |
| Q30-AC02 | Test retains local title and photo context, injects a failed latest fetch, retries and preserves the editor. Reload requires confirmation; returning to edit is available. |
| Q30-AC03 | The second session changes the advert again before reconciliation; a second conflict requires new choices. A synthetic response displays withdrawn/hidden state. Missing latest and network errors share a retryable unavailable message. |

Actual evidence date: 17 November 2026 CET. Python 3.12.9, Node 24.6.0. Synthetic accounts, local services only.

| Command | Result |
| --- | --- |
| `VERIFY_RUN_ID=q30-conflict-final2-20261117 npm --prefix apps/mobile run test:e2e -- owner-conflict.spec.ts` | 2 passed (desktop/mobile); ignored isolated evidence under `.local/verification/T18/q30-conflict-final2-20261117`. |
| `PYTHONPATH="$PWD/backend" .venv/bin/python -m pytest -o addopts='' backend/tests/test_marketplace.py -q` | 5 passed, including existing version conflict regression. |
| `npm --prefix apps/mobile run test:unit -- tests/session.test.ts tests/ownerValidation.test.ts tests/ownerGuardNative.test.tsx` | 64 passed. |
| `npm --prefix apps/mobile run typecheck` and `git diff --check` | exit 0. |

The initial browser attempt used an incorrect sign-in selector; the corrected scenario passed. No screenshots captured. The hidden/withdrawn display test uses a synthetic owner response; backend moderation remains authoritative. No API, schema, migration, or dependency changes; Q31 can consume the explicit reconciliation flow. No external action or publication was performed.
