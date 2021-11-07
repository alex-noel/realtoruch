# Deployment preparation (not executed)

Terraform was validated locally. Helm templates were rendered and Docker Compose configuration was checked. No cloud project, resource, deployment, image registry push or git push was created. These instructions describe remaining operator work; they are not an authorization to deploy.

## Local development

Install Python 3.12 and Node 24 LTS (Node 22.13+ is also supported), then run `make install` and `make dev` from the repository root. The launcher creates private `.local/` SQLite databases and random development secrets, seeds fictional data once, and starts API :8000, auth :8001 and Expo :8081. Ctrl-C stops its child processes. Demo records never load implicitly in production.

For the PostgreSQL + Elasticsearch local topology, start Docker Desktop, then use `docker compose up --build`. Database and Elasticsearch ports are not published; the three HTTP services are bound to localhost. The local Compose ES instance disables authentication only inside its isolated Docker network. Open the frontend separately with `cd apps/mobile && npm run web`. Compose uses explicitly development-only credentials; it is not a production manifest.

## Physical mobile devices

The same app code exports iOS and Android JavaScript bundles. An actual native build still needs Xcode or Android tooling and device/simulator QA. Set the frontend's `EXPO_PUBLIC_API_URL` and `EXPO_PUBLIC_AUTH_URL` to reachable HTTPS services, or your computer's LAN IP for development. For LAN testing, launch the Python services with `--host 0.0.0.0` and explicitly set CORS to your web preview origin if needed; the default dev launcher binds only localhost. Use `npx expo start --lan`, and launch through a compatible Expo Go or a development build. iOS uses Apple Maps; Android builds require a restricted `GOOGLE_MAPS_ANDROID_API_KEY`, read by `app.config.js`. Never put server secrets in `EXPO_PUBLIC_*` variables. Native tokens use SecureStore; browser tokens remain in memory.

## Cloud sequence

1. Select an existing billed project and review capacity/cost. Bigtable and streaming Dataflow are material fixed costs even with few listings. No cost estimate was invented in this repository.
2. Configure a private versioned GCS Terraform state backend and a state-access role. Supply `terraform.tfvars` from the example. The default GKE control plane is private: the operator needs VPN/bastion access to its VPC. Confirm region/quota availability. Run a reviewed Terraform plan before any separately authorized apply.
3. Build immutable `cloud` and `dataflow` Docker targets, scan them, and push only after deployment authorization. Pin image digests for production. The example base image tags and Dataflow launcher `latest` must be resolved to reviewed digests in the release pipeline.
4. Using an operator/schema-owner connection, apply `infra/sql/001_rentals.sql` to `rentals` and `infra/sql/001_auth.sql` to `auth` once. Apply `grants.sql` with each Terraform-created IAM username (`realtoruch-api@PROJECT.iam`, etc.). App users must not own the schema. Future changes require new numbered migrations; `create_all` is only for local startup.
5. Create a 3072-bit RSA signing pair. Auth alone receives the private key; API/auth receive the public key. Populate per-service Secret Manager versions from locally secured JSON, not Terraform variables or source control. `config/production-secrets.example.json` illustrates the API shape. Supply actual random secrets, never example placeholders. The application runtime fetches its own secret with Workload Identity before starting.
6. Prepare each service's configuration using the table below. SQL connections use Cloud SQL Python Connector, private IP and automatic IAM authentication. No permanent SQL password or public SQL endpoint is needed. Kubernetes config must use namespace `realtoruch`, matching the Terraform Workload Identity bindings. The current chart assumes Terraform's default resource name `realtoruch`; keep it or update chart identities/secret names together.
7. Bootstrap Elasticsearch with a strong local Kubernetes secret `elasticsearch-bootstrap/password` and TLS secret `elasticsearch-tls` containing `tls.key`, `tls.crt`, and `ca.crt`. Certificate SANs must include `elasticsearch` and its cluster DNS names. Create a read API key restricted to `rentals-v1` for search, and a writer key for indexer (index create/write and cluster monitor only). Configure `ELASTICSEARCH_CA_FILE=/etc/elasticsearch/ca.crt`. Never disable TLS verification. Elasticsearch is private; the public service offers validated `/v1/search` queries.
8. Render/review the chart with the immutable cloud image and configured sources; deploy only after separate authorization. API ingress exposes `/v1`, auth/search routes, API docs and health endpoints. `/internal` and metrics have no ingress route. Cluster network policies limit ES traffic to search and indexer. Configure DNS to the Terraform API address and wait for managed TLS issuance.
9. Build a Dataflow Flex Template spec from `infra/dataflow/metadata.json` and the `dataflow` image, upload to the staging bucket, then set its existing GCS URI and enable the job. Workers run with private IPs, private SQL access and a dedicated identity. Set explicit worker sizing/limits for expected load. Enable collectors only after the Dataflow consumer and source access are ready.
10. Export the web app with production API/auth URLs baked in. Upload **only** `apps/mobile/dist` to the public web bucket. Use immutable long cache headers on hashed assets and a short/no-cache policy for `index.html`. Set DNS for the CDN hostname. Replace demo map tiles with a licensed production tile service and retain attribution.
11. Enable uptime checks after DNS/TLS/readiness work. Exercise failover, restore, collector interruption, Dataflow redelivery, search outage fallback, API rate limits and contact retention before claiming an application SLA. Account recovery and email verification are still outstanding product work.

