# Q39 Visual and browser quality

Implemented focused profiles; final integrated reruns are recorded by Q40. The normal functional profile retains desktop/responsive Chromium. `E2E_QUALITY_PROFILE=cross-browser` selects six tagged renter, account-restore and owner/message journeys across WebKit and Firefox. `E2E_QUALITY_PROFILE=visual` selects ten reviewed screenshots (five screens at 390/1440px). Screens use synthetic fixtures, local images/tiles and fixed time, locale and timezone. Real authentication in the browser harness uses synthetic accounts and local file mail only. Responsive Chromium and WebKit are not installed mobile apps.

Exact engines installed locally: Playwright Chromium1254, WebKit2388 (27.2), Firefox1572 (159.0), macOS arm64. Task binaries are in `/private/tmp/realtoruch-quality-browsers`; Chromium entries link to the existing locked cache. Missing engines fail the requested profile. Reviewed visual baselines are macOS-specific because the current product uses system fonts. Requesting the visual profile on another platform fails explicitly pending reviewed platform baselines; it does not silently pass or skip. CI's functional profile continues to use Chromium.

Evidence on 17 November 2026:

- Initial candidate capture revealed a real multiline owner-field overlap. Field flex basis now respects intrinsic content. `q39-fields-candidates` passed four cases: full 320/390/768/1440px and 200% text geometry plus visual captures. The integrator visually inspected the ten screens before copying only those candidates into the baseline directory; owner textarea/property-chip geometry has an explicit assertion.
- `q39-reviewed-baselines`: two browser cases, all ten comparisons passed. No bulk snapshot update was used.
- `q39-overlap-fault`: intentionally injected heading overlap caused the screenshot assertion to fail (41,566 pixels / 13% different), as required. The injection is test-only behind `QUALITY_OVERLAP_FAULT=1`; normal runs omit it. Final normal rerun remains required.
- `q39-engines-initial`: owner/message and account-restore passed in both engines (four cases); renter fixtures initially rejected unfamiliar engine names. The runner also had an environment-forwarding typo discovered and corrected before acceptance.
- `q39-engines-journey`: both real renter journeys passed after allowing separately identified WebKit/Firefox fixtures. Addresses and source IDs are isolated per browser. No app behavior was weakened to pass.

Run from `apps/mobile` with Node24 and the Python3.12 virtualenv on PATH:

```sh
E2E_QUALITY_PROFILE=visual VERIFY_RUN_ID=unique-visual npm run test:e2e
E2E_QUALITY_PROFILE=cross-browser VERIFY_RUN_ID=unique-engines npm run test:e2e
```

Install matching engines with the locked Playwright CLI before requesting a profile. `QUALITY_CAPTURE=1` creates review candidates in private run output; it never approves a baseline automatically. Any future snapshot change must be inspected, linked to the UI change and followed by a passing normal comparison.
