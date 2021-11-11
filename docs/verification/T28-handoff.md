# T28 handoff

- Status: IMPLEMENTED_LOCAL; independent IAM, network and migration review remains required.
- Base: `b4ae27282e4caaebe380f2d6fa2314067c19181b`. Commit: see Git history (created via `scripts/commit.py`).
- Work and checks: 2026-11-11 CET (2026-11-11 UTC).
- Scope: chart, grants and deployment review. The integrator authorized the small `scripts/verify.py` test-selection addition. No schema migration or application API change.

## Changes and compatibility

`infra/sql/grants.sql` covers registered revisions and account closure, merge/cleanup permissions and Dataflow cancellation. Indexer receives row-lock privilege and limited retention access; schema owner runs migrations/grants and runtime users do not own schema. No permissions are retroactively revoked from previously provisioned runtime users: review and revoke obsolete grants as a separate deliberate operator step. `infra/helm/realtoruch` corrects auth readiness, adds read-only worker probes, explicit termination grace, private scraper ingress, egress policies and no-store public BackendConfig headers. `values.yaml` adds a placeholder private SQL CIDR requiring replacement. The chart retains one Recreate indexer, disabled-by-default Spot collection, and separate identities. `docs/deployment.md` corrects the full registry, ES alias/key names, capacity and operator inputs. `backend/tests/test_infra_contract.py` exercises PostgreSQL roles in runner-owned fresh databases; `scripts/verify.py` selects it. Compose remains a shared development-owner topology, not a role-security demonstration.

## Acceptance and test evidence

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC01 | PASS | TC01/TC05: Terraform fmt, credential-free copy init/validate, Helm lint/two renders and Compose config passed. |
| AC02 | PASS, configuration only | TC02: rendered internal ES Service, ingress and network policies; no cloud enforcement tested. SQL access is restricted by role even where databases share an instance. |
| AC03 | PASS, representative | TC03: ten actual PostgreSQL permit/deny statements, full registry applied on fresh databases; broader application operations and live IAM remain review items. |
| AC04 | PASS, configuration only | TC04/TC05: 1,100m/3,712Mi steady requests, retention +100m/256Mi; one Recreate indexer, probes and 30-second grace; actual allocatable and disruption behavior unmeasured. |
| AC05 | PASS, configuration only | TC02/TC06: separate static bucket and API BackendConfigs add no-store; no public ES, metrics or internal ingress route. Secret references/placeholders only. Live proxy behavior remains untested. |
| AC06 | PASS | TC06: deployment checklist documents inputs and no cloud execution. |

## Verification and commands

All commands ran at the worktree root on macOS arm64, Python 3.12.9, Node 24.6.0, Helm 3.16.4, Terraform 1.9.8; Docker server 29.8.0 aarch64. The native Elasticsearch 8.19.6 image was used with `DOCKER_DEFAULT_PLATFORM` unset. The locally available PostgreSQL 16-alpine image was reported by the integrator as emulated x86_64; architecture was not independently confirmed here. No user catalog was used.

- `PATH="/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t26/.local/verification/T26/tools/darwin-arm64:$PATH" helm lint infra/helm/realtoruch` — exit 0, one chart, zero failures.
- Same PATH, `helm template t28 infra/helm/realtoruch` and `helm template t28 infra/helm/realtoruch --set collector.enabled=true` — exit 0 each; collect-listings absent/off and present/on. Outputs were temporary, contain no credentials.
- `docker compose config --quiet` and `git diff --check` — exit 0.
- Terraform binary downloaded from official HashiCorp release and checked against its official SHA256SUMS. `terraform -chdir=infra/terraform fmt -check`; with empty environment and private HOME, `terraform -chdir=.local/verification/T28/tf-copy init -backend=false -input=false` and `terraform -chdir=.local/verification/T28/tf-copy validate` — all exit 0; providers google/google-beta 6.50.0. The copy contains only `.tf` files and no credentials, remote state or backend initialization. Initial checksum command failed because the downloaded archive was named `terraform.zip`; renamed to the official filename, then checksum passed.
- Disposable, uniquely named and labeled PostgreSQL container, random loopback port, initialized all entries in `infra/sql/migrations.json`; psql applied grants with distinct roles. Ten statements tested positive/negative access, 10 passed, 0 failed. The container was deleted. An initial `docker inspect` architecture format failed; deletion was performed afterward.
- `PATH="/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t26/.local/verification/T26/tools/darwin-arm64:$PATH" PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_metrics.py -k test_t26_helm -q` — 2 passed, 0 failed, 0 skipped.
- `PATH="/Users/alexnoel/.nvm/versions/node/v24.6.0/bin:/Users/alexnoel/Documents/ChatGPT/realtoruch/.local/worktrees/t26/.local/verification/T26/tools/darwin-arm64:$PATH" env -u DOCKER_DEFAULT_PLATFORM /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python scripts/verify.py services --run-id t28-7a27` — exit 0, 188 passed, 0 failed, 0 skipped; ignored raw report `.local/verification/T01/t28-7a27/report.json`. This first run predates adding the new role test and final grant refinements.

## Recovery and review

Re-render both profiles, run the service runner on its disposable resources, and review resulting role statements. Roll back chart changes through a reviewed release; correct grants forward under the schema owner and preserve existing data. The new network policy allows general outbound HTTPS for Google APIs/providers and needs an egress gateway/firewall to enforce domain restrictions; SQL CIDR, node allocatable, private metrics transport, scraper key provisioning, ES privileges, SMTP and actual ingress cache behavior all require target-environment review. Worker readiness does not prove mail delivery. The single node/zone has no availability guarantee, and worker termination can interrupt in-flight work despite the grace period. No cloud resources, provider requests, real email, image pushes, deployment or Git push were made.
- The new role test was additionally run against the run-owned loopback PostgreSQL instance with `PG_PORT=$(docker port realtoruch-t01-t28-7a28-pg 5432/tcp | awk -F: '{print $NF}') VERIFY_RUN_ID=t28-7a28 TEST_POSTGRES_URL="postgresql+psycopg://rentals:verification@127.0.0.1:$PG_PORT/r_t28_7a28" PYTHONPATH=backend /Users/alexnoel/Documents/ChatGPT/realtoruch/.venv/bin/python -m pytest backend/tests/test_infra_contract.py -q` — exit 0, 1 passed, 0 failed, 0 skipped. The test applies the complete manifest to fresh temporary databases and performs ten role statements.
- Final service profile: same command as above with `--run-id t28-7a28` — exit 0, 189 passed, 0 failed, 0 skipped; private ignored report `.local/verification/T01/t28-7a28/report.json`, 2026-11-11 21:53:07–21:54:50 UTC. It ran the new role test and removed its labeled containers. The subsequent targeted test also verified the added loopback guard. PostgreSQL statements use `SET ROLE` after an owner connection, which verifies table privileges; separate-login `CONNECT` denial needs independent review.
