# Q37 — Message drafts stay within the rental desk

Status: IMPLEMENTED_LOCAL; strong private-state/retry review pending. Base b67e9629b4fa9e82687e550e10cc188e06ac5395. Message bodies and retry identities remain in the existing in-memory model; no persistent draft storage or server draft entity was added. Copy now states that unsent text lasts only while the rental desk stays open.

The existing single desk confirmation composes owner edits with any message draft, even when Messages is off-tab. Thread and tab changes within the desk retain drafts; closing, Escape, native modal back and View home ask before discarding. A pending send must finish before closing. Keep editing restores focus where available. Save-and-leave is hidden if doing so would silently discard a separate message draft. Confirmed discard, session reset and desk teardown clear all message drafts; session reset overrides the ordinary guard. View home no longer stops the model before a canceled exit. Q36's target/viewport composer focus fence and message visibility/read machinery remain intact.

| Criterion | Evidence |
| --- | --- |
| Q37-AC01 | Desktop/mobile browser covers A→B→A draft retention, View home cancel, off-tab owner/message composite prompt, close/Escape Keep and Discard; native modal callback adapter test covers hardware back wiring. |
| Q37-AC02 | Model test clears all private state while a delayed send resolves; browser forces session expiry with a draft confirmation open and verifies immediate close/clear. |
| Q37-AC03 | Existing and new unit tests plus browser held-send retry verify unchanged text reuses its client ID. Failure copy says the draft remains only while the desk is open. |

Actual evidence date: 17 November 2026 CET. Python 3.12.9, Node 24.6.0; synthetic accounts and loopback services. No message bodies or traces are committed.

| Command | Result |
| --- | --- |
| `npm --prefix apps/mobile run test:unit` | 234 passed in 17 files, including message, session and native modal adapter tests. |
| `npm --prefix apps/mobile run typecheck`; `git diff --check` | exit 0. |
| `VERIFY_RUN_ID=q37-send-final-20261117 npm --prefix apps/mobile run test:e2e -- message-drafts.spec.ts` | 2 passed desktop/mobile; ignored run evidence in `.local/verification/T18/q37-send-final-20261117`. |
| `VERIFY_RUN_ID=q37-final-20261117 npm --prefix apps/mobile run test:e2e -- message-drafts.spec.ts owner-guard.spec.ts` | 4 passed desktop/mobile. |
| `VERIFY_RUN_ID=q37-read-a11y-20261117 npm --prefix apps/mobile run test:e2e -- message-quality.spec.ts accessibility.spec.ts --grep 'Q36 conversation metadata\|T20-TC01'` | 4 passed desktop/mobile, including offscreen unread behavior and normal/200% text layouts. |

A targeted accessibility test was updated to explicitly discard the unsent fixture before closing, preserving its earlier layout/keyboard checks. The shared advert desk delegates View home to the existing composed shell guard to avoid nested confirmations. Entry JavaScript measured 648,269 uncompressed bytes in the combined owner/message run, under the 650,000-byte budget. No installed native-device behavior or durable storage is claimed.
