# Free rental API, v1

Anonymous reads do not require a token or an account. The application publishes OpenAPI at `/openapi.json` and interactive docs at `/docs`. The public search route is an application endpoint that accepts the same filters as the REST catalog. Elasticsearch, SQL, index administration and raw search DSL are private.

Start with the canonical REST catalog. These examples use local service ports. In a hosted environment, use the published API origin for both routes; port 8002 is the local Compose search application.

```sh
API=http://localhost:8000
SEARCH=http://localhost:8002

curl -sS --get "$API/v1/listings" \
  --data-urlencode 'city=Kraków' \
  --data-urlencode 'property_type=apartment' \
  --data-urlencode 'max_price=5000' \
  --data-urlencode 'max_price_exclusive=true' \
  --data-urlencode 'min_area=50' \
  --data-urlencode 'advertiser=private' \
  --data-urlencode 'polygon=[[19.90,50.02],[20.02,50.02],[20.02,50.10],[19.90,50.10]]' \
  --data-urlencode 'sort=price_asc' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=24'

curl -sS --get "$SEARCH/v1/search" \
  --data-urlencode 'city=Kraków' --data-urlencode 'no_commission=true' \
  --data-urlencode 'page=2' --data-urlencode 'page_size=24'

curl -sS --get "$API/v1/market/history" \
  --data-urlencode 'city=Kraków' --data-urlencode 'months=6'
curl -sS --get "$API/v1/market/summary" --data-urlencode 'city=Kraków'
curl -sS --get "$API/v1/sources" --data-urlencode 'city=Kraków'
# Replace HOME_ID with an id from a response:
curl -sS "$API/v1/listings/HOME_ID"
```

## Filters and pages

- `page` is one-based and defaults to 1. `page_size` is 1–100 and defaults to 24. Both routes require `page * page_size <= 10000`. For example, page 100 at size 100 is valid; page 101 at that size is not. Narrow the filters to browse beyond that window. An in-window page past the last result returns an empty `items` array and the available count.
- `sort` accepts `newest` (default; first observed time descending), `price_asc`, `price_desc`, and `area_desc`. Equal primary values sort by ascending canonical home ID. Reuse the same filters, sort and size on adjacent pages. That ordering is stable on a static dataset; there is no snapshot across HTTP requests.
- Use `city`, `district`, `property_type=apartment|house|room|all`, `rooms=1..100`, and an exact `amenity` token. City and district labels compare without regard to ASCII case; retain the published spelling of accented labels. Common city aliases such as `Krakow` and `KRaków` resolve to `Kraków`. `hide_suspicious=true` selects homes with no current risk flags. Flags explain review signals; they do not establish fraud.
- `min_price` and `max_price` are base monthly rent in PLN, inclusive by default. `max_price_exclusive=true&max_price=5000` excludes exactly 5,000 PLN. `min_area=50` includes exactly 50 m²; `max_area` is also inclusive.
- `advertiser=private` reflects the normalized classification of the source offer and does not verify ownership. `no_commission=true` requires a known zero commission. A private offer with unknown commission still qualifies as private; an agency offer with a known zero commission qualifies for the commission filter.
- `bbox` is `west,south,east,north` with increasing coordinates. `polygon` is a JSON ring with 3–64 distinct vertices, optionally closed by repeating the first vertex. Coordinates are WGS84 `[longitude,latitude]`. Self-intersections and invalid or degenerate rings are rejected. Boundary points are included. Approximate locations are representative coordinates. If both bounds are provided, a listing must satisfy both.
- `q` is text, never search DSL. Elasticsearch uses analyzed word matching across title, address, district and description; SQL looks for a literal case-insensitive substring in title, address or district. Keyword matches and totals can change on fallback. The selected field and ID determine order on both engines.

## Freshness, counts and errors

A search response contains `items`, `total`, `page`, `page_size`, `engine`, `degraded`, `consistency` and `total_relation`:

| Route / state | Engine | Degraded | Consistency | Total relation |
| --- | --- | --- | --- | --- |
| REST with a usable search page | `elasticsearch` | `false` | `sql_checked` | `index` |
| REST falls back after search failure or a stale candidate | `postgresql` (or local `sqlite`) | `true` | `sql` | `exact` |
| REST is configured for SQL alone | `postgresql` (or local `sqlite`) | `false` | `sql` | `exact` |
| Direct application search | `elasticsearch` | `false` | `eventual` | `index` |

REST checks every candidate against current SQL at read time. The returned home must be active, visible and match the current structured filters; the card is rendered from SQL. If a candidate has become hidden, delisted, otherwise ineligible, or changed its selected sort value, REST rebuilds the requested page and count with SQL. An index total counts documents in the index, including possible stale entries outside the current page, and can miss newly added or updated homes until the index catches up. An exact total counts matching rows at the same SQL statement snapshot as the page.

Direct search only sees the index projection. Newly added homes can be absent, and a recently removed home can remain visible until its tombstone is indexed. T08 targets 100 committed changes searchable within 30 seconds on its reference environment. [Local synthetic runs](verification/T08-handoff.md) observed about 0.26–0.33 seconds with an immediate worker poll and forced refresh. These are measurements of that workload, with no production lag guarantee. The API does not emit an index-wide `as_of` or lag timestamp; neither can be inferred from an individual home's observation or update time.

