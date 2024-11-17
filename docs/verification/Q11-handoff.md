# Q11 Broken photo recovery

VERIFIED_LOCAL after parent implementation review. Evidence collected 17 November 2026, Europe/Warsaw, Node24.6.0/Python3.12.9 with isolated local fixtures.

ListingPhoto now uses a source-keyed load lifecycle, catches web/native image errors and renders a labelled placeholder in the original frame. Switching source resets recovery state, and late events from an unmounted source cannot change the replacement. Original lazy loading and alt labels remain. Missing-photo call sites remain assigned to Q12/Q14 as planned.

| Criterion | Evidence |
| --- | --- |
| Q11-AC01 | Q11 browser test covers HTTP404 and corrupt image bytes in card, detail and compare. |
| Q11-AC02 | Gallery changes broken→working→corrupt→working; real naturalWidth confirms decoding, with no retry loop. Source-keyed component isolates old failures. |
| Q11-AC03 | Failed/loaded detail frame heights match within1px; card height remains≥202px. The native Image uses the same error handler and fallback, but installed native rendering is not verified. |

Commands from apps/mobile under Node24: npm run typecheck exit0; VERIFY_RUN_ID=q11-photo-20261117-01 npm run test:e2e -- accessibility.spec.ts --grep Q11 exit0,2passed/0failed/0skipped (desktop and390px Chromium). The full existing suite is reserved for integrated validation. No dependency/API changes or external requests.

[Sanitized synthetic comparison screenshot](../previews/quality/q11-photo-fallback.png). Raw artifacts are in the integration checkout .local/verification/T18/q11-photo-20261117-01.
