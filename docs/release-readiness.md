# Local release readiness — 17 November 2026

**LOCAL_PARTIAL.** The latest app-quality application is `803ad02752fbf98457e6c59494b546c93998a0e7`. All 40 implementations are integrated locally. Final TypeScript, 273 unit tests and the web export passed; full combined browser/native/performance acceptance remains partial. Workers and database-heavy verification were stopped at the user's request. [Current quality handoff](verification/Q40-quality-handoff.md) records exact evidence and limits. Nothing was pushed or deployed.

## Historical photo continuation

**LOCAL_PARTIAL.** The earlier photo candidate was `a7d550c16b359576e8ea3de2a5ff6d0f74d84efb` on `codex/core-sprint-2026-11`. Owner photo uploads now pass local backend, browser and native-adapter/export checks. The 72-hour collection gate, installed mobile and production operations remain open. This continuation is committed locally and has not been pushed or deployed.

## Photo continuation checks

| Check | Result and scope |
| --- | --- |
| Offline Python | 420 passed, 0 failed, 133 explicit service/tooling skips on the final application. |
| PostgreSQL and Elasticsearch | 275 passed, 0 failed, 0 skipped; includes photo migration, restricted API-role lifecycle, metadata, ownership and deletion races. Owned containers were removed. |
| Frontend | Strict TypeScript and 131 unit tests passed. Complete desktop/responsive browser suite: 38 passed without skips on `e00d7a2`; its frontend is identical to the final application. The two photo flows also passed on the final backend. |
| Native | Final iOS and Android Hermes/JavaScript exports passed. Native picker/permission/cache adapters have unit coverage; physical-device behavior remains unverified. |
| Storage/configuration | Private local derivatives, fake GCS generation fences, per-catalog/test isolation, persistent Compose volume and optional disabled cleanup CronJob. Compose/Helm checks and two Helm diagnostic tests passed. No cloud resources created. |
| Dependency audit | Locked installs and `pip check` passed. OSV found no new advisories; two pre-existing moderate npm advisories remain. |
| Collection smoke | One 42.7-second current-parser cycle successfully ingested two adverts each from Otodom, Gratka and Morizon, producing four canonical homes. This does not complete 72-hour acceptance. |

[T23/T24 handoff and every AC/test case](verification/T23-T24-handoff.md) and [exact profile evidence](verification/T23-T24-evidence.json) record the dates, revisions, corrected initial failures and external limits. Migration 011 and revised API grants are required before enabling owner uploads. GCS markers must survive lifecycle rules; bucket versions/backups need deployment-specific handling. Photo descriptions remain independent last-write-wins metadata, while advert text and photo order use optimistic versioning.

## Earlier core baseline

The following core evidence records the 12 November candidate `a17cf16f4e6c3c33d629684fd6a75685eb147b53` and its specified compatible revisions. It is retained as historical evidence, not a new hosted CI result for the photo continuation.

Reviewed source was pushed to GitHub with the user's explicit authorization. No cloud resource, container registry image, deployed website, signed mobile app, or external email was created by this integration.

## Core baseline checks

