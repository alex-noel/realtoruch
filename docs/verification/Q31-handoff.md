# Q31 — Review before publishing

Status: IMPLEMENTED_LOCAL; standard review pending. Base Q30 commit 52adfa8 (Q29 and Q30 separately reviewed/integrated). A saved draft opens a read-only review before publication; editing a published advert and reconciling a published conflict also require a review before the explicit apply action. The review uses the exact normalized candidate or saved advert, shows address/coordinates, base rent, known or unknown fees and other charges, amenities and photo links. Returning to edit preserves the draft. Verification guidance points to Account and preserves the saved draft. Published edits cannot use the guard's Save and leave to bypass review.

| Criterion | Evidence |
| --- | --- |
| Q31-AC01 | Synthetic browser asserts preview causes no publish/update request, returning to edit retains rent, and the confirmed request contains the reviewed rent. Unknown fees and photo link appear in the unverified preview. |
| Q31-AC02 | Unverified account sees Account verification guidance and disabled Publish; test returns to Account and reopens the saved draft without publication. |
| Q31-AC03 | Verified browser injects a publish failure and retries; published edit injects a version conflict, reconciles, and requires a second explicit preview confirmation before saving. Draft/preview remains recoverable on errors. |

Actual evidence date: 17 November 2026 CET. Python 3.12.9, Node 24.6.0; synthetic accounts and isolated local services.

| Command | Result |
| --- | --- |
| `VERIFY_RUN_ID=q31-preview-final-20261117 npm --prefix apps/mobile run test:e2e -- owner-preview.spec.ts owner.spec.ts --grep 'unverified owner\|owner publishes'` | 4 passed, desktop/mobile. |
| `VERIFY_RUN_ID=q31-interaction-20261117 npm --prefix apps/mobile run test:e2e -- owner-guard.spec.ts owner-conflict.spec.ts` | 4 passed, desktop/mobile. |
| `npm --prefix apps/mobile run test:unit -- tests/ownerValidation.test.ts tests/ownerGuardNative.test.tsx tests/session.test.ts` | 64 passed. |
| `npm --prefix apps/mobile run typecheck`; `git diff --check` | exit 0. |

Ignored browser artifacts are under `.local/verification/T18/` with the run IDs above. The first preview run used a selector that also matched the new success message; the corrected tests passed. A final local refresh-error message adjustment was typechecked after browser runs. No screenshots were captured. The listing address and coordinates are explicitly disclosed as included; unknown optional costs are not represented as zero. The verification path uses the existing Account screen and does not send mail automatically. No schema, backend or dependency changes and no external action.
