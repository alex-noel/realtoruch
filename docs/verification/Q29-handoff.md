# Q29 — Protect unsaved owner edits

Status: IMPLEMENTED_LOCAL; strong private-account reset review pending. Base d659984 on branch codex/q29-owner-guard. A single rental-desk guard covers advert and profile fields, including raw numeric values, coordinates and photo links. Back, profile collapse, tab changes, dialog close/Escape and the native modal close callback route through it. Keep editing restores input focus; discard clears the profile snapshot when transitioning within the desk. Save and leave is offered only for a valid complete form, waits for a successful save and leaves failures visible with the draft intact. An account/session reset unmounts private editor state and fences a pending exit continuation.

| Criterion | Evidence |
| --- | --- |
| Q29-AC01 | Desktop/mobile synthetic browser exercises profile and advert exits, close, Escape, mode switch, Back, valid save-and-leave and invalid-draft guard. |
| Q29-AC02 | Browser injects a 503 on save, confirms visible failure and retained fields, retries successfully, and checks focus after Keep editing. |
| Q29-AC03 | No automatic save; browser forces refresh/session expiry with a dirty editor and checks it disappears without a discard prompt. The native Modal adapter unit checks `onRequestClose` invokes the same shell close callback. |

Actual evidence date: 17 November 2026 CET; Python 3.12.9, Node 24.6.0, isolated synthetic services. No installed-device claim.

| Command | Result |
| --- | --- |
| `npm --prefix apps/mobile run typecheck` | exit 0. |
| `npm --prefix apps/mobile run test:unit -- tests/ownerGuardNative.test.tsx tests/ownerValidation.test.ts tests/session.test.ts` | 64 passed, exit 0. |
| `VERIFY_RUN_ID=q29-guard-final4-20261117 npm --prefix apps/mobile run test:e2e -- owner-guard.spec.ts` | 2 passed (desktop/mobile), exit 0; ignored run evidence under `.local/verification/T18/q29-guard-final4-20261117`. |
| `git diff --check` | clean. |

Earlier browser runs exposed an incorrect test label and a timeout shorter than the 15-second refresh interval; corrected cases passed. No before/after screenshots were captured. There are no backend, schema or dependency changes. Q37 can register its message draft with the same shell guard instead of adding a second dialog. No external sends or publication occurred.
