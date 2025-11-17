# Task handoff

Task: Q22 — show truthful email preference loading and recovery

Status: VERIFIED_LOCAL

Base revision: `cc2a9b0`. Branch: `codex/q22-alert-preferences`. Resulting commit: `484ec48`.

## Result

Email alert settings now start unknown and show loading, loaded off, confirmation pending, enabled, unconfigured, and failed states distinctly. The toggle stays unavailable until a preference is loaded, failed updates retain the last confirmed value with a recovery message, and a retry control appears when the lookup fails. Preference state belongs to the current user component and late requests are ignored after disposal.

Changed files: `apps/mobile/src/components/NotificationInbox.tsx`, `apps/mobile/tests/notificationPreferences.test.tsx`, and `apps/mobile/e2e/journey.spec.ts`. The browser journey exercises request, resend-control behavior, file-mail confirmation, and disabling alerts. Synthetic screenshots: [confirmation pending](Q22-email-confirmation-pending.png) and [disabled](Q22-email-disabled.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q22-AC01 | PASS | `notificationPreferences.test.tsx`: failed lookup yields `value: null` and `loadFailed`; retry loads the authoritative enabled value. UI renders no toggle until `value` exists. |
| Q22-AC02 | PASS | Unit test verifies failed update preserves the confirmed off value and sets `updateFailed`, then a retry yields confirmation pending distinctly. Browser journey confirms pending, confirms from file mail, and disables. |
| Q22-AC03 | PASS | Per-user keyed component disposal plus controller epoch fencing. Unit tests verify delayed load and update results do not publish after disposal/account switch, including dispose/reactivate behavior under React StrictMode. |

## Verification

| Actual command and working directory | Exit code | Result | Evidence path |
| --- | ---: | --- | --- |
| `npm run typecheck` from `apps/mobile` with Node 24.6.0 | 0 | Passed | — |
| `npm run test:unit -- tests/notificationPreferences.test.tsx` from `apps/mobile` with Node 24.6.0 | 0 | 5 tests passed | — |
| `VERIFY_RUN_ID=q22-final-20261117-1815 npm run test:e2e -- journey.spec.ts` from `apps/mobile` with Node 24.6.0 and `.venv` activated | 0 | 2 tests passed (desktop/mobile) | `.local/verification/T18/q22-final-20261117-1815/` |

The Q22 follow-up resets internal loading/busy flags on controller disposal without publishing to an unmounted view. This allows React StrictMode's second effect setup to start a fresh load; the focused unit test and typecheck were rerun.

Evidence recorded 2026-11-17. The browser journey uses isolated local services and file mail only. The backend rate limits confirmation resends to one per 60 seconds; within that window the resend action correctly remains confirmation-pending and sends no duplicate. The test verifies this behavior and confirms with the existing file-mail link. No external email or provider delivery was used.

## Compatibility and review

No API, schema, configuration, or dependency changes. Existing email notification endpoints and confirmation-token flow are unchanged. The device alert toggle is intentionally left for Q23. Final integration review is pending.

## Remaining work

None for local Q22 acceptance. Parent integration review remains pending.
