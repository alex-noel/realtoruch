# Shared product and technical contracts

These contracts prevent workers from independently changing the meaning of rent, identity, “seen,” direct offers or email delivery. They are proposed sprint requirements grounded in the existing implementation. Any change must be reviewed by the integrator and reflected in the owning task/test before consumers proceed.

## Preserve the existing architecture

The project already uses Python/FastAPI/SQLAlchemy services and an Expo React Native application shared with web. Use the committed dependency locks and the repository's compatible Python 3.12 / Node 24 setup. Do not upgrade Expo/React/RN, replace the stack or add another frontend as incidental work.

Local verification exercises SQL ingestion and workers. Cloud configuration models the source capture → Bigtable/raw archive + Pub/Sub → Dataflow processing → Cloud SQL path, with indexing and alerts downstream. Keep events backward compatible and use fake cloud clients for local contract tests. A passing fake-client test does not prove deployed Dataflow/Bigtable behavior.

REST, auth, search, collection/index/delivery workers keep their service boundaries. SQL is authoritative for canonical/current account state; Elasticsearch is a derived search projection. Public search is the application search service, not unrestricted Elasticsearch access. Databases and internal diagnostics remain private.

## Search and cost semantics

Use the existing `SearchFilters` contract in `backend/realtoruch/schemas.py`:

```json
{
  "city": "Kraków",
  "property_type": "apartment",
  "max_price": 5000,
  "max_price_exclusive": true,
  "min_area": 50,
  "advertiser": "private",
  "no_commission": false,
  "hide_suspicious": false,
  "polygon": "[[19.90,50.02],[20.02,50.02],[20.02,50.10],[19.90,50.10]]",
  "page": 1,
  "page_size": 24
}
```

The rectangle is a synthetic acceptance-test area, not a recommendation about Kraków neighborhoods.

- Price means advertised **base monthly rent in PLN**. Exactly 5,000 is excluded when `max_price_exclusive=true`. Area 50.0 is included; 49.9 is excluded.
- Monthly fees, utilities, deposits and commission remain separate fields. Unknown is null/unknown, never silently zero. A “total” field must disclose omitted unknown charges.
- `advertiser=private` reflects the normalized declared/inferred classification; it is not proof of legal ownership. Suspicious-agent indicators must remain explained, reviewable and separate from source declarations.
- `no_commission=true` requires a known zero commission. It is independent from direct/agency. A direct listing with unknown commission may satisfy “direct” but must not satisfy “known zero commission.”
- City spelling normalization, apartment type, amenities, district, rooms, sort and other existing filters remain supported.
- Public discovery includes active, visible canonical properties only. Saved lists can retain inactive/delisted properties. Moderator-hidden content follows existing restricted-detail rules and must not leak through a stale index.
- Structured filters agree between SQL and ES. Text relevance can differ and must be documented. Static pagination sorts have a canonical-ID tiebreaker; do not promise snapshot-stable pages while concurrent data changes.

Polygon coordinates are **[longitude, latitude]**, WGS84 degrees. Preserve the existing simple ring validation: 3–64 distinct vertices, optional repeated closing point, no self-intersection, finite ranges, no invalid/degenerate geometry. The SQL contract includes boundary points. T12/T18 verify ES agreement. If a location is approximate, the point is a representative coordinate; do not imply a precise apartment location.

## Identity and listing state

A source listing is not a canonical home. Crossposts and later source IDs can refer to the same property. Canonical identity must survive updates, aliases and justified merge/split corrections.

Do not merge solely because a phone/agency, city centroid, stock image or similar title matches. Conflicting known unit/floor/address evidence is a strong negative signal. T09 freezes labelled evaluation data before T10 changes matcher behavior.

Network timeout, 403/429, challenge HTML, parser drift or a missing search-page result is not proof of delisting. An inactive observation requires explicit supported removal evidence. Preserve the existing stale-to-unknown policy and exclude nonactive discovery entries without destroying historical/favorite records.

A removal from one portal does not deactivate a property still active on another source. Unchanged checks should advance freshness with at most one unchanged checkpoint per source/day; every actual rent/status change remains represented. Replays remain idempotent.

Manual correction must preserve aliases, seen prices, favorites, favorite price floors, source histories and genuine pending alerts, while avoiding spurious “new home” alerts caused only by identity correction. Moderator actions remain auditable and do not expose private audit reasons in public DTOs.

## Canonical eight-step acceptance sequence

Use synthetic data and a local file mail transport. Match notifications by kind/logical event ID; account-verification and opt-in-confirmation emails are separate from the rental-alert count.

| Stage | Action / data | Expected state | Incremental rental alerts |
| --- | --- | --- | ---: |
| Setup | Existing matching H0, then save the filter/polygon and confirm email | H0 becomes a silent search baseline | 0 |
| New result | Ingest H1, private apartment, 55 m², 4,500 PLN, inside area | One active canonical H1 appears on map/list | 1 new_match |
| Open | Open H1 detail | H1 is marked seen for the user and price | 0 |
| Like | Favorite H1 | Saved list contains H1; floor is 4,500 | 0 |
| Remove | Explicitly remove every active source for H1 | H1 leaves discovery/map, remains saved as delisted | 0 |
| Same-price repost | New source ID strongly matches H1 at 4,500 | Same canonical H1, seen/favorite preserved | 0 |
| Lower-price relist | Delist/relist H1 at 4,200 | Same H1; favorite floor becomes 4,200 | 1 price_drop |
| Final delist | Explicitly remove all active sources again | H1 remains saved with history; no discovery pin | 0 |

