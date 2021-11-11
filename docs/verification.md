# Verification record

The current implementation was verified locally on 11 November 2026, including a browser-driven rental journey, email previews, PostgreSQL and Elasticsearch. No cloud resources were applied and no code or images were pushed.

| Check | Result |
| --- | --- |
| Python integration/unit suite | 102 passed; two opt-in service tests skipped in this run and passed separately against PostgreSQL/Elasticsearch; one upstream TestClient deprecation warning |
| TypeScript strict check | Passed on 11 November |
| Expo production web export | Passed on 11 November |
| Expo iOS/Android Hermes bundle exports | Passed for both platforms on 11 November (about 2.1 MB each); not a signed native build or device test |
| Terraform 1.13.5 + Google / Google beta 6.50.0 | `fmt` and `validate` passed on 11 November; no plan/apply |
| Helm 3.19 lint/template rendering | Passed on 11 November: 29 resources with collector off; 30 with collector on; alerts Deployment and service account verified |
| Docker Compose | Configuration validated; isolated PostgreSQL 16 and Elasticsearch 8.19.6 containers started for service integration tests, then stopped |
| PostgreSQL migrations / roles | 001 rentals/auth + 002 alerts + 003 email applied; SQL grants applied to local test roles. Cloud SQL IAM remains unverified |
| Email / push transport | Confirmation, unsubscribe, retry/cancellation and email-file tests passed; actual SMTP protocol tested against a local socket receiver; Web Push payload encryption verified |
| Optional GCP/Dataflow dependencies | pip dry-run resolved successfully on 7 November; managed Dataflow execution not tested |
| Public/secret boundary | No phone hashes in public listings; ES stays ClusterIP; `/internal` excluded from ingress |

## Eight-step rental journey — 11 November

The browser ran the production web export against the local auth/API services and a separate background alerts process. Synthetic lifecycle events were injected with `scripts/journey.py` into a separate database; real listings were never marked inactive or repriced for the test.

1. Selected Kraków, rent **below** 5,000 PLN, minimum 50 m² and direct offers, drew an area, and saved the search. Reopening Saved searches restored the polygon and filters.
2. Enabled email alerts, opened the locally generated confirmation email link, and saw successful confirmation in the app.
3. Inserted a matching 55 m² home at 4,500 PLN. The worker produced one inbox notification and one email preview.
4. Opened it and saved it. Its card displayed **SEEN**, the notification became read, and Saved homes contained it.
5. Delisted it: the saved card displayed **DELISTED**, while the filtered discovery list/map had zero results/pins.
6. Relisted under a different advert ID at 4,500 PLN: the canonical ID stayed the same, unread count stayed zero, and no rental email was added.
7. Relisted at 4,200 PLN: exactly one **PRICE DROP ON A SAVED HOME** notification and email were produced, showing 4,500 → 4,200 PLN.
8. Delisted again: Saved homes retained the seen/delisted home at the last price; discovery/map again had zero matches.

The email queue contained exactly three sent local previews: confirmation, first match and lower price. These were local `.eml` files, not delivery to an external mailbox. The phone viewport check at 390 × 844 showed the notification controls/cards without horizontal overflow. The final browser console check had no errors or warnings.

The PostgreSQL tests apply the actual numbered migrations, repeat the full API/alert journey, and test an ingestion/indexer acknowledgement race. A real Elasticsearch query confirmed polygon/exclusive-price matching and removal of inactive homes. The emulated AMD64 ES image initially failed its seccomp startup check on Apple Silicon; the native ARM64 image ran successfully without disabling protections.

![Verified price-drop notification](previews/rental-alerts.png)
![Verified phone notifications](previews/rental-alerts-mobile.png)
![Delisted favorite retained](previews/delisted-favorite.png)

## Live Kraków collection — 11 November

Otodom, Gratka and Morizon each contributed 18 adverts: **54 source adverts merged into 41 canonical homes**, including eight declared private offers. Two real offers matched the selected price/size/private filters and the drawn area in the browser. These bounded samples do not establish full-market coverage or verify owner identity.

The second concurrent run checked 12 new adverts per provider and skipped six fresh ones each, with no reported errors. A recheck-only run while all records were still fresh finished with zero outbound requests and no extra history rows. Unit tests separately cover city scoping, freshness budgets, daily unchanged checkpoints, idempotency and concurrent search delivery. OLX remains disabled after HTTP 403 on public robots retrieval; no account was created or used and no successful OLX parser is claimed.

## Earlier live Warszawa checks — 11 November