| Check | Result and scope |
| --- | --- |
| Offline Python | 392 passed, 0 failed, 115 explicit real-service cases skipped; those dependencies are required in the separate service profile. |
| PostgreSQL and Elasticsearch | 240 passed, 0 failed, 0 skipped; fresh and upgrade migrations, real roles, leases, index versions, identity and delivery races, account erasure, paired restore and replay. |
| Frontend | Strict TypeScript and 122 unit tests passed. Production web export and all 36 desktop/responsive Chromium cases passed without skips. |
| Hosted CI | [All four jobs passed](https://github.com/alex-noel/realtoruch/actions/runs/43119698856) on `d56ae2313f34c574877e16050ea3affd67b064b6`, including locked fresh installs, runtime dependency audit and Android/iOS JavaScript exports. Only the grant/test/documentation follow-up differs from the candidate; the full current service profile verifies it. Native bundles are not installed-device tests. [Latest branch runs](https://github.com/alex-noel/realtoruch/actions/workflows/ci.yml?query=branch%3Acodex%2Fcore-sprint-2026-11). |
| Configuration | 13 commands passed: Compose 10 services/three loopback bindings; Terraform 1.9.8 with cached Google/google-beta 6.50.0 providers and disabled backend; Helm 3.16.4 lint/render with collector off/on (40/41 objects). No plan/apply. |
| Index convergence | 100 changed homes converged in 0.431287 seconds in the documented four-CPU/eight-GiB container budget. [Profile and one-sample limits](performance/index-convergence.md). |
| Capacity | Native PostgreSQL, 10,000 homes/100,000 observations/2,000 searches, 20 clients, 300.13 seconds: 64,154 HTTP 200s; p95 SQL 66.7–68.4 ms, ES REST 115.6–118.9 ms, history 452.6 ms; sampled API RSS below 137 MiB. Earlier emulated history target failed. [Full comparison](performance/catalog-load.md). |
| Deduplication | Frozen 220 synthetic pairs: 80/80 known positives, 0/100 false-positive merges, 0/40 ambiguous merges. Formal report is one call per partition; automated regression tests also reuse the corpus, so this is not an untouched statistical holdout or a live accuracy estimate. [Report](verification/dedupe-final.json). |

Local profiles ran on macOS 15.7.7 arm64, Python 3.12.9 and Node 24.6.0. Service tests used disposable PostgreSQL 16.15 and Elasticsearch 8.19.6; the cached Alpine PostgreSQL image is amd64 under emulation, while the capacity acceptance used a separate native ARM64 PostgreSQL image. Every service container created by the verification runner was removed after checking ownership. The configuration run used a credential-free copied directory; a preliminary Terraform version probe refreshed a public release-check cache, not a cloud project.

The profiles ran between `2026-11-11T23:21:48.648195+00:00` and `2026-11-11T23:34:38.737368+00:00`. Offline and browser profiles used `d56ae2313f34c574877e16050ea3affd67b064b6`; the final service profile used `a17cf16f4e6c3c33d629684fd6a75685eb147b53`. Backend application and frontend files are byte-identical between these revisions; the later grant/test/documentation change is not silently presented as an earlier test result. Exact per-profile timestamps, counts, runtime and compatible earlier benchmark/config revisions are recorded in [T32 evidence](verification/T32-evidence.json). The subsequent documentation commit does not change the tested application.

## User journeys and review corrections

The browser suite covers Kraków with a drawn polygon, base rent strictly below 5,000 PLN, at least 50 m² and declared private advertisers. Known zero commission remains a separate filter; unknown fees do not become zero. Existing matches form a silent saved-search baseline. New matches alert once, opening marks the canonical home seen, and same-price reposts stay quiet. A lower-price relist of a saved home creates one logical price-drop alert. Delisted favorites remain visible while discovery excludes them. Two-account publishing, messages, viewport read cursors, session recovery, link handling and erasure also pass using synthetic accounts and file mail.

Independent review found and reproduced two P1 defects, both corrected before this candidate:

- Moderator-hidden homes could be retrieved or newly saved through Favorites. Both canonical and alias saves now return 404; hidden entries are omitted while their saved rows remain for restoration. Ordinary delisted homes remain accessible and removable.
- Identity corrections could turn an old title edit or later restore into a false price drop. Merge now evaluates at most 100 pending events for the original cards using their original user state, then silently baselines corrected prices and visible search matches. Favorite floors never rise. Split applies the same baseline to both resulting homes, including stored hidden/inactive prices. Genuine already-related pending drops survive; newly linked historical prices do not create retroactive favorite relationships. A backlog or incomplete drain returns recoverable 409 and rolls back notifications, deliveries, floors and identity changes. Newly generated same-user/same-price cross-kind duplicates coalesce; historical notifications remain intact.

The integrator reviewed the changes and a separate worker reproduced merge, split, hidden-restore and partial-drain cases. The restricted API role also needed INSERT on notifications and push deliveries for this new merge path. An actual-role regression reproduced each missing privilege independently, then verified one genuine drop with one email and push queue record; auth/indexer/Dataflow insert denials remain enforced. Existing deployments must reapply the reviewed grants before updating the API. The review also covered account closure/erasure, delivery fencing, index acknowledgements, public DTOs and incoming-link guards. No unresolved P0/P1 was found in the reviewed paths. This is bounded code review and test evidence, not a security certification.

## Open gates and next actions

| Gate | Current evidence | Smallest next action / owner |
| --- | --- | --- |
| T07 duration and provider coverage | The original `b3782cc` manifest stopped recording at `2026-11-12T05:54:21.566956Z`: 30,403.246314 covered seconds, two eligible cycles, ten unobserved slots. Its target elapsed without enough coverage; Gratka failed both discovery attempts. No live removal observed. | A new reviewed pin and a host available for the full 72 hours are needed. Preserve the original evidence; elapsed time alone is insufficient. [Current report](verification/collection-soak.md). |
| Current-parser collection | A separate one-cycle smoke on `9147daf` passed for Otodom, Gratka and Morizon, with four HTTP attempts and two ingested adverts each. Six source adverts deduplicated to four homes. The wrapper's redundant cleanup errored after saving the cycle; a process check confirmed the scheduler exited. | Keep this bounded sample separate from long-run acceptance. The corrected Gratka parser has live success; sustained availability and live removal remain open. |
| OLX | Configurable feed/HTML connectors and offline access checks exist; automatic HTTP collection remains disabled after 403. | Supply an approved feed or permitted automated access. No account/session bypass was created. |
| External email and push | File mail, local SMTP protocol, cancellation/retry and receipt tests pass. | Supply sender/provider credentials and an explicitly designated test recipient/device, then validate actual delivery. SMTP acceptance with lost acknowledgement can duplicate physical mail. |
| Installed mobile and map/domain inputs | Web and native JS exports pass. | Supply platform build/signing tools, device/simulator, restricted Android map key and HTTPS association domain; execute installed cold/warm-link and map checks. |
| Cloud and operations | Terraform/Helm/Compose and representative SQL roles pass locally. No infrastructure is deployed. | Separately review project/quotas/cost, secrets, IAM/network enforcement, authenticated metrics scraper, TLS/CDN behavior, backups/PITR and deployment approval. Single-zone/single-node configuration does not establish a 95% uptime SLA. |
| Repository policy | Earlier core hosted checks passed after the authorized push. The 17 November photo continuation has local verification and has not been pushed. | Push only when requested; hosted checks must run for the new revision after a push. No default-branch merge or policy change was performed. |

Capacity timings apply to the recorded six-route mix and machine and do not include the new photo decoder workload. A separate all-history saturation diagnostic exceeded 750 ms; no production capacity or SLA is inferred. Restore evidence uses paired, quiesced local snapshots, not Cloud SQL PITR; restoring uploaded media also requires matching object storage. Full-market coverage, verified owner identity, staffed fraud review, portable photo export, commercial/sales categories and complete Otodom parity remain separate product work.

## Acceptance traceability

The [core acceptance index](verification/core-acceptance.json) records all 157 ACs and 162 test cases across the 26 core tasks, with task-specific evidence and scope limits. T07-AC02 and T07-AC03 remain INCOMPLETE. T32 records that incompleteness rather than converting it into operational acceptance. The user selected T23/T24 on 17 November; their additional 12 ACs and 12 required cases are recorded separately in the [photo handoff](verification/T23-T24-handoff.md). Other stretch tasks remain outside this continuation. See the historical [T32 handoff](verification/T32-handoff.md), current [feature ledger](feature-status.md) and [deployment prerequisites](deployment.md).
