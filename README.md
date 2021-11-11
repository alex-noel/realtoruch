# Realtoruch

A Polish rental discovery app with a Python backend, shared React Native / web frontend, and configuration-only GCP infrastructure.

**Current status:** runnable local app with real, bounded Kraków and Warsaw collection from Otodom, Gratka and Morizon, plus a separate sample catalog. OLX collection is blocked by HTTP 403 in the tested environment and remains disabled. This is not full marketplace coverage, full Otodom feature parity or a production deployment; see the [feature ledger](docs/feature-status.md).

## Run locally

Requires Python 3.12 and Node 24 (see `.nvmrc`).

```sh
make install
make dev
```

Open **http://localhost:8081**. Public API docs: **http://localhost:8000/docs**. Auth: port **8001**. Create a local account with a 12+ character password to try favorites, saved areas, email alerts and reports. The launcher also runs the background alert worker. Ctrl-C stops the services.

The launcher creates ignored local databases and random development secrets. The original sample catalog is in Warszawa: select that city to view its 12 fictional homes, 18 source adverts and six months of fictional observations. For the Kraków journey below, use `make journey`. No live listing fetches run by default.

## Collect and view real listings

```sh
make collect
make live
```

`make collect` uses `config/sources.live.json` and stores real data in the ignored `.local/live-rentals.db`. It reads up to two search pages, attempts up to 12 new adverts and rechecks up to 24 stored adverts per enabled source, at six requests per minute per provider. The three providers run concurrently; each retains its own pacing. Previously checked adverts wait six hours before another request. Source robots rules may reduce coverage further. The report at `.local/last-collection.json` records counts, limits and failures. A partial/failed run exits nonzero while preserving successful observations.

Useful bounded commands:

```sh
make collect ARGS="--source otodom --max-listings 3 --max-pages 1"
make collect ARGS="--city Kraków --recheck-only"
make collect ARGS="--city Warszawa --max-pages 1 --max-listings 6"
```

`make live` serves the collected catalog at the same local address, with no sample seeding. Stop any running `make dev` first because they use the same ports. Collection does not run automatically when opening the UI. The optional worker `--loop` and configured cloud CronJob perform recurring collection; no background scheduler is installed by these commands.

See [source behavior and limitations](docs/source-connectors.md). The raw research captures, real catalog and private contact fingerprints are ignored by Git.

## Included

- Responsive, sharp-cornered list/map interface with native iOS/Android map components.
- Drawn map areas, city, text, size, price, rooms, property, amenities, direct/agency, commission and risk filters. The UI price limit is exclusive: below 5,000 means <5,000 PLN base rent; building fees are separate.
- Listing gallery, full fee breakdown, source comparisons, three-home comparison and observed price changes.
- Separate FastAPI REST, authentication and Elasticsearch-backed search services.
- Seen homes, persistent favorites including delisted properties, saved polygon searches, a notification inbox, confirmed email alerts and optional browser/native push. Same-price reposts stay quiet; a new lowest rent on a liked home produces a price-drop alert.
- Conservative canonical deduplication, preserved source evidence, idempotent updates, lifecycle tracking, price history and private phone fingerprints.
- Source-specific public HTML discovery/parsing for Otodom, Gratka and Morizon; configurable JSON feeds and JSON-LD URLs; oldest-first stored-advert rechecks, explicit removal handling and collection reports.
- Six-hour collector job, Bigtable → Pub/Sub → Dataflow → private PostgreSQL path, transactional search and alert queues, daily unchanged-observation checkpoints. Cloud execution remains unverified.
- Terraform for Warsaw GKE/fleet, Spot ingestion, private Cloud SQL, Bigtable, Pub/Sub, optional Dataflow job, CDN, IAM/secrets and a 95% availability monitoring target. Helm workloads and a local Docker Compose topology.

## Try the complete rental journey

```sh
make journey
# In another terminal, after saving your search in the app:
make journey-event ARGS=new
# Open and like the matching home, then:
make journey-event ARGS=delist
make journey-event ARGS=relist
make journey-event ARGS=drop
make journey-event ARGS=delist
```

This uses a separate `.local/journey-rentals.db`. In the app, draw an area around Kraków/Krowodrza, choose rent below 5,000 PLN, minimum 50 m², and direct offers, then save the search. In Notifications, enable email alerts and follow the confirmation link in the generated `.local/mail/*.eml` file. The local mail adapter writes previews only; it does not send real email. The new home is 55 m² at 4,500 PLN. A repost at that price is silent; the `drop` event relists it at 4,200 PLN. A final delist keeps it in Saved homes and removes it from discovery. Events are synthetic and never modify the live catalog.

For real email delivery, configure SMTP and a verified sender as described in [deployment preparation](docs/deployment.md#email-and-device-notifications). The inbox and email preferences survive sign-out; optional device push is revoked on sign-out.

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
