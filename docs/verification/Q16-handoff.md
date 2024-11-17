# Q16 Overlapping map homes

Status **IMPLEMENTED_LOCAL**, with local checks passing and strong review pending.

Base revision `5745c37` on `codex/q12-gallery` includes Q15. Q09 paging is present through the integrated base.

## Result

Overlapping pins on a results page combine into a count marker. Activating it opens a keyboard-accessible list on web and a scrollable list on native. Choosing a home opens its detail and highlights its pin. Each group uses an existing approximate coordinate from its members. The map recalculates groups as zoom changes and suppresses them while drawing an area.

`mapGroups.ts` provides the shared grouping calculation. Web uses Leaflet's projection, and native estimates the onscreen positions from the current region and viewport. The synthetic browser screenshots show [overlapping individual pins](../previews/quality/q16-before.png) and [the five-home chooser](../previews/quality/q16-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q16-AC01 | PASS | The browser check tabs through all five choices, opens a detail with Enter, and separately opens each detail by touch. A mocked native adapter checks the native count marker and unchanged anchor. |
| Q16-AC02 | PASS | The browser check restores focus to the count marker, verifies its selected style and the selected choice, checks markers are suppressed while drawing, and compares the next page's marker IDs to its fixture slice. |
| Q16-AC03 | PASS | Browser network capture contains only listing pages one and two. The shared tests check transitive overlap, zoom, active and geocoded eligibility, exact anchors and all member IDs. The chooser describes locations as approximate. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 16:02–16:06 CET. Browser runs used Node 24.6.0, Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic fixtures and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:unit -- tests/mapGroups.test.tsx` | 0 | 5 passed, including two native adapter checks | |
| `npm run test:e2e -- boundaries.spec.ts accessibility.spec.ts journey.spec.ts -g 'Q16\|Q15\|TC03\|TC05\|results pager\|search controls\|sort choices\|draw and save'` | 0 | 18 passed across desktop and mobile, 0 skipped | `q16-groups-20261117-02` |
| `npm run test:e2e -- boundaries.spec.ts -g 'Q16 grouped pins'` | 0 | 2 passed across desktop and mobile after the final fixture capture adjustment | `q16-groups-20261117-03` |
| `npm run test:e2e -- boundaries.spec.ts --project=mobile -g 'Q16 grouped pins'` | 1 | Expected baseline failure. The old map omitted the group marker. | `q16-groups-baseline-20261117-01` |
| `npm exec -- expo export --platform ios --platform android --output-dir ../../.local/verification/Q16/native-20261117-02` | 0 | Both Hermes bundles exported | `native-20261117-02` |

## Compatibility and review

The adapters group only the homes they already receive. Polygon controls, coordinate entry, map recovery and lazy loading keep their existing interfaces. The saved-search journey checks map membership for active and delisted homes through the grouped marker's member IDs. The native projection approximates view positions using the reported region. Installed iOS and Android gesture and screen reader behavior remains a device verification gate. Strong review remains pending.

On 17 November 2026 around 16:11 CET, the amended marker sizing passed Node 24 typecheck, all five unit checks and all four grouped-pin and pager Chromium checks in `q16-marker-type-20261117-02`. The browser checks double the marker text size, verify a 500,000 zł price is clipped within its marker with the full accessible label, and verify the group count and label fit.
