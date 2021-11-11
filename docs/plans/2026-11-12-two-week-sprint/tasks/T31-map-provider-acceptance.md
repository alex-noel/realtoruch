# T31 — Validate configured map tiles, attribution and restricted mobile credentials

**User instruction:** I want maps to work reliably in the browser and installed apps with an explicitly configured provider, correct attribution and usable fallback behavior.

| Field | Instruction |
| --- | --- |
| Tier / priority | CONDITIONAL / P1 |
| Active effort estimate | 4 hours |
| Proposed window | D8–D10 (2026-11-23–2026-11-25) |
| Worker slot | UNALLOCATED |
| Dependencies | [T20](T20-web-accessibility-and-performance.md), [T21](T21-native-links-and-lifecycle.md) |
| Required review | standard |
| External gates | G05 |
| Shared merge/contract locks | native-config, map-components |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The baseline map UI works locally, but production provider configuration and Android map credentials remain external inputs. This task validates an existing selected provider; it does not choose or purchase one.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T31/<run-id>/`; commit sanitized reports only.

## Read first

- `apps/mobile/src/components/PropertyMap.tsx`
- `apps/mobile/src/components/PropertyMap.web.tsx`
- `apps/mobile/app.config.js`
- `apps/mobile/.env.example`
- `docs/mobile-validation.md (from T21)`
- `docs/deployment.md`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/components/PropertyMap.tsx (provider/config fixes only)`
- `apps/mobile/src/components/PropertyMap.web.tsx (provider/config fixes only)`
- `apps/mobile/app.config.js`
- `apps/mobile/.env.example`
- `docs/verification/maps.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Require G05: chosen permitted tile/map provider, allowed web origins/app identifiers, any client-intended restricted key and its usage scope. Check current primary provider documentation for attribution and restrictions; do not recommend a paid provider or alter accounts during this task.

2. Validate web tile URL construction and native provider configuration against the app's documented environment variables. Client-visible restricted map keys are distinct from server credentials; never bundle service-account/private keys.

3. Render required attribution and retain it in narrow layouts. Do not prefetch bulk tile regions or build offline caches against a public/community server without a permitted provider contract. Keep test requests to a short interactive session.

4. Confirm the Kraków polygon, pin selection and map/list synchronization, coordinate order and bounds. Preserve source precision labels; a city-centroid or approximate point must not be described as an exact apartment address.

5. Simulate denied key, exhausted quota, unavailable tiles and offline mode. Show a concise error/retry state and keep list/filter/favorite access working. Avoid retry storms and ensure repeated map mount/unmount releases listeners.

6. Record platform/provider/version/origin tested and actual network results without unrestricted credentials. Installed-device evidence must come from T22 or a real run here; web rendering and JS exports alone do not prove native maps.

## Acceptance criteria

- **T31-AC01:** Provider configuration and allowed use are explicit with required attribution.

- **T31-AC02:** Only client-intended restricted credentials appear in the frontend; private keys remain absent.

- **T31-AC03:** Kraków polygon and selected pins agree with list/filter results.

- **T31-AC04:** Approximate coordinates are labelled accurately.

- **T31-AC05:** Provider failures retain usable listing discovery and bounded retry behavior.

- **T31-AC06:** Evidence identifies tested platforms and blocked native/provider checks honestly.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T31-TC01 — covers T31-AC01, T31-AC02

**Given:** Configured provider and restricted test app/origin.

**When:** Inspect config and render a short session.

**Then:** Tiles load within allowed scope and attribution is visible; no private credential is bundled.

### T31-TC02 — covers T31-AC03

**Given:** Known synthetic coordinates and polygon vertices around Kraków.

**When:** Select pins, draw/edit and compare results.

**Then:** Map and list agree with backend longitude/latitude semantics.

### T31-TC03 — covers T31-AC04

**Given:** Exact, district-centroid and unknown coordinate fixtures.

**When:** Open map/detail.

**Then:** Location labels reflect known precision without inventing exact addresses.

### T31-TC04 — covers T31-AC05

**Given:** 403/429/timeout/offline tile failures.

**When:** Retry once and navigate to list/favorites.

**Then:** App remains usable, explains failure and avoids uncontrolled repeated requests.

### T31-TC05 — covers T31-AC05

**Given:** Repeated map mount/unmount.

**When:** Inspect subscriptions/request counts.

**Then:** Listeners and obsolete requests are cleaned up.

### T31-TC06 — covers T31-AC06

**Given:** Only web access or missing Android configuration.

**When:** Complete report.

**Then:** Native/provider checks are not-run/blocked rather than passed.


## Verification commands and checks

- `cd apps/mobile && npm run typecheck`
- `make verify-web`
- Run bounded provider/map validation and T22 native checks if available

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Configured-provider acceptance report and targeted fixes
- Documented attribution, failure behavior and environment inputs
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not buy map service, change provider accounts or perform bulk tile downloads.
- Do not publish server-side credentials in app configuration.
