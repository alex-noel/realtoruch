# Two-week implementation plan: 12–25 November 2026

Prepared 11 November 2026 for `realtoruch`, against commit `ae893a6` on `codex/krakow-rental-journey`.

This is a delegation-ready plan, not a record of newly implemented features. It contains **36 task prompts, 217 numbered acceptance criteria and 222 Given/When/Then test cases**. Each task is written as a user instruction and includes scope, technical requirements, dependencies, file ownership, acceptance tests, verification commands and handoff requirements.

Start with the **26 core tasks**. They strengthen the existing rental journey, collection, storage and operational evidence. Four tasks depend on external access or devices. Six larger tasks are fully specified as a ready reserve and are not promised within this sprint.

## How to use this pack

1. Read [delegation and integration rules](DELEGATION.md) and [shared product/technical contracts](CONTRACTS.md).
2. Give one worker the **entire linked task file**, its assigned worktree, and the reviewed prerequisite commits. Do not send only a title or AC list.
3. Require the [handoff template](HANDOFF_TEMPLATE.md), current test evidence and AC-by-AC status. Do not accept “implemented” as proof that an external service worked.
4. Use [manifest.json](manifest.json) for programmatic dispatch and [AC–test matrix](AC_TEST_MATRIX.md) for coverage review.
5. Run `python3 docs/plans/2026-11-12-two-week-sprint/validate_plan.py` after editing this pack.

No workers have been launched by creating this plan. No application code, external accounts or cloud resources are changed by the plan.

## Starting evidence and gaps

These are observations from the checked-out repository and its recorded verification. **Application tests and live collection were not rerun while writing this plan.**

| Area | Existing evidence at the baseline | What the sprint must establish |
| --- | --- | --- |
| Rental journey | Polygon/filter search, saved searches, seen/favorites, same-price suppression, price-drop inbox/email queue and retained delisted favorites already exist | Repeatable real-service and browser regression coverage; concurrency safety |
| Sources | Recorded live samples from Otodom, Gratka and Morizon; an OLX parser plus one manual import | Parser-drift contracts, durable fetching budgets, multi-day evidence; actual OLX access is a separate gate |
| Live sample | Recorded 66 canonical homes, 89 source advertisements and 112 observations | Larger isolated benchmark; counts are historical observations, not a current catalog guarantee |
| Automatic OLX | Baseline automatic requests return 403 | Configurable onboarding, then a bounded live check only if access is available |
| Backend checks | Previous verification recorded 132 tests, including 5 real PostgreSQL/Elasticsearch checks | Current branch evidence with required service tests unable to silently skip |
| Frontend | Web and iOS/Android JS exports; recorded main web JS around 597 kB | Browser automation, accessibility/performance evidence, then installed native testing when devices/toolchains exist |
| Email | Local SMTP/file transport and queue behavior | Fenced delivery races, then actual designated-inbox reception if configured |
| Accounts/owner platform | Auth, publishing, moderation and private messages already implemented | Session recovery, precise unread cursors, account erasure races and bounded own-data export |
| Operations | Short collection runs, local SQLite/PostgreSQL restore checks and a small load sample | >=72-hour soak, representative-scale load, lifecycle-aware restore, observability and CI configuration |
| Infrastructure | Terraform/Helm/Compose/Dataflow configuration | Config validation and service-permission alignment only; no deployment |

See the existing [feature ledger](../../feature-status.md), [verification record](../../verification.md), [architecture](../../architecture.md) and [source notes](../../source-connectors.md). The baseline commit was already pushed before this planning request; older “nothing pushed” wording in historical docs is not a description of current Git state.

## Scope and success

The primary outcome is a **locally verified release candidate** for the requested Kraków journey:

- Choose a drawn area, apartment rent **below 5,000 PLN**, area **at least 50 m²**, and direct offers.
- Save the search and opt into email; existing matches form a silent baseline.
- Receive one logical new-match alert for a genuinely new qualifying canonical property.
- Opening a property marks it seen; a same-price repost stays quiet.
- Favorite a property; receive a lower-price alert when it drops below the tracked favorite price floor.
- Keep a delisted favorite in the saved list while excluding it from discovery and map pins.

