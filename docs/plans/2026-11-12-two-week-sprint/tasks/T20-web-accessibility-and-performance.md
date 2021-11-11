# T20 — Make the web experience accessible, responsive and measurably fast

**User instruction:** I want the rental app to remain simple, square and fast while being usable with a keyboard, screen reader, narrow screen and enlarged text.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 8 hours |
| Proposed window | D7–D8 (2026-11-20–2026-11-23) |
| Worker slot | D |
| Dependencies | [T17](T17-inbox-client.md), [T19](T19-source-status-and-request-lifecycle.md), [T18](T18-browser-regression-suite.md) |
| Required review | standard |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | root-ui, shared-ui, frontend-dependencies |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The recorded web export has an approximately 597 kB main JS file plus lazy Leaflet and marketplace chunks. That historical size is a starting observation, not a fresh performance benchmark. The shared app already has working dialogs and maps.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T20/<run-id>/`; commit sanitized reports only.

## Read first

- `apps/mobile/src/web.css`
- `apps/mobile/src/theme.ts`
- `apps/mobile/src/components/UI.tsx`
- `apps/mobile/src/components/Dialogs.tsx`
- `apps/mobile/src/components/MapDrawing.tsx`
- `apps/mobile/src/components/PropertyMap.web.tsx`
- `apps/mobile/src/components/MarketplaceDialog.tsx`
- `apps/mobile/e2e/* (from T18)`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `apps/mobile/src/web.css`
- `apps/mobile/src/components/UI.tsx`
- `apps/mobile/src/components/Dialogs.tsx`
- `apps/mobile/src/components/MapDrawing.tsx`
- `apps/mobile/src/components/ListingCard.tsx`
- `apps/mobile/src/components/MarketplaceDialog.tsx (targeted accessibility changes)`
- `apps/mobile/e2e/accessibility.spec.ts (new)`
- `scripts/web_budget.py (new)`
- `docs/performance/web-baseline.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Audit search, listing details, account, favorites, notifications, owner publishing and messages at viewport widths 320, 390, 768 and 1440 px. Prevent horizontal document overflow and inaccessible actions. Keep right-angle corners and existing restrained style; do not redesign the product or introduce a component framework.

2. Implement dialog semantics, initial focus, focus containment on web, Escape close and focus restoration. Native platform behavior must remain valid; gate DOM APIs to web. Use labels for inputs and icon buttons, visible keyboard focus, logical tab order and live announcements for meaningful asynchronous outcomes.

3. Provide a keyboard-accessible polygon editor using the existing vertex model: add/edit/remove latitude-longitude vertices, finish/clear area and announce validation errors. Preserve graphical drawing. Validate WGS84 ranges, at least three distinct vertices and existing polygon complexity/geometry rules.

4. Make status, agency/direct, commission-unknown and seen/favorite meaning understandable without color alone. Meet WCAG AA text contrast targets in the tested UI and support 200% text zoom without hiding essential actions. Document observed audit coverage instead of claiming certification.

5. Use lazy loading for map/dialog code already separated and defer offscreen images with explicit dimensions, appropriate thumbnails and accessible alternative text. Keep the production main JS bundle <=650,000 uncompressed bytes, measured by a script that identifies the actual entry bundle rather than summing every lazy chunk.

6. Record a repeatable synthetic benchmark on a declared machine/browser with a 100-result local fixture: cold load under a documented throttling profile, warm filter/apply and dialog-open interaction p95 <=200 ms over 30 actions. If hardware/profile prevents the target, report measured failure and cause rather than changing the target silently. Do not remove functionality or disable accessibility to meet budgets.

## Acceptance criteria

- **T20-AC01:** All listed screens are usable at the four widths and 200% text zoom with no hidden essential actions.

- **T20-AC02:** Dialogs and primary flows work entirely by keyboard with correct focus behavior.

- **T20-AC03:** A user can create, adjust and clear a polygon without pointer input.

- **T20-AC04:** Critical labels/contrast/state distinctions pass the scoped automated and manual audit.

- **T20-AC05:** The main JS bundle stays within the declared size budget and map/marketplace remain lazy.

- **T20-AC06:** A reproducible performance report includes raw measurements, hardware/profile, p95 and explicit target results.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T20-TC01 — covers T20-AC01

**Given:** Each listed screen at four widths and 200% text zoom.

**When:** Open all primary dialogs and validation states.

**Then:** No document overflow or unreachable submit/close action appears.

### T20-TC02 — covers T20-AC02

**Given:** Focus on a listing card action.

**When:** Open dialog, tab through it, press Escape.

**Then:** Focus stays within dialog until close and returns to the initiating control.

### T20-TC03 — covers T20-AC03

**Given:** Keyboard-only user with a blank area.

**When:** Add three valid vertices, edit one, finish and clear.

**Then:** Results follow the same polygon contract as graphical drawing; invalid coordinates show labelled errors.

### T20-TC04 — covers T20-AC04

**Given:** Direct/agency/unknown commission and seen/favorite states.

**When:** Inspect accessible tree, contrast and monochrome rendering.

**Then:** State meanings remain discoverable without color or unlabeled icons.

### T20-TC05 — covers T20-AC05

**Given:** Production web export.

**When:** Run bundle budget script and inspect chunk loading.

**Then:** Entry JS <=650,000 bytes; unopened map/dialog chunks are not counted as eagerly loaded code.

### T20-TC06 — covers T20-AC06

**Given:** Fixed 100-result fixture and recorded browser/hardware profile.

**When:** Run 30 warm interactions and cold-load samples.

**Then:** Report reproduces p95, declares pass/fail, and includes no fabricated global performance score.


## Verification commands and checks

- `cd apps/mobile && npm run typecheck && npm run build:web`
- `python3 scripts/web_budget.py (new)`
- `make verify-web`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Targeted UI/accessibility changes
- Viewport/focus tests and measured web performance report
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not rewrite App.tsx wholesale or replace React Native Web with a second frontend.
- Do not claim an accessibility certification or production capacity from local measurements.
