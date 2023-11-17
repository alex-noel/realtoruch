# Q09 Results pagination

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

The change starts from `e50735d` on `codex/q09-map-pagination` and has no task dependencies.

## Result

Discover shows one pager above the results in list, split and map-only views. Selecting a page scrolls to the results heading and moves focus there. During a pending or failed request, the pager describes the last displayed page and disables both controls.

`App.tsx` owns the shared pager and `boundaries.spec.ts` covers it with a synthetic 49-home catalog. The integrator approved a focused change to `PropertyMap.web.tsx` so selecting a pin updates its highlight in place. This lets the existing dialog focus restoration return to the opening pin.

Synthetic mobile screenshots show [the baseline map](../previews/quality/q09-before.png) and [the map on page two with pagination](../previews/quality/q09-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q09-AC01 | PASS | The browser regression visits all three pages in map-only, list and split views. It compares marker listing IDs and card labels to the same ordered fixture slice of 24, 24 and 1 homes. |
| Q09-AC02 | PASS | The regression holds a request for page two and then holds and fails a changed-filter request. It checks that both controls are disabled for the prior snapshot, checks that retry re-enables valid controls and checks the first and last page limits. |
| Q09-AC03 | PASS | Switching views retains the page and active direct-offer filter without another listing request. Closing details from a pin or card on page two restores its focus and scroll position. |

## Verification

Commands ran from `apps/mobile` on 17 November 2026 around 15:18–15:22 CET. Final typecheck and browser verification used Node 24.6.0. The earlier baseline reproduction used Node 23.6.0. Browser runs put the checkout's `.venv/bin` on `PATH` and used Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Typecheck passed | |
| `npm run test:e2e -- boundaries.spec.ts` | 0 | 4 passed, 0 failed, 0 skipped across desktop and 390 × 844 Chromium | `q09-pager-node24-20261117-01` |
| `npm run test:e2e -- boundaries.spec.ts --project=mobile -g 'results pager'` | 1 | Expected regression failure with the base App restored for the run. Map-only lacked the `Page 1 of 3` label. The implementation was restored before final verification. | `q09-pager-baseline-20261117-01` |

## Compatibility and review

Both views continue to render from the same search snapshot. Existing request-generation fences and filter semantics apply. The change uses the current API, schema and dependencies. The browser harness used only loopback services and synthetic fixtures. Installed iOS and Android behavior was outside the browser check. Integrator review remains pending.
