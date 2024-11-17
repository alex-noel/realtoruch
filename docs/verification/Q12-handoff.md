# Q12 Listing photo gallery

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

Base revision `9c636cd` on `codex/q12-gallery` includes the reviewed Q11 photo recovery.

## Result

Listing details show the current photo position, labelled previous and next buttons, and up to five nearby thumbnails. A one-photo listing shows its position. A listing without photos shows an explicit placeholder. Opening another listing starts at its first photo.

`Dialogs.tsx` owns the gallery. The integrator approved a compact fallback in `ListingCard.tsx` so failed thumbnails use the Q11 photo source lifecycle in a 44 px button. `accessibility.spec.ts` verifies the gallery and keeps the existing Q11 assertions scoped to the main image. The synthetic 320 px screenshots show [the original 30-photo controls](../previews/quality/q12-before.png) and [the bounded gallery](../previews/quality/q12-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q12-AC01 | PASS | The Q12 check exercises zero, one and 30 photos at 320 px, walks to photo 30, verifies the endpoint controls and selected thumbnail, and opens the next listing at photo one. |
| Q12-AC02 | PASS | Left and Right work from the navigation buttons and selected thumbnail. Focus follows the selected thumbnail as the window moves and arrows on the dialog close button leave the photo unchanged. |
| Q12-AC03 | PASS | Exactly five gallery URLs are requested initially. Moving to photo six requests only nearby photos. The failing photo shows the shared placeholder and the next URI displays successfully. The Q11 and lazy-loading regressions also pass. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 15:35–15:38 CET. Node 24.6.0 and the checkout's Python 3.12.9 virtual environment were on `PATH`. Browser checks used Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic fixtures and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:e2e -- accessibility.spec.ts -g 'Q11\|Q12\|TC02\|TC05'` | 0 | 8 passed across desktop and mobile projects, 0 skipped | `q12-gallery-20261117-02` |
| `npm run test:e2e -- accessibility.spec.ts --project=mobile -g 'Q12 gallery'` | 1 | Expected baseline failure. The original gallery lacked the `Photo 1 of 30` position. | `q12-gallery-baseline-20261117-01` |

## Compatibility and review

The gallery uses the current listing payload and shared photo source recovery. The change uses existing dependencies. Installed iOS and Android galleries and spoken screen reader output were outside the browser checks. Integrator review remains pending.
