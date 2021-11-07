# Scope and parity ledger

“All features of Otodom” is a much larger product than an aggregation/search release. This implementation is a runnable foundation, not complete Otodom parity. This ledger makes the boundary explicit.

| Requested area | Implemented | Still required for live production / full parity |
| --- | --- | --- |
| Otodom, OLX, Gratka, other sources | Configurable feed adapter, JSON-LD adapter, four disabled source profiles, source links | Contracted feed/API access; each provider's real payload mapping and completeness validation |
| Active offers | Explicit status, per-source timestamps, scheduled rechecks, stale-to-unknown policy | Live provider fixtures and monitoring |
| Deduplication and cleanup | Canonical property model, conservative matching, cleaned text, retained source evidence | Image perceptual hashing, address geocoding, human merge/split tooling |
| Maps and lists | Interactive Leaflet web map; native map component; responsive cards and pagination | Licensed production map tiles; Android maps key; native device QA |
| Direct/agency and fees | Independent advertiser, commission and risk filters; unknown fees kept unknown | Verified advertiser identity and appeals workflow |
| Historical prices | Observation history, city/district/region medians, charts and sample sizes | Long-running real observations; representative index methodology if desired |
| Reused contacts | Private keyed fingerprints, distinct-property counts, 90-day policy | Production retention/rights workflow and operational key rotation |
| Suspicious adverts | Explained heuristic signals and user reports | Moderation console, fraud review, image/content classifiers, appeals |
| Rental search features | City, text, district, price, rooms, area, property type, amenity, advertiser, fees, risk, sort and bounding box | Draw-on-map searches, commute times, more structured fields, transit/school layers |
| Listing details | Gallery, features, source comparisons, price observations, fee breakdown | Floorplans, videos/3D tours, richer building data supplied by feeds |
| Accounts | Separate auth service, registration/login, secure native token storage, account-isolated favorites/searches | Email verification, password reset, refresh/revocation, account deletion, social sign-in |
| Alerts | Saved queries and new-match counts in the app | Email/push delivery and unsubscribe/preferences flows |
| Free public API | Anonymous bounded read endpoints, OpenAPI docs, public search, rate limiting | Production host, dataset redistribution rights, published quotas/support policy |
| Advertiser platform | Not included | Posting/editing own adverts, agency profiles, advertiser CRM/inbox, billing, promoted placements, subscriptions and integrations |
| Other Otodom products | Not included | Sales, new developments, commercial categories, editorial content and financing tools |
| Cloud | Terraform + Helm + Docker Compose + Dataflow entry point | Deployment, credentials, SQL bootstrap, real TLS certificates, load tests and disaster recovery drills |

Demo source links open portal homepages, not invented listing URLs. Photos are illustrative Unsplash images and do not depict verified rental offers. The sample data is only loaded by an explicit development command and is labelled throughout the UI and API.
