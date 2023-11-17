# Q03 Actionable API errors

Implemented in the integration checkout. Independent Terra high-reasoning review approved the final change after its fallback issue was corrected.

Known route/status/detail combinations now produce typed recovery codes and fixed safe text for conflicts, verification, cooldowns, limits, blocked conversations and review states. Validation fields are allowlisted and bounded. Unknown errors do not echo server input or credential strings. Session refresh, cancellation and account fencing remain unchanged.

| Criterion | Evidence |
| --- | --- |
| Q03-AC01 | Twelve mapped API response cases plus unmatched route/status cases in session.test.ts. |
| Q03-AC02 | Unknown string/object/HTML/credential and validation-array fixtures verify bounded text and fields. |
| Q03-AC03 | Full session suite passes, including refresh races, replay/logout and account changes; business errors preserve active session and token. |

Validation: npm run test:unit -- tests/session.test.ts: exit0,39passed,0failed/0skipped. npm run typecheck: exit0. Commands run from apps/mobile, Node24.6.0, macOS arm64. No backend/schema/dependency changes.

The first targeted run found one existing race-test synchronization flaw: setToken left initial state signed-out, so polling signed-out could release the blocked write before confirmed logout. The test now subscribes and waits for the new logout publication. This retains the controlled ordering; application logout code was not changed. The corrected run passed.

Private raw output is not committed. No external operation ran. Export purpose-token semantics remain Q26 scope.

Evidence time: 2026-11-17T15:20:13+01:00