Base rent, monthly fees, agency/direct status and known zero commission are independent concepts. The precise shared contract and canonical test sequence are in [CONTRACTS.md](CONTRACTS.md).

**Excluded from this sprint's execution:** cloud provisioning/deployment (the previously excluded step 7), paid resources, production DNS changes, app-store publication, automatic account creation, unsolicited external messages and Git pushes. Infrastructure files and local validation remain in scope. A single-zone configuration or laptop load test does not establish a production uptime guarantee.

“All features of Otodom” remains a larger product program. Sales/commercial/new-development products, billing/promotions, CRM integrations, commute layers, editorial/financing, comprehensive geographic coverage and staffed fraud operations are not implicitly added to these two weeks.

## Capacity and confidence

Assumption: **four implementation workers plus one integrator/reviewer**, ten workdays, six productive hours per worker per day.

| Allocation | Hours | Meaning |
| --- | ---: | --- |
| Core task estimates | 175 | 26 bounded implementation/verification tasks, including T32's final integration work |
| Protected buffer | 48 | Fixes, rebases, failed checks, underestimated concurrency work and integration |
| Available conditional capacity | 17 | Use only if external inputs are ready and the core remains on track |
| Total worker capacity | 240 | 4 × 10 × 6 |
| Conditional catalog | 20 | All four external tasks cannot fit while retaining the full buffer |
| Stretch catalog | 50 | Six ready specifications; unallocated, beyond the base commitment |
| Additional integrator/reviewer | 30–40 | Contract decisions, branch review, sensitive-change review and evidence acceptance; not counted as a fifth implementation lane |

These are **engineering effort estimates, not model token/runtime estimates or a delivery guarantee**. No model pricing is assumed. Parallel agents do not remove database/UI integration dependencies. Reserve the stronger reviewer for identity, concurrency, auth, erasure and infrastructure boundaries; smaller workers can handle bounded implementation and test tasks.

T07 also needs at least **72 hours of real elapsed time**. Start its bounded run in week one. Never compress simulated time and present it as a multi-day live run.

## Proposed workday schedule

A/B/C/D are worker slots, not four agents that should edit the same checkout. Task estimates may cross days. Exact nonoverlapping hour slots and dependency checks are recorded in the manifest.

| Day | Date | A | B | C | D | Integrator focus |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | Thu 12 Nov | T01 isolated verification | T05 parser contracts | T09 dedupe evaluation | Available buffer; inspect external prerequisites | Agree contracts, task worktrees, migration registry, evidence format |
| D2 | Fri 13 Nov | T02 CI | T03 collector fencing | T08 revisioned indexing | T13 delivery fencing | Review test harness and lock/claim designs |
| D3 | Mon 16 Nov | T14 session resilience | Finish T03; start T04 | Finish T08; start T10 | Finish T13; T06 source preflight | Accept versioning/fencing contracts; resolve shared-model edits |
| D4 | Tue 17 Nov | T18 browser journey | Finish T04; start T07 soak; start T19 | Finish T10 | T21 native links | Pin soak revision/config; review identity correction |
| D5 | Wed 18 Nov | Finish T18; start T16 | Finish T19; start T26 | T11 history/storage | T15 account lifecycle | Review auth/erasure and precise read-cursor contracts |
| D6 | Thu 19 Nov | Finish T16; start T12 | Finish T26; soak monitoring | Finish T11; start T27 | Finish T15; start T17 | Public/private DTO, grants and migration integration |
| D7 | Fri 20 Nov | Finish T12; start T25 | Finish T07 live report after >=72 h | Finish T27; start T28 | Finish T17; start T20 | Week-one evidence checkpoint; verify external inputs |
| D8 | Mon 23 Nov | Finish T25; regression buffer | Conditional T30/T29 if inputs ready; otherwise fixes | Finish T28; review/buffer | Finish T20; conditional T22 if ready | Freeze features; select at most 17 h of gated work |
| D9 | Tue 24 Nov | Start T32 final candidate | Gated checks or correctness fixes | Gated T31/OLX checks or fixes | Finish chosen native checks; fixes | Independent sensitive-change review and AC audit |
| D10 | Wed 25 Nov | Finish T32 and focused retests | Fix/retest only | Fix/retest only | Fix/retest only | Publish local readiness report in repository; no push/deploy |

