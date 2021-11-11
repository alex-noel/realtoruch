# T28 — Align Terraform, Helm and service permissions with the verified application

**User instruction:** I want infrastructure configuration ready for a later deployment review, with service boundaries and permissions matching the implemented application, without creating any cloud resources.

| Field | Instruction |
| --- | --- |
| Tier / priority | CORE / P1 |
| Active effort estimate | 6 hours |
| Proposed window | D7–D8 (2026-11-20–2026-11-23) |
| Worker slot | C |
| Dependencies | [T02](T02-ci-quality-gates.md), [T08](T08-versioned-search-index.md), [T13](T13-delivery-fencing.md), [T15](T15-account-data-lifecycle.md), [T26](T26-operational-metrics-and-runbooks.md) |
| Required review | strong: IAM, networking and migrations |
| External gates | None for the task's specified local implementation |
| Shared merge/contract locks | infra-config, sql-grants |
| Initial status | PLANNED — no implementation or acceptance is claimed by this prompt |

## Why this task exists

The user explicitly excluded cloud execution. Existing Terraform/Helm describes one-zone Warsaw GKE, a core node, Spot collection, private storage/search and public REST/search services. Configuration validation is permitted; deployment is not.

## Working instructions

Treat this entire file as the user instruction for one task. Start from the integrator's reviewed dependency base (original sprint baseline `ae893a6`), in an assigned isolated worktree on a `codex/` branch. The local repository is `/Users/alexnoel/Documents/ChatGPT/realtoruch`; use your assigned checkout's root if it differs. Read `AGENTS.md`, [shared contracts](../CONTRACTS.md) and the relevant source files before changing behavior.

Preserve the existing Python/FastAPI/SQLAlchemy and Expo React Native web/mobile stack and committed locks. Keep the Kraków journey intact: strict <5,000 base rent, >=50 m², declared direct status separate from known zero commission, silent existing-search baseline, canonical seen/favorite identity, quiet same-price reposts, favorite lower-price alerts and retained delisted favorites excluded from discovery. Never expose phone fingerprints, account secrets or private messages in public listing/search data.

Implement only the named scope. Coordinate shared-file contracts/merge slots with the integrator; avoid whole-file reformatting or incidental framework upgrades. Every schema change needs PostgreSQL and SQLite fresh/upgrade coverage through T01, using only reserved migration numbers. Do not alter applied baseline migrations.

Use synthetic fixtures and run-owned local resources by default. No cloud provisioning/deployment, paid resources, Git pushes or app publication. Live collection/email/map/provider actions are allowed only where this task explicitly specifies their bounded scope and the required input/authorization gate is satisfied. Do not create accounts, evade access restrictions or send messages to unrelated people.

Complete independent local work while external prerequisites are missing. Report the exact blocker; never substitute a mock/export/screenshot for required real-service, inbox or installed-device evidence. A failed numeric target remains failed. Record actual wall-clock verification dates, independently from Git metadata.

Stage only intended changes and create **every** commit with `python3 scripts/commit.py` plus normal commit arguments. Both author and committer dates must be the same timestamp five calendar years before actual time in Europe/Warsaw (February 29 maps to February 28 when needed). No plain `git commit`, automatic commit-producing rebase/cherry-pick, or push. See [integration rules](../DELEGATION.md).

Return the [handoff template](../HANDOFF_TEMPLATE.md): changed files, commit, exact executed commands/results, counts including skips, each AC and test case status/evidence, migrations/compatibility/recovery, risks and remaining blockers. Keep raw private artifacts under ignored `.local/verification/T28/<run-id>/`; commit sanitized reports only.

## Read first

- `infra/terraform/*`
- `infra/helm/realtoruch/*`
- `infra/sql/grants.sql`
- `infra/sql/migrations.json (from T01)`
- `infra/local/init.sql`
- `compose.yaml`
- `docs/architecture.md`
- `docs/deployment.md`
- `backend/realtoruch/settings.py`

Paths marked “from Txx” are dependency outputs; confirm the reviewed version exists before relying on it. Do not recreate a conflicting contract if the dependency is unavailable.

## Allowed implementation scope

- `infra/terraform/* (configuration corrections only)`
- `infra/helm/realtoruch/* (configuration corrections only)`
- `infra/sql/grants.sql`
- `infra/local/init.sql (fresh-install permissions only)`
- `compose.yaml (local parity only)`
- `docs/deployment.md`
- `backend/tests/test_infra_contract.py (new)`

New files and targeted helper extraction are allowed inside this scope. Tell the integrator before editing unrelated services or changing a shared API. A path with a parenthetical qualifier limits which part of that file you own.

## Technical requirements

