# Scope and parity ledger

“All features of Otodom” is a much larger product than an aggregation/search release. This implementation is a runnable foundation, not complete Otodom parity. This ledger makes the boundary explicit.

| Requested area | Implemented | Still required for live production / full parity |
| --- | --- | --- |
| Otodom, OLX, Gratka, other sources | Live Kraków/Warsaw sample collection from Otodom, Gratka and Morizon; HTML discovery, pagination and detail mapping; generic feed/JSON-LD adapters | OLX is blocked (403) and lacks a verified portal parser; wider geography/categories, exhaustive coverage and markup-change monitoring |
| Active offers | Explicit status, per-source timestamps, city-scoped oldest-first rechecks, freshness budgets, concurrent providers, run reports, stale-to-unknown policy | Long-running monitoring; real removal-event validation |
| Deduplication and cleanup | Canonical property model, conservative matching, corroborated same-portal repost identity, Morizon–Gratka cross-post identity, cleaned text, retained source evidence | Image perceptual hashing, address geocoding, human merge/split tooling |
| Maps and lists | Interactive Leaflet web map; native map component; responsive cards and pagination | Licensed production map tiles; Android maps key; native device QA |
| Direct/agency and fees | Independent advertiser, commission and risk filters; unknown fees kept unknown | Verified advertiser identity and appeals workflow |
| Historical prices | Observation history, city/district/region medians, charts and sample sizes | Long-running real observations (current live history starts with collection); representative index methodology if desired |
| Reused contacts | Private keyed fingerprints, distinct-property counts, 90-day policy | Production retention/rights workflow and operational key rotation |
| Suspicious adverts | Explained heuristic signals and user reports | Moderation console, fraud review, image/content classifiers, appeals |
| Rental search features | City, text, district, price, rooms, area, property type, amenity, advertiser, fees, risk, sort, bounding box and validated drawn polygons | Commute times, more structured fields, transit/school layers |
| Listing details | Gallery, features, source comparisons, price observations, fee breakdown | Floorplans, videos/3D tours, richer building data supplied by feeds |
| Accounts | Separate auth service, registration/login, secure native token storage, account-isolated favorites/searches/seen history; delisted favorites retained | General account email verification, password reset, refresh/revocation, account deletion, social sign-in |
| Alerts | Durable inbox, confirmed email opt-in/unsubscribe, SMTP delivery/retries, local mail previews, duplicate suppression, liked-home price drops; optional Web Push and Expo delivery queues | Production SMTP/sender credentials and deliverability checks; real browser/device push delivery and Expo credentials |
| Free public API | Anonymous bounded read endpoints, OpenAPI docs, public search, rate limiting | Production host, dataset redistribution rights, published quotas/support policy |
| Advertiser platform | Not included | Posting/editing own adverts, agency profiles, advertiser CRM/inbox, billing, promoted placements, subscriptions and integrations |
| Other Otodom products | Not included | Sales, new developments, commercial categories, editorial content and financing tools |
| Cloud | Terraform + Helm + Docker Compose + Dataflow entry point | Deployment, credentials, SQL bootstrap, real TLS certificates, load tests and disaster recovery drills |

Real records link to their source listing pages. Demo source links open portal homepages, not invented listing URLs. Demo photos are illustrative Unsplash images and do not depict verified rental offers. The sample data is only loaded by an explicit development command and is labelled throughout the UI and API.