Do not assign every conditional task automatically. Prefer T30 (6 h) and T22 (6 h) if prerequisites are ready, leaving at most 5 h for T29 (4 h) **or** T31 (4 h). If prerequisites are blocked, retain the capacity for core fixes. No answer or elapsed time counts as an approval for external sending.

The schedule assumes immediate dependency review at handoff. A delay on T01 → T08 → T10 → T11 → T12 → T25 → T32 is critical. Protect this chain before starting stretch work. T17/T19/T18 converge into T20; T15/T26 converge into T28. Shared-file merge locks are described in [DELEGATION.md](DELEGATION.md).

## Core task prompts

| Task | User instruction / outcome | Priority | Estimate | Dependencies | Planned worker |
| --- | --- | --- | ---: | --- | --- |
| [T01](tasks/T01-isolated-verification.md) | Make verification reproducible and isolated for parallel workers | P0 | 6 h | — | A |
| [T02](tasks/T02-ci-quality-gates.md) | Add CI gates for Python, TypeScript, builds and isolated service tests | P0 | 6 h | T01 | A |
| [T03](tasks/T03-collector-leases.md) | Fence collector ownership and keep leases alive during slow or empty runs | P0 | 8 h | T01 | B |
| [T04](tasks/T04-conditional-fetching.md) | Reduce download volume with conditional requests and bounded retries | P1 | 6 h | T03 | B |
| [T05](tasks/T05-parser-contracts.md) | Expand portal contract fixtures and detect markup drift | P0 | 6 h | — | B |
| [T06](tasks/T06-olx-onboarding.md) | Prepare a configurable OLX feed/access preflight | P1 | 4 h | T05 | D |
| [T07](tasks/T07-collection-soak.md) | Run and report a bounded 72-hour collection soak | P0 | 6 h | T03, T04, T05 | B |
| [T08](tasks/T08-versioned-search-index.md) | Make search indexing monotonic, batched and safe under retries | P0 | 10 h | T01 | C |
| [T09](tasks/T09-dedupe-evaluation.md) | Create a labelled duplicate-identity evaluation dataset | P0 | 6 h | — | C |
| [T10](tasks/T10-identity-correctness.md) | Fix duplicate identity errors and concurrent correction races | P0 | 8 h | T08, T09 | C |
| [T11](tasks/T11-history-storage.md) | Bound historical-rent queries and preserve their methodology | P1 | 8 h | T10 | C |
| [T12](tasks/T12-public-search-contract.md) | Harden public API/search contracts and fallback behavior | P1 | 6 h | T08, T11 | A |
| [T13](tasks/T13-delivery-fencing.md) | Make email, push and account-job delivery safe under concurrent workers | P0 | 8 h | T01 | D |
| [T14](tasks/T14-session-resilience.md) | Preserve safe sign-in behavior across tabs, offline periods and revocation | P0 | 6 h | T01 | A |
| [T15](tasks/T15-account-data-lifecycle.md) | Prevent account-data resurrection and add a scoped data export | P0 | 8 h | T10, T13, T14 | D |
| [T16](tasks/T16-message-read-cursors.md) | Use message high-water marks for read state and stable inbox pagination | P1 | 6 h | T10 | A |
| [T17](tasks/T17-inbox-client.md) | Finish reliable inbox polling, pagination and user feedback | P1 | 5 h | T14, T16 | D |
| [T18](tasks/T18-browser-regression-suite.md) | Automate the eight-step rental journey and account/owner browser regressions | P0 | 8 h | T01, T14, T02 | A |
| [T19](tasks/T19-source-status-and-request-lifecycle.md) | Show collection freshness and prevent stale browser/mobile requests | P1 | 6 h | T03, T14 | B |
| [T20](tasks/T20-web-accessibility-and-performance.md) | Make the web experience accessible, responsive and measurably fast | P1 | 8 h | T17, T19, T18 | D |
| [T21](tasks/T21-native-links-and-lifecycle.md) | Handle native deep links and account lifecycle across app restarts | P1 | 6 h | T14 | D |
| [T25](tasks/T25-load-and-query-budgets.md) | Measure and optimize search, ingestion and storage at a representative local scale | P1 | 8 h | T08, T11, T12 | A |
| [T26](tasks/T26-operational-metrics-and-runbooks.md) | Expose bounded operational metrics and actionable local incident runbooks | P1 | 6 h | T03, T08, T13 | B |
| [T27](tasks/T27-restore-and-erasure-recovery.md) | Prove backup restoration preserves rental state and resumes account erasure safely | P1 | 6 h | T11, T15 | C |
| [T28](tasks/T28-infrastructure-config-alignment.md) | Align Terraform, Helm and service permissions with the verified application | P1 | 6 h | T02, T08, T13, T15, T26 | C |
| [T32](tasks/T32-integrated-release-candidate.md) | Integrate the sprint and produce a truthful local release-candidate report | P0 | 8 h | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T25, T26, T27, T28 | A |

