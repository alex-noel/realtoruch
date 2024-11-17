# Q14 Comparison and selection editing

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

Base revision `845f90f` on `codex/q14-comparison` includes Q11 image recovery and Q13 cost presentation.

## Result

The comparison tray names selected homes and allows individual removal. The comparison dialog places values for each metric side by side at phone and desktop widths. Fixed-height image or placeholder frames and shared metric rows keep long titles and source names aligned. The panel explains that it compares listing snapshots from when each home was added.

`App.tsx` owns tray selection and the three-home limit. `Dialogs.tsx` owns the comparison table. Synthetic 320 px screenshots show [the original stacked comparison](../previews/quality/q14-before.png) and [the shared metric rows](../previews/quality/q14-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q14-AC01 | PASS | The browser test selects three homes, verifies feedback when adding a fourth, removes one named selection and sees the two remaining homes. |
| Q14-AC02 | PASS | The browser test checks common row positions at 320 and 1440 px, including a long title, a long unbroken source name and a missing photo. |
| Q14-AC03 | PASS | After a detail fetch fails and discovery receives an updated price, comparison keeps the captured rent and shows the snapshot caption, delisted status and unknown building fees and commission. Opening comparison issues no detail request. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 16:16–16:22 CET. Browser checks used Node 24.6.0, Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic fixtures and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:e2e -- accessibility.spec.ts -g 'Q14\|Q04\|Q11'` | 0 | 6 passed across desktop and mobile, 0 skipped | `q14-compare-20261117-03` |
| `npm run test:e2e -- accessibility.spec.ts -g 'Q14 comparison'` | 0 | 2 passed with the final known-cost fixture and assertion | `q14-compare-20261117-04` |
| `npm run test:e2e -- accessibility.spec.ts --project=mobile -g 'Q14 comparison'` | 1 | Expected baseline failure. The original dialog omitted the snapshot caption. | `q14-compare-baseline-20261117-01` |

## Compatibility and review

Comparison uses captured listing values, the existing photo recovery and the current three-home limit. Account-change fences retain their existing behavior. Installed-device UI and spoken screen reader output were outside the browser checks. Integrator review remains pending.
