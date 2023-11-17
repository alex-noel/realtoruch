# Q01 Unify visual tokens and control states

Status: **PLANNED** · Priority: **P2** · Active effort: **2–3 hours**

Executor: **economy** · Review: **standard**

Dependencies: **None** · Merge locks: **shared-ui**

When delegated, read [DELEGATION.md](../DELEGATION.md) and this packet. Work from reviewed dependencies in an isolated checkout. This is a plan, not a report of completed implementation. Use [HANDOFF_TEMPLATE.md](../HANDOFF_TEMPLATE.md) for the result.

## Problem and evidence

- [apps/mobile/src/theme.ts](../../../../apps/mobile/src/theme.ts): A small palette exists, but spacing, type sizes and interaction styling are repeated inline.
- [apps/mobile/src/components/UI.tsx](../../../../apps/mobile/src/components/UI.tsx): Buttons have pressed opacity but no common loading or destructive variant.

## Change

Keep the existing green, cream and square-corner identity. Define a small spacing/type scale and shared button variants, including visible busy, disabled, hover and focus states. Publish usage examples for later screen tasks; migrate only shared primitives here.

## File scope

- `apps/mobile/src/theme.ts`
- `apps/mobile/src/components/UI.tsx`
- `apps/mobile/src/web.css`

New paths are proposed outputs; dependency paths must be read after their producer is reviewed. Existing shared files are limited to the named feature. Add focused tests where needed; coordinate lockfile/schema changes through the integrator.

## Acceptance

- **Q01-AC01:** Existing consumers render without signature breakage; busy buttons announce progress and cannot submit twice.
- **Q01-AC02:** Primary, secondary and destructive actions remain distinguishable without color alone, with at least 44 CSS px target boxes for shared controls.
- **Q01-AC03:** Review representative controls at 320 and 1440 px and 200% text; existing focus and contrast checks pass.

## Verification

- npm run typecheck
- Existing accessibility.spec.ts checks plus before/after control screenshots.

Frontend npm commands run from `apps/mobile`; Make and Python commands run from the checkout root. Use the isolated browser/service harness described in [DELEGATION.md](../DELEGATION.md). New tests are requirements to implement, not commands already known to pass.

## Exclusions

No new brand, font download, design-system dependency or whole-app style rewrite.
