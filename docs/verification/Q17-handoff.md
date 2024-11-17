# Q17 Readable rent history

Status **IMPLEMENTED_LOCAL**, with local checks passing and integrator review pending.

Base revision `15c9d37` on `codex/q12-gallery` includes the gallery work. Q17 changes the detail history section independently of the gallery.

## Result

Rent insights show a readable chart at phone widths, with two to five date ticks, a period summary, sample notices and the complete textual monthly rows. Period change compares the first and latest observed sample medians when there are two or more months. The chart leaves gaps between missing months. Listing details label the eight-observation limit and show Polish local dates in a consistent day-month-year format.

`Insights.tsx` owns the chart and district selection. `Dialogs.tsx` changes the rent history section, and `accessibility.spec.ts` holds the deterministic fixtures. The 320 px screenshots show [the original chart](../previews/quality/q17-before.png) and [the responsive chart](../previews/quality/q17-after.png).

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| Q17-AC01 | PASS | At 320 and 1440 px the test checks a 24-month trend, a flat line at 0.0%, no observations, and a one-month chart with one plotted value and no period change. It checks two or five date labels in bounds with no overlap and all 24 textual rows. |
| Q17-AC02 | PASS | The test checks the illustrative and small-sample notices, period summary, labelled observed-median change and retained methodology. |
| Q17-AC03 | PASS | A 12-observation fixture shows the latest eight with explicit truncation and representative date and PLN formatting. Switching from a Kraków district to Warszawa requests whole-city history and selects Whole city. |

## Verification

Commands ran in `apps/mobile` on 17 November 2026 around 15:42–15:44 CET. Node 24.6.0 and the checkout's Python 3.12.9 virtual environment were on `PATH`. Browser checks used Playwright 1.65.0 and Chromium Headless Shell 158.0.8127.18 with synthetic fixtures and disposable loopback services.

| Command | Exit | Result | Run ID |
| --- | ---: | --- | --- |
| `npm run typecheck` | 0 | Passed | |
| `npm run test:e2e -- accessibility.spec.ts -g 'Q11\|Q12\|Q17\|TC02'` | 0 | 8 passed across desktop and mobile, 0 skipped | `q17-history-20261117-01` |
| `npm run test:e2e -- accessibility.spec.ts --project=mobile -g 'Q17 rent history'` | 1 | Expected baseline failure. The old chart omitted the 24-month period summary. | `q17-history-baseline-20261117-01` |

## Compatibility and review

The chart retains the existing history API, client request fencing, and server methodology text. The detail view shows the most recent eight loaded observations. The implementation uses the existing chart dependency. Installed iOS and Android rendering was outside the browser checks. Integrator review remains pending.
