# Q20 Saved homes and favorite feedback

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

Base revision `3b6b6aa` on `codex/q14-comparison` contains Q14. The integrated base includes Q04, Q13 and Q18.

## Result

The card and detail save controls share per-home pending and failed states. A failed mutation leaves the confirmed state in place and offers an inline retry. Saved homes can be filtered by All, Available and Unavailable. A filter with zero matches offers a return to All. An empty loaded collection offers a way to browse homes.

Availability follows existing listing status. Available is active. Unavailable is delisted or unconfirmed. The existing server visibility filter and account-generation checks apply. The synthetic mobile screenshots show [the original page-level error](../previews/quality/q20-before.png) and [inline retry after failure](../previews/quality/q20-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q20-AC01 | PASS | The browser test dispatches two immediate save activations and observes one request. While the request is held, both card and detail actions are disabled. Failure preserves the unsaved state and exposes retry from both surfaces. |
| Q20-AC02 | PASS | The browser holds removal and checks the row stays saved until success. It verifies distinct zero-match and empty-collection states. |
| Q20-AC03 | PASS | The test opens a delisted saved home. A separate test holds an old account's save result through sign-out and sign-in and verifies the new account receives neither a saved flag nor recovery for the old operation. The implementation uses the existing server visibility checks. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 16:24–16:27 CET. Browser checks used Node 24.6.0, Python 3.12.9, Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic accounts and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:unit -- tests/accountCollections.test.ts` | 0 | 16 passed | |
| `npm run test:e2e -- accessibility.spec.ts -g 'Q20\|Q04\|Q14'` | 0 | 8 passed across desktop and mobile, 0 skipped. Includes returning focus to a settled save action. | `q20-favorites-20261117-02` |
| `npm run test:e2e -- accessibility.spec.ts -g 'Q20 waits for favorite'` | 0 | 2 passed with the final screenshot framing | `q20-favorites-20261117-03` |
| `npm run test:e2e -- accessibility.spec.ts --project=mobile -g 'Q20 waits for favorite'` | 1 | Expected baseline failure. The original card had no disabled Saving action during a held request. | `q20-favorites-baseline-20261117-01` |

## Compatibility and review

The existing favorites API confirms mutations and retains responsibility for moderation visibility. The app's session generation fences pending and failed activity, and account changes clear it. Installed-device behavior and spoken screen reader output were outside the browser checks. Integrator review remains pending.
