# Realtoruch

A Polish rental discovery app with a Python backend, shared React Native / web frontend, and configuration-only GCP infrastructure.

**Current status:** runnable local app with a synthetic catalog, configurable source adapters and tested core workflows. Live portal ingestion awaits approved feeds/API access. This is not yet full Otodom feature parity or a production deployment; see the [feature ledger](docs/feature-status.md).

## Run locally

Requires Python 3.12 and Node 24 (see `.nvmrc`).

```sh
make install
make dev
```

Open **http://localhost:8081**. Public API docs: **http://localhost:8000/docs**. Auth: port **8001**. Create a local account with a 12+ character password to try favorites, saved searches and reports. Ctrl-C stops the services.

The launcher creates ignored local databases and random development secrets. All 12 sample homes, 18 source adverts and six months of price observations are explicitly fictional. No live listing fetches run by default.

## Included

- Responsive, sharp-cornered list/map interface with native iOS/Android map components.
- City, text, area, price, rooms, property, amenities, direct/agency, commission and risk filters.
- Listing gallery, full fee breakdown, source comparisons, three-home comparison and observed price changes.
- Separate FastAPI REST, authentication and Elasticsearch-backed search services.
- Account-isolated favorites and saved searches with new-match counts; user reports.
- Conservative canonical deduplication, preserved source evidence, idempotent updates, lifecycle tracking, price history and private phone fingerprints.
- Configured JSON feeds and JSON-LD adapters for approved sources, six-hour collector job, Bigtable → Pub/Sub → Dataflow → private PostgreSQL path, transactional search outbox.
- Terraform for Warsaw GKE/fleet, Spot ingestion, private Cloud SQL, Bigtable, Pub/Sub, optional Dataflow job, CDN, IAM/secrets and a 95% availability monitoring target. Helm workloads and a local Docker Compose topology.

## Verify

```sh
make test
make web-build
docker compose config --quiet
cd apps/mobile
EXPO_OFFLINE=1 npx expo export --platform ios --platform android --output-dir dist-native
```

The no-cloud default uses SQLite and SQL search to run immediately. Docker Compose uses PostgreSQL and Elasticsearch. Native JavaScript exports do not replace testing a signed app on physical devices.

## Repository

| Path | Purpose |
| --- | --- |
| `apps/mobile` | Expo shared frontend, platform-specific maps |
| `backend/realtoruch` | API, auth, search, ingestion, workers and Dataflow |
| `backend/tests` | Data integrity, privacy, API/auth and connector checks |
| `config` | Disabled source profiles and configuration examples |
| `infra/terraform` | GCP resources; no apply performed |
| `infra/helm/realtoruch` | Kubernetes services, jobs, ingress and network policies |
| `infra/sql` | Initial PostgreSQL schemas and least-privilege grants |
| `docs` | Architecture, source onboarding, deployment and parity boundaries |

Read [architecture](docs/architecture.md), [source connectors](docs/source-connectors.md), [deployment preparation](docs/deployment.md), and [verification](docs/verification.md) before connecting live data or deploying.
