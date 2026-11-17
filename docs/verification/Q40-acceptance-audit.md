# Q40 acceptance coverage audit and real owner appeal

Reviewed all forty task packets (120 acceptance criteria), current handoffs and their browser/unit/backend coverage on 17 November 2026. Coverage review is separate from final integrated acceptance: Q22/Q23/Q37 and the final Q39/Q40 profiles were still in progress during the audit.

Two concrete missing local paths were found:

1. Q19-AC01 named Warszawa, but the complete guest continuation journey exercised Kraków only. Follow-up `630718e` adds a separate exact-city/polygon/name/persisted-filter case; it passes desktop/mobile and leaves the existing silent-baseline renter journey intact.
2. Q40-AC01 included owner appeal end to end. Q35 had mocked UI tests plus real API/backend tests, but the real owner browser journey stopped after withdrawal. This commit extends that real journey through actual appeal submission and a fresh owner-list API read proving persisted pending status.

The existing isolated fixture helper gains only a fixed `hide-owner` operation. Its existing production prohibition, run-token, exact SQLite URL and owned-run-directory checks remain mandatory. It accepts only the existing browser profile allowlist, resolves the fixed synthetic `owner-<profile>@example.test` account, and requires exactly one withdrawn advert with a listing. It marks that listing hidden to supply the review condition. It adds no application endpoint, moderator capability, configurable arbitrary mutation or production access.

The browser retains its full real create/validate/save/preview/publish/conflict/message/read/withdraw journey. After the fixture hides the withdrawn home, it refreshes the actual owner dashboard, checks publishing is unavailable, opens the named appeal, submits to the real API and requires201, named success and pending state. A further actual GET must return `hidden: true` and `appeal_status: pending`; repeat appeal is absent before and after refresh. Existing failure injections in the earlier publish/update flow remain intact; appeal, owner projection, identity/session and messages are not mocked.

## Actual verification

Source: 630718e plus this test/helper-only addition. Node24.6.0, Python3.12.9, macOS arm64. Run completed on17 November2026 around16:14UTC.

- From `apps/mobile`, `VERIFY_RUN_ID=q40-real-appeal-02 npm run test:e2e -- owner.spec.ts --grep 'owner publishes'`: **2 passed,0 failed,0 skipped**, desktop12.3s/mobile9.1s,22.1s suite. The tagged owner scenario also remains included in Q39's final WebKit/Firefox smoke.
- `npm run typecheck --prefix apps/mobile`: passed.
- Python AST parsing of `apps/mobile/e2e/fixture.py`: passed.
- `git diff --check`: passed.

The first attempt failed2/2 because its new assertion used shortened text rather than the dashboard's actual hidden-state copy. The corrected assertion passed; no product change or requirement relaxation was needed. Raw run evidence remains ignored under `.local/verification/T18/q40-real-appeal-02`; no trace, mail, account storage or database is committed.

## Audit limits and remaining gates

No further concrete missing local criterion was identified. In particular, Q32/Q33 include actual SQLite/PostgreSQL migration, lifecycle and restricted-role cases; Q26 checks real JSON bytes and backend export authorization; Q38 combines controlled UI decision faults with actual ordinary-user denial and unchanged backend identity-review regressions. Native picker/share/platform mappings use adapters and explicitly reserve installed-device behavior for external acceptance, as their packets require. These are not device passes.

Historical Q18 evidence used Node23; final Node24 full profiles must supply current acceptance. Final integrated offline/services/web counts, all Q39 visual/browser results, entry/warm budgets and native JavaScript exports remain the integrator's Q40 work. This audit makes no final forty-task pass claim. No external messages, collection, provider calls, deployment or push occurred.