```sh
# 422: page would cross the common result window.
curl -i "$API/v1/listings?page=101&page_size=100"

# 422: invalid ring (the edges cross).
curl -i --get "$SEARCH/v1/search" \
  --data-urlencode 'polygon=[[19.90,50.02],[20.02,50.10],[19.90,50.10],[20.02,50.02]]'
```

Invalid filter or pagination inputs return HTTP 422 and a `detail` array describing the invalid input. Hidden or missing detail returns HTTP 404 with `{"detail":"Home not found"}`. An unavailable direct search returns 503 with `{"detail":"Search is temporarily unavailable"}`. REST serves a degraded SQL page if search fails; if it cannot read SQL either, it returns 503 with `{"detail":"Rental catalog is temporarily unavailable"}`. Clients should treat 503 as an availability problem, not as a zero-match result.

The default development application limit is 120 requests per minute per IP per process. Its 429 response includes `Retry-After: 60` (seconds) and `{"detail":"Rate limit reached; try again shortly"}`. The production infrastructure configures a separate public edge throttle of 120 requests per minute per IP; an edge-generated 429 can have different headers or body. Honor `Retry-After` when present (seconds or HTTP date); otherwise back off with jitter rather than immediately retrying. Shared IP addresses share their quota.

## Response fields

These allowlists describe the v1 data contract. Clients should tolerate additive fields in future versions. SQL visibility and all index-response validation happen before public serialization.

| Object | Fields |
| --- | --- |
| Listing | `id`, `title`, `description`, `city`, `district`, `region`, `address`, `lat`, `lon`, `area_m2`, `rooms`, `floor`, `rent_pln`, `fees_pln`, `deposit_pln`, `commission_pln`, `total_monthly_pln`, `advertiser_type`, `property_type`, `status`, `amenities`, `images`, `risk_flags`, `risk_score`, `is_demo`, `first_seen`, `last_seen`, `updated_at`, `sources`, `contact_adverts` |
| Source advert (`sources[]` on a listing) | `name`, `url`, `rent_pln`, `fees_pln`, `commission_pln`, `advertiser_type`, `status`, `last_checked`, `match_reason` |
| Risk flag | `code`, `label`, `detail`, `severity` |
| Published app contact | `id`, `name`, `kind`, `profile_id` (public profile reference) |
| Listing detail | Listing fields plus `history[]` (up to 100 changed observations, each with `at`, `rent_pln`, `fees_pln`, `status`) |
| Market history | `city`, `district`, `region`, `methodology`, and `points[]` with `month`, `median_rent_pln`, `median_per_m2`, `sample_size`, `is_demo` |
| Market summary | `homes`, `source_listings`, `duplicates_removed`, `private_homes`, `median_rent_pln`, `demo`, `districts`, `cities` |
| Source health | `demo_mode` and `sources[]` with `name`, `enabled`, `mode`, `status`, `disabled_reason` (generic), `cadence_minutes` (nullable configured recheck interval), `last_observed_at`, `stored_adverts`, and nullable `health` |
| Collector health | `status`, `city`, `started_at`, `finished_at`, `ingested`, `checked`, `fresh_skipped`, `limited`, `errors[]` (up to 20, each with `kind`, `stage`, `http_status`), `consecutive_failures`, `last_success_at`, `retry_after` |

Timestamps in these payloads are UTC with a `Z` suffix. `rent_pln` is advertised base monthly rent; `fees_pln`, `deposit_pln` and `commission_pln` are separate. Unknown is `null`, including fees or commission the source did not disclose. `total_monthly_pln` is base rent plus known monthly fees and is null if those fees are unknown. It excludes deposits, commission and any utilities or other charges not included in the reported monthly fees.

Search excludes delisted and hidden homes subject to the freshness guarantees above. Detail can still show a visible delisted home and its observations; it returns 404 for moderator-hidden content. Listing cards include up to 100 source adverts and 100 published app contact references each. The API excludes phone fingerprints, raw contact fields, account email and tokens, drafts, private messages, moderator notes, delivery payloads and private source diagnostics. Public links omit URL fragments; links containing credentials are not published.

Provider health summarizes collection; it is not proof that a particular listing is available. The `city` parameter selects both collector health and stored advert totals/freshness for that city; omit it for the provider-wide view. `last_success_at` is the most recent completed, successful run in that scope which was not limited to a sample, or `null` if there is none. The latest attempt and its `limited` flag are reported separately. `consecutive_failures` and `retry_after` describe provider-wide backoff. `cadence_minutes` is a positive configured recheck interval from 1 to 10,080 minutes, or `null` if missing or invalid. Neither timestamp nor cadence guarantees portal coverage or that the collector ran on schedule.

Market history covers the current UTC calendar month and the preceding `months - 1` months (`months` is 1–120, default 12). Each month's latest observation per source is reduced to the latest active source for each visible canonical home. Rents are advertised observations and per-square-metre values use the current known home area. Small samples are shown as such; months with no observations are omitted. Demo samples are labelled. The catalog is an observed sample with incomplete coverage; these figures are not signed leases or a census.

The availability of this free endpoint does not grant redistribution rights for third-party listing text, photos, source links or other content. Before reusing or redistributing source material, check the relevant terms and obtain any required permission from the rights holder.
