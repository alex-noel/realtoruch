# Realtoruch

A Polish rental discovery app with a Python backend, shared React Native / web frontend, and configuration-only GCP infrastructure.

**Current status:** runnable local app with real, bounded Warsaw collection from Otodom, Gratka and Morizon, plus a separate sample catalog. OLX collection is blocked by HTTP 403 in the tested environment and remains disabled. This is not full marketplace coverage, full Otodom feature parity or a production deployment; see the [feature ledger](docs/feature-status.md).

## Run locally

Requires Python 3.12 and Node 24 (see `.nvmrc`).

```sh
make install
make dev
```

Open **http://localhost:8081**. Public API docs: **http://localhost:8000/docs**. Auth: port **8001**. Create a local account with a 12+ character password to try favorites, saved searches and reports. Ctrl-C stops the services.

The launcher creates ignored local databases and random development secrets. All 12 sample homes, 18 source adverts and six months of price observations are explicitly fictional. No live listing fetches run by default.

## Collect and view real listings

```sh
make collect
make live
```

`make collect` uses `config/sources.live.json` and stores real data in the ignored `.local/live-rentals.db`. It reads up to two search pages, attempts up to 12 new adverts and rechecks up to 24 stored adverts per enabled source, at six requests per minute. Source robots rules may reduce coverage further. The report at `.local/last-collection.json` records counts, limits and failures. A partial/failed run exits nonzero while preserving successful observations.

Useful bounded commands:

```sh
make collect ARGS="--source otodom --max-listings 3 --max-pages 1"
make collect ARGS="--recheck-only"
```

`make live` serves the collected catalog at the same local address, with no sample seeding. Stop any running `make dev` first because they use the same ports. Collection does not run automatically when opening the UI. The optional worker `--loop` and configured cloud CronJob perform recurring collection; no background scheduler is installed by these commands.

See [source behavior and limitations](docs/source-connectors.md). The raw research captures, real catalog and private contact fingerprints are ignored by Git.

## Included

- Responsive, sharp-cornered list/map interface with native iOS/Android map components.
- City, text, area, price, rooms, property, amenities, direct/agency, commission and risk filters.
- Listing gallery, full fee breakdown, source comparisons, three-home comparison and observed price changes.
- Separate FastAPI REST, authentication and Elasticsearch-backed search services.
- Account-isolated favorites and saved searches with new-match counts; user reports.
- Conservative canonical deduplication, preserved source evidence, idempotent updates, lifecycle tracking, price history and private phone fingerprints.
- Source-specific public HTML discovery/parsing for Otodom, Gratka and Morizon; configurable JSON feeds and JSON-LD URLs; oldest-first stored-advert rechecks, explicit removal handling and collection reports.
- Six-hour collector job, Bigtable → Pub/Sub → Dataflow → private PostgreSQL path, transactional search outbox. Cloud execution remains unverified.
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
