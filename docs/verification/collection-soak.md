# T07 collection soak

The runner schedules 12 six-hour slots starting at a saved UTC timestamp. Each
slot has a 10-minute admission window. It writes the slot ID before starting any
requests, keeps a 60-second heartbeat, and accounts for an expired admission
window as missed. A restart never replays an interrupted slot: completed worker
checkpoints are recovered from the private catalog, and unknown counts remain
unknown. A restart or a heartbeat gap over 120 seconds subtracts the unobserved
period from runner coverage. Shorter pauses are below the detection threshold.
The horizon is fixed at 72 hours. Any detected runner gap leaves fewer than 72
hours of runner coverage and therefore an incomplete run even when the wall
clock reaches the horizon. The runner neither fills missed slots nor silently
extends the schedule. A recorded request-budget violation stops collection
across restarts, including when recovered from the last worker result.

The original soak pin is `b3782cca0f4a05b788e4fd00656ef01327deb552`. The SHA-256 of
`config/sources.live.json` is
`1340806cbb1e8e552a6ca9fac26a27835814e45ee68caa3f163b935a4f20fba3`.
Only Kraków and Otodom, Gratka and Morizon are included. Each provider may check
one discovery page, two new details and four stored adverts due for recheck in a
slot. Each allowed origin gets one logical robots check; a timeout or other
failure that exhausts that check stops the provider for that cycle. The total
ceiling is 18 HTTP attempts per provider per slot, including up to four robots
attempts and nine retries (one retry per logical request). Configured starts are
at least 10 seconds apart; robots directives and durable backoff may impose
longer waits. OLX remains disabled. Due known URLs found during discovery wait
for a due recheck slot; previously inactive URLs are outside this sample's
recheck population. This is a bounded sample of listings.

An eligible interval has a known disposition for every provider and at least one
provider attempt. An all-deferred interval and an interval interrupted with
unknown results are accounted for separately. Provider success fractions use
all accounted intervals, including failures, deferrals and misses. A successful
real check requires a successful provider run with at least one ingested
observation. Byte totals count response bodies consumed by the connector,
excluding headers and protocol overhead. A history change count can include the
initial observation and changes to other fields; observed rent changes and
transitions to inactive are counted separately. Queue snapshots are counts of
pending work in SQLite; the live soak does not run delivery or index workers.

The reporter caps wall elapsed time at the fixed horizon. It reports saved
runner coverage, recorded gaps and the unobserved tail after the last heartbeat.
A heartbeat older than 120 seconds before the horizon checkpoint is stale.
Expired slots still marked pending in the manifest appear as unobserved in the
report and stay outside the accounted-interval denominator. Only the runner
records missed slots on a later checkpoint. Reporting reads only the manifest.

## Original live soak

Run `krakow-72h-20261111` started at **2026-11-11 21:27:38.320642 UTC**.
Its last heartbeat was **2026-11-12 05:54:21.566956 UTC**, before the fixed
target end of **2026-11-14 21:27:38.320642 UTC**. The 17 November read-only
report recorded **30,403.246314 seconds** (8 hours 27 minutes) covered and
**228,796.753686 seconds** (63 hours 33 minutes) unobserved.
The stale manifest has **2 of 12 eligible cycles**, 10 unobserved intervals,
and zero recorded gaps, misses, deferrals or interruptions. Both completed
cycles ended in under 42 seconds. The live result is **INCOMPLETE**.

| Provider | Cycle results | Discovery parsed | New details checked / ingested | Due rechecks | HTTP attempts (robots / retry) | Body bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Otodom | Two successes | 2 | 4 / 4 | 0 | 8 (2 / 0) | 4,242,383 |
| Gratka | Two discovery `unrecognized_page` failures | 0 | 0 / 0 | 0 | 4 (2 / 0) | 1,986,866 |
| Morizon | Two successes | 2 | 4 / 4 | 0 | 8 (2 / 0) | 4,457,534 |

