# Verification record

Verified locally on 7 November 2026. No cloud resources were applied and no code or images were pushed.

| Check | Result |
| --- | --- |
| Python integration/unit suite | 38 passed |
| TypeScript strict check | Passed |
| Expo production web export | Passed |
| Expo iOS/Android Hermes bundle exports | Passed for both platforms; not a signed native build or device test |
| Terraform 1.13.5 + Google / Google beta 6.50.0 | `fmt` and `validate` passed; no plan/apply |
| Helm 3.19 template rendering | 27 resources with collector off; 28 with collector on |
| Docker Compose | Configuration validated; containers not started because Docker daemon was unavailable |
| Optional GCP/Dataflow dependencies | pip dry-run resolved successfully; managed Dataflow execution not tested |
| Public/secret boundary | No phone hashes in public listings; ES stays ClusterIP; `/internal` excluded from ingress |

## Browser checks

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

- Live Otodom/OLX/Gratka/Morizon collection, since no approved access/feed was supplied.
- Production PostgreSQL/Elasticsearch container integration, GCP permissions/quotas, TLS issuance, Cloud SQL grants and Cloud CDN behavior.
- A real Dataflow streaming job or Spot interruption/recovery.
- Signed iOS/Android apps, native map credentials, physical-device behavior or app-store delivery.
- Load capacity, a 30-day 95% availability result, backup restoration or production security certification.

The [feature ledger](feature-status.md) identifies further product scope, including the advertiser platform and notification delivery. This verification record should not be interpreted as complete Otodom parity or production acceptance.