## Conditional task prompts

These are complete instructions, but external acceptance cannot proceed on fabricated credentials or substitute mock results.

| Task | User instruction / outcome | Priority | Estimate | Dependencies | Assignment |
| --- | --- | --- | ---: | --- | --- |
| [T22](tasks/T22-installed-mobile-acceptance.md) | Verify the complete rental journey in installed iOS and Android apps | P0 | 6 h | T17, T18, T21 | UNALLOCATED |
| [T29](tasks/T29-olx-live-access-validation.md) | Validate an actually available OLX access path without bypassing access controls | P1 | 4 h | T06, T07 | UNALLOCATED |
| [T30](tasks/T30-real-email-delivery-acceptance.md) | Verify real email delivery and suppression with an explicitly authorized test inbox | P0 | 6 h | T13, T14, T18 | UNALLOCATED |
| [T31](tasks/T31-map-provider-acceptance.md) | Validate configured map tiles, attribution and restricted mobile credentials | P1 | 4 h | T20, T21 | UNALLOCATED |

## Ready reserve / stretch prompts

Select these only if the core is already accepted and the integrator explicitly trades remaining capacity. T23 + T24 form an 18-hour dependency chain, so they are unlikely to fit late in this sprint. Otherwise carry these specifications into the next sprint unchanged or rebase them against the new baseline.

| Task | User instruction / outcome | Priority | Estimate | Dependencies | Assignment |
| --- | --- | --- | ---: | --- | --- |
| [T23](tasks/T23-owned-media-storage.md) | Add private, validated image uploads for owner advertisements | P2 | 10 h | T15, T08 | UNALLOCATED |
| [T24](tasks/T24-owner-photo-uploader.md) | Build the cross-platform owner photo upload and ordering flow | P2 | 8 h | T23, T17 | UNALLOCATED |
| [T33](tasks/T33-location-provenance-and-enrichment.md) | Track location precision and add an opt-in bounded geocoding adapter | P2 | 8 h | T05, T12 | UNALLOCATED |
| [T34](tasks/T34-photo-similarity-evaluation.md) | Evaluate photo similarity as review evidence without changing automatic identity | P2 | 8 h | T09 | UNALLOCATED |
| [T35](tasks/T35-phone-fingerprint-key-lifecycle.md) | Define and test phone fingerprint key rotation and retention | P2 | 8 h | T15, T26 | UNALLOCATED |
| [T36](tasks/T36-opt-in-message-email.md) | Add a separate opt-in email category for unread private messages | P2 | 8 h | T13, T16, T17, T21 | UNALLOCATED |

## External input gates