Bounded collection from the public Warszawa rental pages of Otodom, Gratka and Morizon succeeded. Each connector checked robots rules and paced requests. All three search parsers discovered listings on pages one and two, including links to the next page. This is a sample check, not a complete inventory of those portals.

- The Warszawa portion of the live SQLite catalog contains **16 source adverts merged into 12 homes**, with no demo records: six Otodom, five Gratka and five Morizon adverts. Four Gratka/Morizon cross-posts merged using their shared internal identity and compatible property details.
- A final recheck visited all 16 stored adverts with zero reported collection errors. The catalog contains 39 observations, including an Otodom base-rent change from 3,500 to 3,300 PLN. Ten source adverts have private contact fingerprints; public listing responses exclude those fingerprints and source syndication keys.
- Chrome showed the real homes as a list and map. The direct-offer filter returned four homes. A merged Gratka/Morizon home displayed both source links, 15 gallery images, its stated 960 PLN monthly fee and a 4,260 PLN monthly total. The last gallery image loaded, and all gallery controls wrapped within the dialog.
- The market API returned a 3,375 PLN median for the 12 homes. Live history currently starts with these November observations; the demo's fictional past months are absent from the live database.
- OLX returned HTTP 403 for robots retrieval and remains disabled. No OLX-specific parser or working live collection is claimed.

Fixture and integration tests cover explicit removal, parser failure, throttling, changed rent, bounded discovery, robots wildcard rules, conflicting duplicate evidence and private-data boundaries. Simulated Bigtable/Pub/Sub tests verify that a failed publication does not advance recheck state. Portal removals, throttling and cloud failures were tested with controlled responses, not induced on live services. Sanitized fixture provenance is recorded in [the fixture README](../backend/tests/fixtures/portals/README.md).

![Verified live catalog](previews/live-catalog.jpg)

## Demo browser checks — 7 November

The running application was checked in Chrome at desktop size and a 390 × 844 phone viewport:

- Synthetic catalog rendered 12 canonical homes from 18 source adverts, with source links and clearly marked demo state.
- Private-offer + no-risk filtering reduced the result set to seven homes.
- Property comparison showed each home's base rent, fees, deposit, commission, dimensions, advertiser and sources.
- Rent insights displayed six observed months, per-month sample sizes and methodology.
- A 3,000 PLN maximum yielded three homes; map pins matched that filtered result set.
- Tapping a repeated-contact example opened its gallery, source/fee details, price history and non-accusatory signal explanation.
- Narrow-screen filter overflow was found and corrected; tablet map switching and initial map bounds were corrected.
- A React Native empty-text conditional warning found in dialog inspection was corrected; the final static production bundle was checked with no new dialog errors.

![Verified desktop preview](previews/desktop.jpg)

## Performance and dependencies

Importing individual icons reduced the main web bundle from about 3.1 MB to about 587 KB uncompressed (about 167 KB gzip). Leaflet loads as a separate approximately 149 KB / 43 KB gzip chunk. These are build sizes, not measured Core Web Vitals or a latency SLA. The UI requests at most 24 homes per page and avoids external font loading.

The project was moved to the compatible Expo 58 / React 19.3 / React Native 0.88 package set. The latest audit run after that upgrade showed **zero high/critical** and five moderate findings associated with Expo's development-time `glob`/`minimatch` dependency chain. No forced incompatible downgrade or global major override was applied. Keep these toolchain dependencies under review before release. Python requirements are pinned for the tested base runtime and development environment; cloud extras have bounded versions and were dependency-resolved, not fully exercised.

## Not verified

- Working OLX collection, full-market coverage or geography outside the configured Kraków/Warszawa searches.
- Unattended collection over an extended period, live removal detection and portal changes beyond the captured fixtures.
- Production GCP permissions/quotas, Cloud SQL IAM, TLS issuance, Cloud CDN, and long-running deployment behavior. Local PostgreSQL/Elasticsearch integration is verified.
- A real Dataflow streaming job or Spot interruption/recovery.
- Real SMTP-provider/inbox delivery and real browser/Expo push-provider delivery. Production SMTP and native push credentials have not been supplied.
- Signed iOS/Android apps, native map credentials, physical-device behavior or app-store delivery.
- Load capacity, a 30-day 95% availability result, backup restoration or production security certification.

The [feature ledger](feature-status.md) identifies further product scope, including the advertiser platform and production delivery prerequisites. This verification record should not be interpreted as complete Otodom parity or production acceptance.
