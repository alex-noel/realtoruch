# Q27 rental desk handoff

Status: IMPLEMENTED_LOCAL; standard review pending. Base: e50735d; branch: codex/q27-rental-desk. Evidence collected 2026-11-17 Europe/Warsaw using isolated synthetic fixtures.

The rental desk retains its existing behavior; the three owner and moderation components now live in separate modules. `MarketplaceDialog.tsx` owns mode switching, shared `run`/`busy` and errors, message teardown and parent close. `AdvertDesk.tsx` owns profile, advert listing, appeal and editor selection; `AdvertEditor.tsx` owns draft, location and photo-link editing; `ReviewDesk.tsx` owns reports, identity review and decisions. These correspond directly to the former same-named functions; `emptyProfile` moved with the desk and `emptyDraft` with the editor. This map also identifies where to integrate the concurrent legacy media uploader: the existing photo links and draft save remain in `AdvertEditor` and the save API call remains in `AdvertDesk`.

`RentalDeskWork` defines the shell's shared `run` and `busy` interface. `AdvertDeskProps`, `AdvertEditorProps` and `ReviewDeskProps` are exported. `registerExitGuard` is an optional, currently unused registration extension passed from desk to editor; it has no effect on closing or draft state. A later unified dirty/exit task must define and wire actual registration, cleanup and navigation behavior across the shell and messages before relying on it.

| Acceptance | Evidence |
| --- | --- |
| Q27-AC01 | Move-oriented extraction; owner browser flow passed on desktop and mobile, including publish, edit, messages and withdrawal. Moderation logic moved unchanged; no dedicated moderation browser case was run. |
| Q27-AC02 | Separate modules and exported interfaces above; shell remains shared ownership. |
| Q27-AC03 | Web export emitted a separate MarketplaceDialog chunk; owner browser tests and messages unit tests passed. |

| Command (working directory) | Result |
| --- | --- |
| `npm run typecheck` (`apps/mobile`) | exit 0 |
| `npm run test:unit -- tests/messages.test.tsx` (`apps/mobile`) | exit 0; 12 passed |
| `VERIFY_RUN_ID=q27-owner-20261117-1516 npm run test:e2e -- owner.spec.ts` (`apps/mobile`, checkout venv activated) | exit 0; desktop and mobile passed, 2 total; private harness data in `.local/verification/T18/q27-owner-20261117-1516` |
| `git diff --check` (checkout root) | exit 0 |

The initial browser attempt was blocked by sandbox loopback binding; the isolated run above succeeded with elevated local permissions. No API, schema, dependencies or lockfile changed. Private message and account boundaries remain in the unchanged shell and messages component. No external checks were requested or run. Standard review remains outstanding.