The isolated SQLite catalog used migrations 001, 005, 006 and 008. From an
empty baseline it grew to eight homes, eight source adverts, eight initial
history rows and eight event receipts. Pending work was eight outbox and eight
alert events. There were zero budget violations, lease losses, email or push
deliveries, recorded rent changes, status changes, or daily checkpoints. Live
removal remains **UNVERIFIED**.

The original checkout and manifest are preserved. From the repository root,
the current reporter reads the original run with the following command.

```sh
.venv/bin/python scripts/soak_report.py .local/worktrees/t07-live/.local/verification/T07/krakow-72h-20261111/manifest.json
```

## Current-version live smoke

A separate start on pin `9147daf80f57d0071f77f9dfde73118a9de6411f` used the
same source config and request budgets. It recorded one eligible cycle from
**2026-11-17 13:54:08.754074 UTC** through **2026-11-17 13:54:51.420520 UTC**,
with **42.666446 seconds** of runner coverage. Each provider discovered one
page, ingested two adverts and used four HTTP attempts, including one robots
request. There were zero retries, errors, lease losses or budget violations.
Gratka succeeded on this pin, which includes the mixed-route parser correction
in `3db8927`. SQLite applied 001, 005, 006, 008, 009 and 010. The private
catalog contains six source adverts, six history rows and four canonical homes.
Live removal remains **UNVERIFIED**.

The smoke used run ID `krakow-current-smoke-20261117` and the standard
`scripts/reliability.py soak` command in the separate `t07-smoke-20261117`
checkout. The wrapper terminated the scheduler after its saved cycle-01
result. A redundant process-group cleanup then returned EPERM and caused the
wrapper to exit 1. A separate process check found no matching runner. The
completed cycle remains in its private manifest beside the catalog and logs.
The smoke checks the newer parser, migrations and ingestion paths for one
live cycle. The 72-hour gate remains **INCOMPLETE**.

## Starting and resuming a reviewed run

Start the bounded schedule in a clean checkout at the reviewed SHA, with an
available host and network for the full 72 hours.

```sh
/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/reliability.py soak --run-id "$soak_run_id" --commit "$soak_commit"
```

The command runs in the foreground. Resume an interrupted run with the same ID
and pin after any in-flight collector exits and releases the lock. Keep the
checkout and catalog unchanged while the run is live. The artifacts are private
under `.local/verification/T07/<run-id>/`. The child uses an explicit clean
environment, a stable run-owned phone key and file-only email settings. The
original one-shot flags retain their existing catalog.

## Separate deterministic drill

On 2026-11-11, the local test used a fake HTTP transport, a fake clock, a
synthetic source and a fresh SQLite database. It restarted Python between 15
drill phases. Timeout used two detail attempts, 403 and 429 one each, and a
persisted 13-hour 429 deadline deferred two later checks without HTTP. Malformed
HTML did not change the last active observation. An unchanged same-day replay
added zero history rows; the next UTC day added one unchanged checkpoint.
Repricing, confirmed 410/404, and a same-price repost retained six total
observations across two source advert identities attached to one canonical home.
The favorite survived confirmed removal. The duplicate event and the repost
added zero notifications; the entire drill emitted one new-match and one price
drop, both with local file previews. No provider traffic occurred in this drill.

A separate process test terminated after two saved cycles, then terminated again
while the third slot was running. On restart the first two slots remained
unchanged, the third was accounted for without replay, and the fourth retained
its original ID and UTC schedule. A SQL recovery test proved that completed
worker checkpoints survive even if the scheduler misses the JSON result, while
partial attempt counts remain explicitly unknown. The worst-case request-budget
test counted 18 attempts (including both origins' robots and all retries); a
robots timeout test exhausted two attempts and stopped before any details.

These fixtures validate failure and removal handling. They do not count toward
elapsed live coverage or real portal removal evidence.
