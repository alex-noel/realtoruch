# Scope and parity ledger

“All features of Otodom” is a much larger product than an aggregation/search release. This implementation is a runnable foundation, not complete Otodom parity. This ledger makes the boundary explicit.

| Requested area | Implemented | Still required for live production / full parity |
| --- | --- | --- |
| Otodom, OLX, Gratka, other sources | Live Kraków/Warsaw samples from Otodom, Gratka and Morizon; verified OLX public-page parser and one manually captured/imported live offer; feed/JSON-LD adapters | Automatic OLX HTTP access still returns 403; wider geography/categories, exhaustive coverage and markup-change monitoring |
| Active offers | Explicit status, city-scoped oldest-first rechecks, freshness budgets, concurrent providers, durable local run health, leases, backoff and stale-to-unknown policy; three successful bounded live cycles | Multi-day monitoring; real removal-event validation; cloud jobs still report through logs rather than the local SQL health tables |
| Deduplication and cleanup | Conservative matching, same-portal reposts, Morizon–Gratka identity, normalized street/unit and image URL variants; moderator merge/split with audit, aliases and preserved saved/seen state | Perceptual image hashing, address geocoding, broader accuracy evaluation |
| Maps and lists | Interactive Leaflet web map; native map component; responsive cards and pagination | Licensed production map tiles; Android maps key; native device QA |
| Direct/agency and fees | Independent advertiser, commission and risk filters; unknown fees kept unknown; moderation appeals for first-party adverts | Verification that a declared private advertiser really is the owner |
| Historical prices | Observation history, city/district/region medians, charts and sample sizes | Long-running real observations (current live history starts with collection); representative index methodology if desired |
| Reused contacts | Private keyed fingerprints, distinct-property counts, 90-day policy | Production retention/rights workflow and operational key rotation |
| Suspicious adverts | Explained heuristics, user reports, moderator hide/restore/dismiss, audited decisions and advertiser appeals | Staffed fraud review, image/content classifiers, abuse escalation and operating policy |
| Rental search features | City, text, district, price, rooms, area, property type, amenity, advertiser, fees, risk, sort, bounding box and validated drawn polygons | Commute times, more structured fields, transit/school layers |
| Listing details | Gallery, features, source comparisons, price observations, fee breakdown | Floorplans, videos/3D tours, richer building data supplied by feeds |
| Accounts | Separate auth, verification and recovery email links, rotating refresh tokens/replay rejection, HttpOnly web cookies/SecureStore, session revocation, retryable account deletion; isolated saved/seen/search data | Real email-provider delivery, social sign-in, production security review |
| Alerts | Durable inbox, confirmed email opt-in/unsubscribe, SMTP delivery/retries, local mail previews, duplicate suppression, liked-home price drops; optional Web Push and Expo delivery queues | Production SMTP/sender credentials and deliverability checks; real browser/device push delivery and Expo credentials |
| Free public API | Anonymous bounded read endpoints, OpenAPI docs, public search, rate limiting | Production host, dataset redistribution rights, published quotas/support policy |
| Advertiser platform | Owner/agency profiles, draft/publish/edit/withdraw, map pinning, HTTPS photo URLs, private inbox/replies/read state, message retry deduplication and blocking | Media upload/storage, richer CRM, billing, promoted placements, subscriptions and integrations; messages currently have no email alerts |
| Other Otodom products | Not included | Sales, new developments, commercial categories, editorial content and financing tools |
| Operations | Repeatable local collection and loopback load checks; SQLite and disposable PostgreSQL backup/restore rehearsals; native prerequisites report; PostgreSQL/Elasticsearch integration checks | Extended load/availability measurements, Cloud SQL point-in-time recovery and physical-device acceptance |
| Cloud (excluded from this continuation) | Terraform + Helm + Docker Compose + Dataflow entry point, auth job worker and SQL migrations/grants | Deployment, credentials, SQL bootstrap, real TLS certificates and cloud disaster-recovery drills; nothing provisioned or pushed |

Real records link to their source listing pages. Demo source links open portal homepages, not invented listing URLs. Demo photos are illustrative Unsplash images and do not depict verified rental offers. The sample data is only loaded by an explicit development command and is labelled throughout the UI and API.
