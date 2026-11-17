# Q35 Advert status and appeal progress

Status **IMPLEMENTED_LOCAL**, with local checks passing and strong review pending.

Base revision `bd243fb` on `codex/q38-moderation` includes Q38. The integrated base includes Q03, Q25, Q27 and Q31.

## Result

The owner desk loads advertiser profile and adverts independently, with separate loading and retry states. A loaded advert keeps its last-saved time, lifecycle state and moderation visibility visible. Withdrawal asks for confirmation using the advert title and address, and confirmed actions announce the affected title.

Hidden adverts offer appeal entry and omit publishing. Pending review disables another appeal, including after refresh. The owner-only response adds a minimal pending or resolved status from the existing reports. A pending owner report also counts as pending review because the existing appeal endpoint rejects a duplicate while it exists. The projection excludes report reasons and other users' reports.

Synthetic mobile screenshots show [the original load failure](../previews/quality/q35-before.png) and [the updated advert status](../previews/quality/q35-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q35-AC01 | PASS | The browser holds both initial loads, fails profile, and verifies the advert list loads. Retrying profile leaves the list intact. A later advert refresh failure leaves profile and the last list available. |
| Q35-AC02 | PASS | The browser confirms hidden adverts lack publishing, submits an appeal, refreshes and sees the pending review with no repeat action. It then loads a resolved review and sees the appropriate publishing path. |
| Q35-AC03 | PASS | Cancel makes no withdrawal request and duplicate confirmation produces one request. The browser checks named success and saved time. Backend tests cover owner-only status, exclusion of others' reports and public payloads, and the existing hidden visibility and appeal rules. |

## Verification

Commands ran on 17 November 2026 around 16:44–16:49 CET. Browser runs used Node 24.6.0, Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18. Deterministic dashboard faults used routed synthetic owner records. The owner publishing and messaging journey used real loopback services.

| Command and working directory | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` in `apps/mobile` | 0 | Passed | |
| `npm run test:e2e -- owner.spec.ts` in `apps/mobile` | 0 | 10 passed across desktop and mobile, 0 skipped | `q35-owner-20261117-03` |
| `npm run test:e2e -- owner.spec.ts --project=mobile -g 'Q35 owner dashboard'` in `apps/mobile` | 1 | Expected baseline failure. The original dashboard lacked the adverts loading state. | `q35-owner-baseline-20261117-01` |
| `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests/test_marketplace.py backend/tests/test_identity_review.py` in the checkout root | 0 | 13 passed, including two owner projection checks | |

## Compatibility and review

The own-advert response adds `appeal_status`. The client also types the existing `updated_at` field. No schema or moderation algorithm changed. The owner list remains scoped to the authenticated user. Browser verification also tightened synthetic verification-mail selection to its exact recipient. Installed-device behavior and strong integration review remain outstanding.
