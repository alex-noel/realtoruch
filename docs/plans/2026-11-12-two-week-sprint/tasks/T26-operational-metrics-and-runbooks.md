# T26 — Expose bounded operational metrics and actionable local incident runbooks

**User instruction:** I want to know whether collection, indexing, alerts and account erasure are progressing, and how to diagnose failures without reading private listing or account content.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D5–D6 (2026-11-18–2026-11-19) |
| Worker slot | B |
| Dependencies | [T03](T03-collector-leases.md), [T08](T08-versioned-search-index.md), [T13](T13-delivery-fencing.md) |
| Required review | strong: privacy and operational signals |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | api-routes, auth-routes, metrics-contract |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The existing API metrics endpoint exposes limited outbox information. Collection and delivery workers need consistent queue-age/failure signals. Metrics must remain internal and cheap to collect.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T26/<run-id>/`; commit sanitized reports only.

## Read first

- `backend/realtoruch/api.py`
- `backend/realtoruch/auth.py`
- `backend/realtoruch/collection_health.py`
- `backend/realtoruch/worker.py`
- `backend/realtoruch/email_alerts.py`
- `backend/realtoruch/auth_jobs.py`
- `infra/helm/realtoruch/templates/alerts.yaml`
- `infra/helm/realtoruch/templates/ingress.yaml`
- `infra/terraform/monitoring.tf`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `backend/realtoruch/metrics.py (new)`
- `backend/realtoruch/api.py (internal metrics/readiness only)`
- `backend/realtoruch/auth.py (own-database metrics/readiness only)`
- `backend/realtoruch/worker.py (structured lifecycle logs only)`
- `backend/realtoruch/auth_jobs.py (structured lifecycle logs only)`
- `backend/tests/test_metrics.py (new)`
- `docs/operations/runbooks.md (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Publish queue depth and oldest eligible job age for search outbox, rental email, push and auth/erasure jobs from the service that owns the database. Add collection last-success age, attempts/failures and lease-expiry signals with bounded provider/state labels. A source with no success must expose an explicit unknown/unavailable state rather than zero age.

2. Define names, units, types and label allowlists in a metrics contract. Do not label by user, email, phone, listing ID, URL, request ID or arbitrary city text. Correlation IDs belong in redacted structured logs, not metric labels.

3. Make queue queries aggregate-only and indexed, with a bounded database timeout. A metrics collection error must not break ordinary user endpoints; expose collection failure separately. Do not claim process-local counters survive worker restarts or aggregate across replicas unless the implementation actually supports that.

4. Specify liveness as process responsiveness and readiness as ability to perform that service's required operations. Optional Elasticsearch fallback should not make the REST API unready when SQL discovery remains functional. Auth and delivery readiness must reflect their own essential dependencies without exposing passwords or full error strings.

5. Write runbooks for source 403/429, expired collection lease, old indexing revision, undelivered email, stalled account erasure and restore verification. Include read-only diagnostic commands, expected signals, safe retry conditions and escalation criteria; never automatically replay everything or send external incident messages.

6. Keep metrics and diagnostic routes off public ingress and deny unauthenticated internet access in config tests. Choose proposed alert thresholds (e.g. indexing age >5 min, eligible email age >15 min, erasure age >1 h) as explicit initial settings to calibrate using T07/T25, not proven SLA guarantees.

## Acceptance criteria

- **T26-AC01:** Every critical queue and collection lifecycle has useful depth/age/failure metrics.

- **T26-AC02:** Metric labels are bounded and contain no account/contact/listing secrets.

- **T26-AC03:** Metrics collection is cheap, time-bounded and cannot cause ordinary API requests to fail.

- **T26-AC04:** Liveness/readiness distinguish required dependencies from supported degraded behavior.

- **T26-AC05:** Runbooks provide concrete diagnosis and guarded recovery for six named incidents.

- **T26-AC06:** Public ingress excludes private diagnostics and configuration tests prove that boundary.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T26-TC01 — covers T26-AC01

**Given:** Queues with known pending/leased/retry/dead/cancelled states and timestamps.

**When:** Scrape each service's metrics.

**Then:** Counts and oldest eligible ages match SQL truth; inactive/cancelled jobs are not counted as ready.

### T26-TC02 — covers T26-AC01, T26-AC02

**Given:** Never-successful source and private canary values in fixtures.

**When:** Scrape metrics and collect worker logs.

**Then:** Unknown source state is explicit; no sensitive value or unbounded identifier appears in labels/logs.

### T26-TC03 — covers T26-AC03

**Given:** Database timeout during metrics collection.

**When:** Request metrics and then ordinary API endpoints.

**Then:** Metrics failure is bounded and identifiable; normal API behavior is not poisoned.

### T26-TC04 — covers T26-AC04

**Given:** ES unavailable with healthy SQL, then required SQL unavailable.

**When:** Check REST readiness and a search.

**Then:** Degraded SQL search remains ready; missing essential SQL produces readiness failure without secret details.

### T26-TC05 — covers T26-AC05

**Given:** Synthetic old lease/index/email/erasure states.

**When:** Follow each runbook in isolated fixtures.

**Then:** Commands identify the state and recovery prerequisites without unbounded replay or external messages.

### T26-TC06 — covers T26-AC06

**Given:** Rendered default and collector-enabled Helm ingress.

**When:** Inspect routes and network policy.

**Then:** No public /metrics or private diagnostic exposure is introduced.


## Verification commands and checks

- Run focused metrics and configuration tests
- `make verify-services`
- Render Helm in T28 using the documented profiles

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Metric contract, implementation and privacy tests
- Six operational runbooks with calibrated-threshold follow-up
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not deploy monitoring, create paging subscriptions or send Slack/email incident messages.
- Do not expose raw queue payloads through public diagnostics.
