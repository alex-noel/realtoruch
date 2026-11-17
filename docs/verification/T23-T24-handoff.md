# Owner photo uploads — T23 and T24

- Status: **VERIFIED for the specified local implementation**; real GCS and installed-device acceptance remain separate gates.
- Base: `9147daf80f57d0071f77f9dfde73118a9de6411f`. Integrated application: `a7d550c16b359576e8ea3de2a5ff6d0f74d84efb`.
- Verification: **17 November 2026**, Europe/Warsaw; exact UTC profile intervals are in [the aggregate evidence](T23-T24-evidence.json).
- Outcome: an owner can select photos on web or through the native adapter, preview, describe, upload, reorder, remove, save and reopen them, and resolve an advert conflict explicitly. Published cards use thumbnails; larger images load on demand.
- The user selected these stretch tasks on 17 November. Integration also covered local launch/storage configuration, scoped binary transport and CORS, account erasure, API-role grants, deployment configuration and verification isolation. No cloud deployment or new source push was authorized for this batch.

## Implementation and compatibility

`media.py` and `media_storage.py` provide verified-account management, opaque IDs, stable upload keys, cancellation before the response arrives, and authenticated draft previews. Only ready assets belonging to the advert owner can attach. External HTTPS image links remain supported; the combined cap is 30, with linked images followed by ordered owned IDs. [Exact endpoint and state contract](../contracts/media.md).

JPEG, PNG and WebP uploads are capped at 10 MiB, 20 million decoded pixels and 32,768 pixels on either side. The streamed body is bounded even without Content-Length, and a 30-second read deadline starts when the request acquires the processing slot. Content and declared MIME must agree. Animation, oversized dimensions and unsafe content are rejected. Orientation is applied, metadata is stripped, and only JPEG display/thumbnail derivatives are stored. Public reads check current publication and listing visibility; private previews use the owner's authorization. No arbitrary remote URL fetch is added.

Local objects use 0700 directories, 0600 files and descriptor-relative no-follow access. One upload body/decode is processed per API process. Two concurrent generated 20 MP decodes peaked at 876.6 MiB in a fresh macOS process, exceeding the chart's 768 MiB limit. One EXIF-rotated decode peaked at 522.2 MiB, produced a 2048×1638 display image and removed EXIF. These are local process samples, not an API pod capacity guarantee.

Account closure and deleted asset state commit before external storage cleanup. GCS permanent deletion installs empty generation-fenced markers, preventing delayed create-only writes from restoring photo bytes. Temporary deletes also name the observed generation, preventing a delayed delete from removing a newer retry. Unconfirmed cleanup remains retryable; successful erasure removes the scrubbed SQL cleanup rows. Open-account deletion preserves its upload-key tombstone and stops repeated storage calls once cleanup is confirmed. The dedicated bucket must preserve live fence markers. Real IAM, provider timeouts, versions, backups and bucket lifecycle policies remain deployment checks.

Rental migration **011** adds media assets; fresh and tracked-baseline SQLite/PostgreSQL upgrades preserve previous rows and applied checksums. No other migration was added, and reserved versions 012–014 remain available. Apply the registry and `grants.sql` before enabling uploads. The actual restricted API role performs upload, attachment, publication and erasure in the service tests; unrelated SQL roles cannot read the media table.

The frontend uses pinned Expo 58 picker/filesystem packages on native and an owned web file input. The web input avoids the SDK web adapter's unreleased object URLs and all-or-nothing mixed-file rejection. At most three uploads run from the client; retries keep the same bytes/key. Only ready IDs are saved. Save failures and session refresh preserve edits. A stale advert version offers explicit reload or merge; attachment deletions and description writes follow a successful advert save. Descriptions are independent per-asset, last-write-wins metadata, not part of the advert's atomic version check.

The launcher separates demo/live/journey storage; Compose persists API and cleanup-worker objects in one named volume. Test media uses private run directories. The optional Helm cleanup job is disabled by default, uses the API identity and private SQL/HTTPS egress, and has no public Service. Production uploads stay disabled until private GCS and a reachable HTTPS API origin are configured. No bucket, IAM grant or deployment was created.

## Acceptance evidence

All cases below pass for local/fake-provider/adapter scope. The native adapter tests and JS exports do not substitute for an installed mobile device.

| AC | Result | Required cases and evidence |
| --- | --- | --- |
| T23-AC01 | PASS | T23-TC01: verified-account guard, foreign asset rejection, actual API-role route lifecycle; media and service suites. |
| T23-AC02 | PASS | T23-TC02 and TC03: generated JPEG/PNG/WebP with GPS/orientation, both derivatives, MIME mismatch, animation, byte/stream and dimension limits. |
| T23-AC03 | PASS | T23-TC01 and TC04: pending/foreign/31-image rejection without version change; ready ordered attachment, publish/withdraw and fake storage routes. |
| T23-AC04 | PASS | T23-TC04: private local adapter and fake GCS contract through management/attachment paths; no cloud credentials. |
| T23-AC05 | PASS | T23-TC05 and TC06: idempotent keys, competing payloads, 25-hour orphan cleanup, paused decode versus cancellation/erasure, storage failures, delayed remote write/delete fakes. |
| T23-AC06 | PASS | T23-TC02 and TC06: stripped metadata, private draft/public visibility, opaque DTOs, account fence and removal; local filesystem path guards. |
| T24-AC01 | PASS | T24-TC01: actual web input; mocked native permission denial/retry and valid/invalid file handling. |
| T24-AC02 | PASS | T24-TC02: six deterministic transfers capped at three, stable-key retry, cancellation before ID/late response; real browser/API cancellation and refresh. |
| T24-AC03 | PASS | T24-TC03: ready-only ordered save, partial-draft explanation, combined 30-photo cap, detach before delete; saved/reopened browser state. |
| T24-AC04 | PASS | T24-TC04 and TC05: 401 followed by real auth refresh, transient failure/retry, reopen, real second-session 409, explicit merge without early mutations. |
| T24-AC05 | PASS | T24-TC06: 320 px labelled keyboard controls, object URL and input/listener cleanup, discarded late previews, mocked native temporary-file deletion. |
| T24-AC06 | PASS locally | T24-TC01–TC06: nine focused adapter/queue tests and desktop/responsive real-browser photo flows with generated PNGs; both native JS exports. |

