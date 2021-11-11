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
extends the schedule.

The live pin is `b3782cca0f4a05b788e4fd00656ef01327deb552`; the SHA-256 of
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

## Live evidence

Run `krakow-72h-20261111` started at **2026-11-11 21:27:38.320642 UTC**.
Its fixed target end is **2026-11-14 21:27:38.320642 UTC**.
The first slot ended at **2026-11-11 21:28:19.729317 UTC**. At the initial
report snapshot, the run had 41.41 seconds of observed coverage, one attempted
and eligible slot, 11 pending, and zero deferred, missed, interrupted or gaps.
The live result is **INCOMPLETE**.

| Provider | Outcome | Discovery parsed | New details checked / ingested | Due rechecks | HTTP attempts (robots / retry) | Body bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Otodom | Succeeded | 1 | 2 / 2 | 0 | 4 (1 / 0) | 2,114,394 |
| Gratka | Failed: discovery parser reported `unrecognized_page` | 0 | 0 / 0 | 0 | 2 (1 / 0) | 993,748 |
| Morizon | Succeeded | 1 | 2 / 2 | 0 | 4 (1 / 0) | 2,235,301 |

Gratka has no successful real check at this snapshot. The scheduler recorded
the failure without an out-of-schedule retry. There were zero budget violations
and zero lease losses. The isolated SQLite catalog used migrations 001, 005,
006 and 008. From an empty baseline it grew to four homes, four source adverts,
four initial history rows, and four event receipts. There were zero recorded
rent changes, status changes or daily checkpoints. Pending work was four outbox
and four alert events, with zero email or push deliveries. **No real removal was
observed**; it remains unverified independently of the fixture drill.

To resume, run the same command in the clean detached checkout at the same pin:

```sh
/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/reliability.py soak --run-id krakow-72h-20261111 --commit b3782cca0f4a05b788e4fd00656ef01327deb552
```

The command runs in the foreground. The lock stays held by an in-flight
collector if the scheduler process dies; let that collector exit before
resuming. Do not edit the pinned checkout or open the run catalog for writing.
The following command reads only the manifest and emits aggregate counts:

```sh
/Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/soak_report.py .local/verification/T07/krakow-72h-20261111/manifest.json
```

Private artifacts in the detached checkout:
`.local/verification/T07/krakow-72h-20261111/{manifest.json,catalog.db,cycle-*.json,cycle-*.log}`.
The child runs in that directory with an explicit clean environment, a stable
run-owned phone key and file-only email settings. No real recipients are
configured. Old one-shot flags retain their previous behavior and catalog.

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