Expected rental-alert total: **two logical events**. A lower price that matches both a favorite and a new search must not produce duplicate user-facing new-match/drop notifications for the same event. Replaying any observation/job does not add a logical event.

Favorites track the lowest already-accounted-for price while favorited. A bounce from 4,200 to 4,500 and back to 4,200 is not a new lower-price event. Identity correction preserves this floor. Do not reset it merely because a source ID or canonical alias changes.

HTTP reads do not generate alerts. Opening detail records seen through the authenticated seen-state action; public detail retrieval alone is not a user identity signal.

## Durable work, indexing and transport

Collector claims and delivery attempts need fencing tokens: a stale owner cannot acknowledge, retry, clear or resurrect a newer claim. An already-running external HTTP/SMTP request may complete after lease loss; its result/ack must be safely fenced. No task can guarantee it unsends bytes already accepted by an external server.

A SQL transaction owns canonical changes plus corresponding outbox/revision events. Use short transactions for claims/acknowledgements; external network I/O must not hold long-lived canonical locks.

T08 uses a positive monotonic revision and strict external Elasticsearch versioning. Bulk requests require per-item success/failure handling. Inactive/hidden/merged tombstones preserve version ordering. REST discovery rechecks current SQL visibility; direct search remains explicitly eventually consistent.

Email guarantees logical event uniqueness and bounded retries. SMTP acceptance followed by a crash before acknowledgement can still produce duplicate physical delivery. Keep Message-IDs stable and document ambiguity instead of promising exactly-once email. Email is the chosen closed-app channel; optional native/web push does not substitute for its acceptance.

Account erasure remains retryable even when mail is disabled or failing. Account closure must serialize with writes so an already-authenticated request cannot recreate favorites/messages/subscriptions after cleanup.

## Interfaces owned by this sprint

| Interface | Producer | Consumer / rule |
| --- | --- | --- |
| Isolated run env, reports and migration registry | T01 | All workers; real services may not silently skip |
| Shared frontend unit-test runner | T14 | T17/T19/T21/T24; one compatible runner |
| Revisioned public search projection | T08 | T10/T11/T12/T25; use monotonic revisions on every public change |
| Public DTO allowlists and degradation metadata | T12 | UI and anonymous API clients; never forward unvalidated private fields |
| Attempt claim tokens | T13 | Email/push/auth workers; stale completion is a no-op |
| Account closure and export-purpose reauthentication | T15 | Every account write; export only own allowed data |
| `PUT /v1/me/conversations/{id}/read` body `{last_message_id}` | T16 | T17; last displayed tuple, not “now” |
| Conversation pagination and conflicting client-message-ID behavior | T16 | T17; static order documented, reused ID/different body returns 409 |
| Typed allowlisted incoming-link actions | T21 | App startup, email and push routing; no arbitrary URL fetch |
| Owned ready media IDs | T23, optional | T24; local previews/pending assets are not stored public photos |

Additive changes keep existing v1 callers working where specified. Document error codes and fixture examples before the consuming worker starts. Do not create a second API because a dependency has not landed.

## Data, privacy and historical statistics

Public listing/search/health/history responses expose an explicit allowlist. Never expose raw phones, HMAC fingerprints, account emails, cookies/tokens, drafts, delivery payloads, private message bodies or private moderator notes. Metrics labels must have bounded cardinality; identifiers belong only in redacted diagnostic context where necessary.

Own-data export is password-reauthenticated, account-scoped, bounded and no-store. It excludes other participants' private messages and all security tokens/hashes. Do not email exports or make public download URLs.

Price history is observed advertised rent, not signed leases or a complete census. T11 uses current UTC month plus N-1 previous calendar months. First take the latest observation for each source/month, then consider active sources and choose one latest active price per canonical home/month. Keep sample sizes; never interpolate unobserved months. Preserve the documented limitation that price-per-m² uses the current known canonical area unless a separately reviewed historical-area model is added.

A shared phone fingerprint or heuristic is evidence for a reviewable risk flag, not proof of fraud. Key rotation and retention remain private operational concerns. Engineering controls do not constitute a legal-compliance certification or rights to redistribute third-party content.

## Evidence targets and nonclaims

Targets are planned acceptance conditions, **not achieved measurements**: >=72-hour source soak, 100-change indexing convergence <=30 s, SQL search p95 <=300 ms, ES-backed REST p95 <=250 ms, history p95 <=750 ms, summary p95 <=300 ms, main web JS <=650,000 bytes. Use the task's dataset/hardware/warm-up definition and retain failed targets as failed.

Reference documents used when defining the relevant tasks:
- [Elasticsearch Bulk API and external version handling](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk).
- [Expo incoming-link behavior and custom scheme builds](https://docs.expo.dev/linking/into-your-app/).
- [Playwright CI setup](https://playwright.dev/docs/ci).
- [OWASP upload validation/storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

Workers should verify version-specific details against the installed locks and current primary documentation when implementing. No framework upgrade or provider purchase is implied.