## Executed verification

Repository-root commands used Python 3.12.9, Node 24.6.0 and macOS 15.7.7 arm64. The service runner used disposable PostgreSQL 16.15 and Elasticsearch 8.19.6 and removed its labelled containers. Set Node 24 on PATH and use the original Playwright browser cache, as in the commands below.

```sh
PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH .venv/bin/python scripts/verify.py offline --run-id nov17-media-offline2
PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH .venv/bin/python scripts/verify.py services --run-id nov17-media-services1
PATH=/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/Users/alexnoel/Library/Caches/ms-playwright .venv/bin/python scripts/verify.py web --run-id nov17-media-web1
PATH=/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin:/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/Users/alexnoel/Library/Caches/ms-playwright VERIFY_RUN_ID=nov17-owner-photos-final .venv/bin/python apps/mobile/e2e/run.py owner-photos.spec.ts
```

| Check | Result |
| --- | --- |
| Offline profile, final application | 420 passed, 0 failed, 133 explicit service/tooling skips; TypeScript and all 131 frontend unit tests passed. |
| Real service profile, final application | 275 passed, 0 failed, 0 skipped; includes current migration, actual-role, account, restore, identity, index and photo tests. |
| Complete browser suite | 38 passed, 0 failed, 0 skipped on `e00d7a2`; frontend is unchanged in final `a7d550c`. |
| Final photo browser rerun | 2 passed, 0 failed, 0 skipped on `a7d550c`, after the storage-fencing follow-up. |
| Native exports | Android and iOS Hermes bundles exported successfully on `a7d550c`; no installed app/device. |
| Configuration | Compose config, Helm lint and enabled cleanup render checks passed. Two Helm diagnostics tests passed with an explicit local Helm binary. No Terraform change/apply. |
| Runtime dependency audit | OSV Scanner 2.7.1 passed against last pushed `3bbe7b4`: zero new advisories/high/critical blockers; two existing moderate npm advisories remain. Locks are unchanged after audit candidate `e00d7a2`. |

Both committed dependency locks installed successfully; Python `pip check` passed. Native exports ran from `apps/mobile` with `EXPO_OFFLINE=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DOTENV=1 CI=true ./node_modules/.bin/expo export --platform ios --platform android --output-dir ../../.local/verification/T24/nov17-native-final`, using Node 24.6.0. Fatal Python lint, whitespace, plan validation and the CI change-boundary check also passed.

The first offline run had one failure because an older cursor migration test assumed 010 was the last possible added hook. Its retained-row/checksum assertions remain, and the hook assertion now permits additive migrations. The first photo browser run reached the final thumbnail assertion but expected the non-demo caption; its fixtures use DEMO_MODE, so the assertion now retains the existing illustrative-image disclosure. Both corrections passed subsequent profiles. Private raw fixtures, mail, databases and traces remain ignored; the committed aggregate contains no advert content or credentials.

## Reproduction, recovery and open gates

Run `make dev`, register/verify through the local file mail sink, open **My adverts**, create a profile and draft, and choose generated JPEG/PNG/WebP photos. Reorder ready photos, save, reopen and publish. Use a second session to edit the same version to exercise reload/merge. Withdrawal removes public photo access; account erasure removes local derivatives and fences late writes in the fake GCS tests.

Independent review covered storage ownership, metadata, cancellation/erasure races, GCS generations, migration ordering, restricted roles, UI/session cleanup and optimistic conflicts. Review corrections are included; no unresolved correctness blocker remains in those reviewed paths. Keep API endpoints and storage available if reverting only the frontend. Preserve migration 011 and restore database plus matching object storage together; an old database-only restore cannot reconstruct photos or deletion fences.

Physical iOS/Android picker/session/map checks need installed builds and a device or simulator. Production GCS needs a private bucket, validated IAM and lifecycle/backup policy plus live provider tests. Actual email delivery still needs the selected sender/provider. None is substituted by local mocks or exports.

Separate collection work reported the stopped original soak honestly and verified one current-pin cycle: Otodom, Gratka and Morizon each ingested two adverts with four requests and no errors, producing four canonical homes from six source adverts. The 72-hour gate remains incomplete; OLX remains disabled. [Exact collection evidence and wrapper cleanup limitation](collection-soak.md).

No new source push, cloud provisioning, app publication or external email was performed. The bounded named collection smoke is the only portal traffic in this continuation.
