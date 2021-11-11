# Web accessibility and performance baseline

Measured on **2026-11-11, Europe/Warsaw (CET)** in the T20 checkout from reviewed base `7c8894b`. The test host was an Apple M4 Pro Mac (`Mac16,11`, arm64, 14 CPU cores, 64 GiB RAM), macOS 15.7.7 (24G720). Runtime: Node 24.6.0, Python 3.12.9, Expo 58.0.23, React Native Web 0.21.4, Playwright 1.65.0 headless Chromium 158.0.8127.18. The timed run ran alone apart from the harness's own services and ordinary host processes.

## Reproduce

Use the repository's locked install, Python 3.12 environment and Playwright Chromium. With the virtual environment and compatible Node first in `PATH`, from the repository root:

```sh
cd apps/mobile
VERIFY_RUN_ID=t20-perf-repro npm run test:e2e -- accessibility.spec.ts --grep T20-TC06
cd ../..
python3 scripts/web_budget.py --output-dir .local/verification/T18/t20-perf-repro/dist
```

The existing harness exports production web assets, starts disposable local services, serves a local map tile, and rejects browser requests outside its owned origins. T20 uses a deterministic response fixture on the local listing API route: 100 results named `T20 home 001` through `100`, rent 4,000–5,980 PLN in increments of 20, 24 items per page, and a local placeholder image per result. The fixture isolates UI rendering and state updates from live catalog and photo response variability. This benchmark measures this browser, fixture and export. It does not measure production catalog, provider image transfer or map tile performance.

## Production JavaScript

For final export `t20-final`, `scripts/web_budget.py` resolved the application entry from the `<script src>` tags in the generated `index.html`. It reported **604,662 uncompressed bytes**, passing **≤650,000** with 45,338 bytes to spare. The other startup scripts were the Metro runtime (3,751 bytes) and shared chunk (289 bytes), for **608,702** total eagerly referenced JavaScript bytes. Neither CSS nor lazy JavaScript is included in the entry number.

At 390 CSS px, initial List view defers the map UI and Leaflet scripts. Opening Map view requests both. Opening the rental desk requests the marketplace chunk. The desktop default intentionally opens the map and list together, so those map scripts are requested as soon as that view mounts. Expo still references Leaflet's CSS in the HTML. Listing photos have explicit dimensions and alt text, with browser lazy loading; there is no server thumbnail field in the existing contract, so the app uses the first available source photo at a thumbnail display size without inventing transformed provider URLs.

## Browser timings

Both Playwright profiles use a **390 × 844 CSS px** viewport for this benchmark. For each of three cold samples, the harness opens a new browser context with cache disabled, 150 ms CDP latency, 1.6 Mbit/s downstream, 0.75 Mbit/s upstream and 4× CPU throttling. This governs browser loading of the real web export; catalog responses and photos are fulfilled locally by the fixture. The ready measurement is navigation start through two animation frames after the 100-result heading and first result are visible.

| Run profile | Sample | Load event end (ms) | First contentful paint (ms) | Results ready (ms) |
| --- | ---: | ---: | ---: | ---: |
| desktop | 1 | 3,550.4 | 3,680.0 | 4,041.1 |
| desktop | 2 | 3,559.7 | 3,692.0 | 4,041.7 |
| desktop | 3 | 3,541.1 | 3,672.0 | 4,032.8 |
| mobile | 1 | 3,549.3 | 3,672.0 | 4,006.9 |
| mobile | 2 | 3,559.4 | 3,696.0 | 4,042.4 |
| mobile | 3 | 3,549.7 | 3,680.0 | 4,042.1 |

Cold load has no numeric target in T20. The warm run uses a fresh unthrottled context with the app loaded, then opens and closes the filter and listing dialogs once before measurement. Each of ten rounds opens filters, applies a new minimum rent (4,020–4,200 PLN in 20 PLN steps) and opens the first matching listing. Samples start at the Chromium keydown and end two animation frames after the expected dialog heading or updated result count appears. The nearest-rank p95 is the 29th of 30 durations sorted ascending.

| Run profile | Actions | Raw durations in order within action (ms, rounded to 0.1) |
| --- | --- | --- |
| desktop | Open filters | 17.7, 26.7, 21.0, 28.8, 28.8, 25.0, 29.5, 29.7, 30.2, 30.3 |
| desktop | Apply filters | 42.9, 47.3, 48.0, 34.3, 49.6, 48.3, 47.9, 47.3, 45.9, 46.5 |
| desktop | Open listing | 21.5, 20.1, 19.5, 22.0, 20.0, 21.4, 21.3, 20.6, 21.4, 22.7 |
| mobile | Open filters | 19.7, 26.4, 22.9, 23.8, 29.4, 30.3, 29.3, 27.7, 26.4, 28.2 |
| mobile | Apply filters | 42.2, 48.0, 47.6, 46.5, 44.0, 48.3, 48.7, 48.7, 49.1, 46.6 |
| mobile | Open listing | 21.4, 22.1, 21.7, 21.7, 37.9, 22.5, 29.7, 19.8, 21.3, 19.4 |

**Warm p95: 48.3 ms desktop and 48.7 ms mobile. Both pass the ≤200 ms target.** The full regression run `t20-final` finished the desktop sample set at 23:44:03 CET and the mobile set at 23:45:19 CET. Unrounded samples are in `.local/verification/T20/t20-final/{desktop,mobile}-web-performance.json` (copied from the runner's per-test output). The earlier focused run `t20-perf1` also passed both sets (49.3 ms and 50.1 ms); its samples are in `.local/verification/T20/t20-perf1/{desktop,mobile}.json`. These raw files are not committed.

## Accessibility audit scope

The browser spec exercises search, filters, listing detail, account, saved homes, notifications, the owner editor and message composer at 320, 390, 768 and 1440 CSS px. Its text-only zoom helper doubles fixed font sizes and line heights while preserving the CSS viewport width and checks the heading's resulting size. It checks document width and scrolls essential actions into the viewport, including field validation and close controls. A separate keyboard test checks focus entry, forward and reverse wrapping, Escape and return to the opening control. The polygon editor test submits coordinates via the real local SQL search API and checks that an inside fixture is included and an outside fixture is excluded.

The scoped contrast check samples the computed foreground and nearest solid background of text labels and actions against a 4.5:1 threshold, and checks the visible keyboard outline. Both profiles measured 9.54:1 for the direct, agency and unknown-commission labels and the primary notification action; 6.44:1 for seen and saved; 5.51:1 for delisted; 5.47:1 for compared; and 5.94:1 for the notification label. The accessibility tree and monochrome rendering expose these states through text and pressed state. This is a scoped Chromium audit; assistive technology on physical devices, browser-specific text scaling preferences and other browser engines were not exercised.
