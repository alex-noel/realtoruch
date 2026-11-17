# Q38 Contextual moderation review

Status **IMPLEMENTED_LOCAL**, with local checks passing and strong review pending.

Base revision `efa2397` on `codex/q38-moderation` includes Q03 response categories and the Q27 review desk extraction.

## Result

The desk distinguishes loading, empty and failed queues, gives each report its own decision reason, and shows the selected report's age and home details. Confirmation shows the affected home and the recorded reason. Merging also shows the target and sources being moved. Separating shows the specific source. A recorded dismissal leaves the home's visibility unchanged.

After a 409 the desk closes the stale confirmation and loads the queue again. Permission errors clear the queue. Other failures preserve the confirmation and the per-report reason. The synthetic screenshots show [the original queue](../previews/quality/q38-before.png) and [targeted merge confirmation](../previews/quality/q38-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q38-AC01 | PASS | The browser switches between two reports, confirms each reason remains separate, then returns to the same reason after a failed merge. |
| Q38-AC02 | PASS | Browser assertions cover hide, restore, merge and split confirmation context. Escape and Cancel make no decision request. Double activation submits one merge with the captured target and reason. Split sends the captured source ID. |
| Q38-AC03 | PASS | The browser checks refresh after an already-reviewed response, clearing restricted content after a 403, and session recovery after a 401. An actual ordinary verified account receives 403 for queue and decision requests and cannot write to the capability endpoint. Existing backend review and identity tests pass. |

## Verification

Commands ran on 17 November 2026 around 16:39–16:43 CET. Browser runs used Node 24.6.0, Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18. The browser fixture used routed moderator data and faults. The ordinary-user authorization check used the real loopback API. Backend tests used the existing temporary databases.

| Command and working directory | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` in `apps/mobile` | 0 | Passed | |
| `npm run test:e2e -- owner.spec.ts -g 'Q38'` in `apps/mobile` | 0 | 4 passed across desktop and mobile, 0 skipped | `q38-review-20261117-03` |
| `npm run test:e2e -- owner.spec.ts --project=mobile -g 'Q38 confirms'` in `apps/mobile` | 1 | Expected baseline failure. The original desk reports an empty queue during loading. | `q38-review-baseline-20261117-01` |
| `PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests/test_identity_review.py backend/tests/test_marketplace.py` in the checkout root | 0 | 11 passed | |

## Compatibility and review

The UI uses the existing report timestamp, authorization checks, and review and identity endpoints. The backend algorithms and payloads remain unchanged. Review by an authorized live moderator, installed-device interaction and strong integration review remain outstanding.
