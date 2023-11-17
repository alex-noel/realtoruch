# Q08 Explicit sort selection

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

Base revision `2fc8b19` on `codex/q08-sort-selector`.

## Result

The sort button shows the active choice and opens a panel with Newest first, Lowest rent, Highest rent and Largest first. Choosing a different option keeps the active filters and restarts results on page one. Cancel, Escape and choosing the active option leave the results intact.

`App.tsx` reuses the shared panel and chips, and `boundaries.spec.ts` exercises the selector using the existing synthetic paged catalog. The 320 px screenshots show [the original control after activation](../previews/quality/q08-before.png) and [the new selector with all options visible](../previews/quality/q08-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q08-AC01 | PASS | The browser test uses Tab and Enter to choose Highest rent directly and touch to select Lowest rent, Largest first and Newest first. It verifies the pressed state on the choices and the selected sort in the trigger's accessible name. |
| Q08-AC02 | PASS | Escape, Cancel and selecting the active sort leave page two and the request count intact. Choosing a different sort issues one request with page one and all other parameters preserved, including the active direct-offer and no-commission filters. |
| Q08-AC03 | PASS | All four choices fit at 320 px. The test delivers the delayed Lowest rent response after Largest first finishes and verifies the latest result stays visible. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 15:25–15:28 CET. Node 24.6.0 and the checkout's Python 3.12.9 virtual environment were on `PATH`. Browser checks used Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic fixtures and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:e2e -- boundaries.spec.ts` | 0 | 6 passed, 0 skipped across desktop and mobile projects. The mobile sort test ran at 320 × 800 with touch enabled. | `q08-sort-node24-20261117-02` |
| `npm run test:e2e -- boundaries.spec.ts --project=mobile -g 'sort choices'` | 1 | Expected baseline failure. Activating the control cycled the sort and no Sort homes dialog appeared. | `q08-sort-baseline-node24-20261117-01` |

## Compatibility and review

The existing search action owns the page reset, cancellation and latest-request checks. The change uses the existing sort values and leaves the API, schema and dependencies intact. Installed iOS and Android behavior and spoken screen reader output were outside the browser check. Integrator review remains pending.