| Secret / service | Required configuration |
| --- | --- |
| API | `ENVIRONMENT=production`, `SERVICE_ROLE=api`, private IAM `DATABASE_URL`, `CLOUDSQL_CONNECTION_NAME`, CORS, JWT public key, random contact/internal secrets, `SEARCH_SERVICE_URL=http://search:8000` |
| Auth | `SERVICE_ROLE=auth`, private IAM `AUTH_DATABASE_URL`, Cloud SQL connection name, CORS, JWT public/private keys |
| Search | `SERVICE_ROLE=search`, CORS, `ELASTICSEARCH_URL=https://elasticsearch:9200`, restricted read API key and CA file |
| Collector | `SERVICE_ROLE=collector`, GCP project, Bigtable instance/table, Pub/Sub topic, phone-HMAC key and provider token variables |
| Indexer | `SERVICE_ROLE=indexer`, private IAM rental database and connection name, ES URL/writer key/CA file |
| Dataflow | `SERVICE_ROLE=dataflow`, private IAM rental database and connection name, phone-HMAC key |

Every service also requires `ENVIRONMENT=production` and `DEMO_MODE=false`. API and collector share the same contact-HMAC key; Dataflow preserves already hashed contacts. Auth requires JWT signing material. No secret versions or credentials are committed.

## Operational limitations

- This is one regular node and one zone. Pod budgets cannot protect against a node/zone failure; Elasticsearch can be rebuilt from SQL after a disk failure. SQL backups/PITR and raw observation retention are configured but restore has not been exercised.
- Bigtable is a managed Google service accessed through Google APIs with Private Google Access and IAM, not a database process with a GKE pod IP.
- The Dataflow template spec, container images, Secret Manager versions, SQL grants and Elasticsearch TLS/API keys must exist before dependent workloads start. Terraform intentionally does not generate secrets or push artifacts.
- Production per-IP throttling lives in Cloud Armor (20 auth requests/minute, 120 public requests/minute). Local in-process throttling is disabled in production to avoid treating a shared load-balancer IP as one user. Keep the ingress attached to the policy.
- Monitor pending outbox size, Pub/Sub oldest unacknowledged message, collector CronJob failures, unknown/stale source count and invalid-event subscriptions. The provided monitoring includes uptime/SLO and Pub/Sub backlog alerts; the remaining dashboards and notification recipients need operational configuration.
- Search is eventually consistent. REST falls back to SQL when search is unavailable. SQL keyword matching and Elasticsearch full-text relevance differ; source status and filters are the same contract.
- Recheck rate and source retention must match actual supplier agreements. No portal permission is inferred from robots.txt or public visibility.