1. Validate defaults remain one GKE zone in the Warsaw region with the requested initial core-node topology, separate Spot collection jobs, fleet membership and configuration for CDN/Pub/Sub/Bigtable/Dataflow/Cloud SQL. Preserve explicit feature flags; document how zero/one core nodes or disruption affect service availability rather than promising an SLA.

2. Audit rendered workloads, service identities, SQL grants and migration paths against new revisions, delivery leases and account-closure data. API, auth, search, indexing and collection must receive only the permissions needed by their implemented operations. Test real PostgreSQL role permissions where possible.

3. Keep Cloud SQL, Bigtable access paths and Elasticsearch internal. Public search means the read-only application search service with validated filters/rate limits, not an unauthenticated Elasticsearch port. Confirm network policies permit required DNS/SQL/queue/provider/SMTP egress without accidentally allowing every internal service to access auth data.

4. Preserve the single active indexing deployment setting until T08 explicitly proves overlapping indexers safe. Render collector-off and collector-on profiles, resource requests/limits, readiness/liveness and graceful shutdown behavior. Compare requested CPU/memory with the chosen single-node allocatable budget and disclose missing headroom.

5. Ensure CDN caching applies only to public immutable/static content; account APIs, messages, tokens and personalized responses must use no-store and bypass shared caching. Keep credentials in secret references/example placeholders; no real SMTP or cloud keys enter values, tfvars or rendered artifacts.

6. Run terraform fmt -check, terraform init -backend=false and terraform validate in a disposable copied directory with no remote state/credentials; Helm lint/template; local Compose config checks; migration/grant tests. Do not run apply, remote-state init, provider-authenticated plan, cluster changes, image push, DNS updates or cloud creation.

## Acceptance criteria

- **T28-AC01:** Terraform and Helm validate offline/configuration-only with both collection profiles.

- **T28-AC02:** Rendered architecture preserves the private database/search boundaries and separate service identities.

- **T28-AC03:** Database grants support required new operations and deny unrelated service access.

- **T28-AC04:** Workload sizing, indexing concurrency and health/shutdown settings are explicit and internally consistent.

- **T28-AC05:** Public caching and secret handling protect account/private content.

- **T28-AC06:** A deployment-review document lists remaining external inputs and accurately states that no cloud resources were created.

## Required test cases

Run these as automated behavioral tests where practical; the task identifies genuine external/manual acceptance separately. Use deterministic barriers/fake clocks for races and explain any not-run case.

### T28-TC01 — covers T28-AC01

**Given:** Clean copied Terraform and Helm directories with no cloud credentials.

**When:** Run the allowed configuration validation commands.

**Then:** Validation completes without remote state or resource mutations; command output is recorded.

### T28-TC02 — covers T28-AC02, T28-AC05

**Given:** Rendered services/ingress/network policies and secret references.

**When:** Inspect public routes, caching and secret placeholders.

**Then:** Only intended public APIs/assets are reachable; ES/SQL/auth data and diagnostics remain protected.

### T28-TC03 — covers T28-AC03

**Given:** Disposable PostgreSQL with separate service roles.

**When:** Run representative permitted and forbidden statements.

**Then:** Required operations pass and cross-service private operations fail.

### T28-TC04 — covers T28-AC04

**Given:** Default one-node profile plus enabled collection profile.

**When:** Sum requests and inspect disruption/probe/shutdown/indexer settings.

**Then:** Capacity assumptions and known single-zone limitations are documented; no unsupported availability claim is made.

### T28-TC05 — covers T28-AC01, T28-AC04

**Given:** Collector feature flag false versus true.

**When:** Render both profiles.

**Then:** No collection job exists in the off profile; on-profile jobs retain Spot/pacing/budget controls.

### T28-TC06 — covers T28-AC05, T28-AC06

**Given:** Diff and validation artifacts.

**When:** Scan for real secrets and deployment commands.

**Then:** Only config/templates/docs changed and no credential/resource creation is present.


## Verification commands and checks

- `terraform fmt -check in infra/terraform`
- `terraform init -backend=false and terraform validate in an isolated copy`
- `helm lint infra/helm/realtoruch and helm template for both profiles`
- `docker compose config --quiet`
- `make verify-services`

Commands marked new or referring to a predecessor become runnable only after that implementation lands. Record the exact command actually used; prose checks are instructions, not shell snippets. Run the relevant regression profile after targeted checks. Do not repeatedly run unrelated suites without a change or unresolved concern.

## Deliverables

- Validated configuration corrections and role tests
- Updated architecture/deployment input checklist and sizing notes
- Completed AC/test evidence using the handoff template, with external/local verification clearly separated.

## Out of scope

- Do not deploy, provision, run cloud plans, create accounts or push container images.
- Do not represent a single-node/single-zone config as a guaranteed uptime SLA.
