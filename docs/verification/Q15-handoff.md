# Q15 Map failure recovery

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

Base revision `dafe9b1` on `codex/q12-gallery`.

## Result

A failed map component or engine import offers Retry map and, in discovery, Show homes as a list. Repeated tile errors show a separate message above the map while keeping its viewport stable. Retry recreates the Leaflet map and keeps the current filters, applied area and drawing state. Owner advert entry keeps the existing manual latitude and longitude fields available.

`MapRecovery.tsx` contains the shared failure view and boundary so importing the fallback keeps drawing and Leaflet deferred. `MapDrawing.tsx` keeps coordinate entry available when the map is unavailable. The native adapter handles caught rendering errors and a 12-second map-readiness timeout. `App.tsx` supplies the existing list-view switch. The [original tile failure](../previews/quality/q15-before.png) and [updated recovery controls](../previews/quality/q15-after.png) use synthetic 390 px browser fixtures.

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q15-AC01 | PASS | Playwright separately rejects the map and Leaflet chunks and injects 503s into distinct tile URLs. It checks separate map-load and tile alerts. |
| Q15-AC02 | PASS | The browser retries both chunks, retries a failed tile layer, verifies the old map pane was removed and that one map and click listener respond, and checks the applied polygon and direct filter survive. The adapter only recreates the map on an explicit retry. |
| Q15-AC03 | PASS | The tile test chooses the list fallback and opens owner advert entry with tile errors still active. Both coordinate fields accept values and report Location set. Attribution is visible after successful tile loads. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 15:50–15:57 CET. Browser runs used Node 24.6.0, Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic fixtures and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:e2e -- accessibility.spec.ts boundaries.spec.ts -g 'Q15\|TC03\|TC05\|results pager\|search controls'` | 0 | 12 passed across desktop and mobile projects, 0 skipped | `q15-map-20261117-04` |
| `npm run test:e2e -- accessibility.spec.ts --project=mobile -g 'Q15 tile recovery'` | 1 | Expected baseline failure with the old web adapter, which omitted the tile-failure alert | `q15-map-baseline-20261117-01` |
| `npm exec -- expo export --platform ios --platform android --output-dir ../../.local/verification/Q15/native-20261117-02` | 0 | Both Hermes bundles exported | `native-20261117-02` |

## Compatibility and review

Discovery and owner maps use the current search, listing and coordinate interfaces. Web map attribution and lazy loading retain their existing behavior. Native iOS and Android interaction remains unverified. This host has no `simctl` or `adb`, and the native readiness callback reports map initialization rather than individual provider tile failures. Integrator review remains pending.
