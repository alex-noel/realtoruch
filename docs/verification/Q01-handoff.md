# Q01 shared controls

Implemented and locally reviewed on 2026-11-17. Shared scales keep the existing visual identity. Button supports primary, secondary, danger and quiet variants, busy labels, disabled progress, hover and press feedback. Legacy outline calls work. Buttons and chips have 44px targets. Usage is in `docs/contracts/ui.md`.

Validation: Node 24 typecheck; 2 button SSR cases using actual React Native Web; 4 field and 9 collection tests. Accessibility run `q01-controls-20261117-01`: 8/8 Chromium desktop/mobile checks, including 320/390/768/1440 widths, 200% text, focus trapping, keyboard polygon and monochrome contrast. Explicit web aria-busy was added after SSR detected RN Web drops the native state prop; rerun button tests and typecheck passed. A follow-up two-case responsive run `q01-controls-baseline-20261117` actually used the final controls (the attempted baseline copy used the wrong directory); do not describe that run as a baseline.

Actual baseline `q01-before-20261117` used HEAD shared controls and passed 2/2. Matching 320/1440 screenshots are in `docs/previews/quality/q01-before-*.png` and `q01-after-*.png`; parent inspected the 320 pair and 1440 after. Larger chip targets add modest height. The fixture's asynchronous demo badge differs between captures; this is not a design change. New visual baseline coverage in Q39 must wait for that state.

No installed-device or spoken assistive-technology test is claimed. Browser busy behavior is represented by a disabled native button and aria-busy; action-specific pending races are owned by later tasks.
