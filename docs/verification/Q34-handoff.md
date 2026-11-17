# Q34 — Owned photo picker and upload queue

Status: IMPLEMENTED_LOCAL; strong media/session and native-dependency review pending. Base efa23970f22ac7e630577c1e1ce89ecb2703aa2f. Picker, queue and scoped binary transport are adapted from the reviewed main-root implementation at 4cb5503; the editor, Q29 guard, Q30 choices and Q31 previews were integrated rather than replaced. Q26's exact export-purpose 401 handling and session fencing remain in the shared request helper. Media remains disabled by default outside run-owned fixtures.

The editor accepts owned JPEG/PNG/WebP selection, validates local bounds, limits active transfers to three, exposes per-photo retry/cancel, reorder and descriptions, and displays the first eligible cover while preserving legacy links. Saving is blocked while any selected photo is unresolved or the combined cap is exceeded; selected IDs are checked ready again before the advert write. Queue changes participate in the unified dirty guard. Photo description and removal operations follow a successful advert write; failed finalization retains editor state for retry. Conflict choices display both ordered photo sets and do not cancel or detach local photos before a confirmed write. Published-edit and draft-publication previews fetch owner-authorized thumbnails and descriptions, and publication is blocked while saved photos cannot be verified.

| Criterion | Evidence |
| --- | --- |
| Q34-AC01 | Local browser uploads two generated images, reorders at 320 px, checks saved IDs in order, preview cover/alt text and publication. A held upload disables saving; selected candidate status is rechecked before write. |
| Q34-AC02 | Focused tests exercise native permission denial, invalid files, timeout/retry with stable key, cancellation and ignored late response; real-browser test injects upload failure and a 409 while preserving text and local photos. |
| Q34-AC03 | Browser keyboard picker/reorder and resource cleanup pass on desktop and 320 px; adapter tests cover preview URL/temp-file disposal and account-generation fences. Installed device picker/permission acceptance remains external. |

Actual evidence date: 17 November 2026 CET. Python 3.12.9, Node 24.6.0. Synthetic generated photos and run-owned loopback services; no external provider or real images.

| Command | Result |
| --- | --- |
| `npm --prefix apps/mobile run test:unit` | 230 passed, 16 files; includes upload queue/adapters, binary refresh/account fencing, Q26 export/session regression. |
| `npm --prefix apps/mobile run typecheck`; `git diff --check` | exit 0. |
| `VERIFY_RUN_ID=q34-final-20261117 npm --prefix apps/mobile run test:e2e -- owner-upload.spec.ts owner-guard.spec.ts owner-conflict.spec.ts owner-preview.spec.ts` | 8 passed desktop/mobile after finalization/guard changes. |
| `VERIFY_RUN_ID=q34-final2-20261117 npm --prefix apps/mobile run test:e2e -- owner-upload.spec.ts` | 2 passed desktop/mobile after adding ordered conflict-photo previews. |
| `EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 CI=true expo export --platform ios --platform android --output-dir ../../.local/verification/Q34/native-final2-20261117` | Both iOS and Android Hermes JavaScript bundles built; no installed-device or live push/provider claim. |

The first uploader browser run exposed duplicate web image roles; removal of the redundant role yielded one labelled image and the rerun passed. One early guard run showed generic feedback replacing the underlying save error; the final combined run passes after preserving it. A synthetic 320 px preview screenshot was visually inspected in ignored `.local/verification/T18/q34-upload-20261117b/`. The per-run browser harness now enables private local media under its disposable run directory. A network failure during discard may leave an unattached server asset for the existing 24-hour orphan cleanup; no discarded ID is attached to an advert.

The only package declaration added is `expo-image-picker` 58.0.10 plus its Expo permission plugin. The integrator owns merging and recalculating `package-lock.json` alongside Q26's already-integrated file-system/sharing dependencies; no install was run through the shared symlink. Backend/schema, actual bucket/provider, and original 011 migration are unchanged. The API transport change and MarketplaceDialog guard-busy extension are narrow scope expansions needed for binary media and safe finalization; independent review is required before merge.
