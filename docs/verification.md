# Verification record

Live collection, the updated application and Helm templates were verified locally on 11 November 2026. Terraform, Compose and native bundle checks below were last run on 7 November 2026. No cloud resources were applied and no code or images were pushed.

| Check | Result |
| --- | --- |
| Python integration/unit suite | 66 passed on 11 November; one upstream TestClient deprecation warning |
| TypeScript strict check | Passed on 11 November |
| Expo production web export | Passed on 11 November |
| Expo iOS/Android Hermes bundle exports | Passed for both platforms on 7 November; not a signed native build or device test |
| Terraform 1.13.5 + Google / Google beta 6.50.0 | `fmt` and `validate` passed on 7 November; no plan/apply |
| Helm 3.19 lint/template rendering | Passed on 11 November: 27 resources with collector off; 28 with collector on; shared API/collector source ConfigMap verified |
| Docker Compose | Configuration validated on 7 November; containers not started because Docker daemon was unavailable |
| Optional GCP/Dataflow dependencies | pip dry-run resolved successfully on 7 November; managed Dataflow execution not tested |
| Public/secret boundary | No phone hashes in public listings; ES stays ClusterIP; `/internal` excluded from ingress |

## Live collection and browser checks — 11 November

Bounded collection from the public Warszawa rental pages of Otodom, Gratka and Morizon succeeded. Each connector checked robots rules and paced requests. All three search parsers discovered listings on pages one and two, including links to the next page. This is a sample check, not a complete inventory of those portals.

- The live SQLite catalog contains **16 source adverts merged into 12 homes**, with no demo records: six Otodom, five Gratka and five Morizon adverts. Four Gratka/Morizon cross-posts merged using their shared internal identity and compatible property details.
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

Importing individual icons reduced the main web bundle from about 3.1 MB to about 569 KB uncompressed (about 161 KB gzip). Leaflet loads as a separate approximately 149 KB / 43 KB gzip chunk. These are build sizes, not measured Core Web Vitals or a latency SLA. The UI requests at most 24 homes per page and avoids external font loading.

The project was moved to the compatible Expo 58 / React 19.3 / React Native 0.88 package set. The latest audit run after that upgrade showed **zero high/critical** and five moderate findings associated with Expo's development-time `glob`/`minimatch` dependency chain. No forced incompatible downgrade or global major override was applied. Keep these toolchain dependencies under review before release. Python requirements are pinned for the tested base runtime and development environment; cloud extras have bounded versions and were dependency-resolved, not fully exercised.

## Not verified

- Working OLX collection, full-market coverage or live collection outside the configured Warszawa searches.
- Unattended collection over an extended period, live removal detection and portal changes beyond the captured fixtures.
- Production PostgreSQL/Elasticsearch container integration, GCP permissions/quotas, TLS issuance, Cloud SQL grants and Cloud CDN behavior.
- A real Dataflow streaming job or Spot interruption/recovery.
- Signed iOS/Android apps, native map credentials, physical-device behavior or app-store delivery.
- Load capacity, a 30-day 95% availability result, backup restoration or production security certification.

The [feature ledger](feature-status.md) identifies further product scope, including the advertiser platform and notification delivery. This verification record should not be interpreted as complete Otodom parity or production acceptance.
