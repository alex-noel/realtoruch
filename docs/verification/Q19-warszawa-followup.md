# Q19 Warszawa continuation follow-up

The Q40 acceptance audit found that the existing complete renter journey tested guest save continuation only in Kraków. This additional real local-API regression covers Q19-AC01's explicit Warszawa case without replacing the original silent-baseline and deletion journey.

The guest changes city to Warszawa, selects Direct offers, enters three exact polygon vertices through the keyboard-accessible coordinate panel and starts saving. Registration returns to the naming draft with a Warszawa-derived name. The test checks the exact polygon string and city in the submitted filters, then verifies the server-returned and reload-persisted filters/name and exactly one write/record. Every browser request is constrained to the run-owned loopback ports or local data/blob URLs.

Actual validation on 17 November 2026, Node 24.6.0 and Python 3.12.9:

- From `apps/mobile`, `VERIFY_RUN_ID=q19-warszawa-audit-02 npm run test:e2e -- journey.spec.ts --grep 'Q19 guest Warszawa'`: **2 passed, 0 failed, 0 skipped** (desktop and mobile), 3.7 seconds.
- `npm run typecheck --prefix apps/mobile`: passed.
- `git diff --check`: passed.

The initial attempt ran before the test file was written due to an incorrect working-directory path and reported no tests; it is not acceptance evidence. The successful run used application source at 579baa8 plus this test-only addition. Raw run data stays ignored under `.local/verification/T18/q19-warszawa-audit-02`. No product code or external services changed. Final integrated profiles remain Q40 work.