- **G01 — User/provider:** A usable authorized OLX portal/feed access path; credentials privately if required; documented scope for a tiny validation sample. **Fallback:** T06 offline readiness and truthful blocked status; OLX remains disabled for automatic collection.
- **G02 — User/sender-domain owner:** Selected SMTP provider, sender identity/domain, local secret configuration, a designated authorized test inbox and explicit permission for the named test sends. **Fallback:** Local file transport and preview tests; actual inbox delivery remains unverified.
- **G03 — User/device/toolchain owner:** Full compatible Xcode and Android SDK, available simulator/emulator/devices, map configuration and any required signing identity. **Fallback:** Native JS exports and adapter tests; do not claim installed iOS/Android acceptance.
- **G04 — Integrator/local runner owner:** An available local machine/runner that can stay awake with network for >=72 hours, sufficient disk, and the already-authorized bounded collection configuration. **Fallback:** Complete resumable harness/failure drills; mark live soak incomplete and local operational release partial.
- **G05 — User/map account owner:** An already selected permitted map/tile provider, allowed web/app identifiers and a restricted client map key where required. **Fallback:** Fixture map tests and usable list fallback; provider acceptance remains unverified.
- **G06 — User/geocoder account owner:** A permitted geocoding provider with documented budget, attribution/access scope and privately configured credentials if needed. **Fallback:** Disabled-by-default adapter and local fixtures; no public bulk geocoding.
- **G07 — User/repository maintainer:** A later explicit instruction to push the reviewed workflow/code and permission/access to observe hosted CI. **Fallback:** Static workflow review plus all equivalent local commands; no hosted run URL/result is invented.

Request missing inputs early through the integrator, but continue independent local work. Do not ask for secrets in a task report or commit. T02's hosted CI result and T33/T36's optional live portions are separate from their offline implementation status.

## Acceptance and release classification

Every AC has a unique ID and at least one mapped test. **PLANNED** is the initial status for all tasks. Worker statements must distinguish implementation, local tests, real-service checks and real external behavior.

- **VERIFIED task:** all applicable criteria pass with current evidence. A failed numeric target remains failed; reporting it does not waive it.
- **IMPLEMENTED_LOCAL task:** code and local checks exist, but named required integration/external ACs remain unverified.
- **BLOCKED_EXTERNAL task:** exact missing input prevents a required check; record completed independent work and who can supply the input.
- **FAILED_REVIEW task:** a correctness/privacy/data-loss issue or unsupported claim must be fixed before acceptance.

T32 can report **LOCAL_VERIFIED** only when the complete core is accepted and its required evidence is current/compatible. Report **LOCAL_PARTIAL** if a core target, mandatory service check or live duration is missing. Report **EXTERNAL_BLOCKED** alongside either local status when hosted CI, real email, installed mobile, maps or OLX remain unverified. Any unresolved P0 identity/privacy/data-loss/notification regression is **NO_GO**.

Even LOCAL_VERIFIED is **not** production deployment approval, a verified SLA, complete portal coverage, real-inbox acceptance, or installed-device acceptance. Do not label the product release-ready for those uses until the corresponding gates are actually verified and deployment is separately authorized.

## Evidence and version discipline

Use real wall-clock times in reports and fixtures. Only Git author/committer dates are backdated through the required helper. A test performed in November 2026 must not be described as a 2021 verification.

Keep per-run artifacts under ignored `.local/verification/<task>/<run-id>/`. Commit sanitized aggregate reports only. Record commit, schema/config hashes, tool versions, commands, exit codes, test counts (including skips), and links from every AC to evidence.

The soak runs on a pinned collector revision. Later behavior changes require relevant revalidation and an explicit compatibility assessment; if they invalidate the long-run evidence, restart the relevant run or mark the live-duration gate incomplete. Never claim the final candidate itself ran for 72 hours unless it did.

The final handoff is [T32](tasks/T32-integrated-release-candidate.md): a current feature ledger, precise remaining blockers and reviewable deployment prerequisites, with no cloud actions or push.
