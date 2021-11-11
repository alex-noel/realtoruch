# Connecting listing sources

The default demo profiles in `config/sources.json` remain disabled. The separate `config/sources.live.json` enables bounded public-page collection for Otodom, Gratka and Morizon in Warszawa. OLX stays disabled after an HTTP 403 response from its robots endpoint in the tested environment. No complete OLX portal parser is included. There is no claim of marketplace-wide coverage.

## Portal mode

Run `make collect`, then `make live` to open real results. The collector uses normal HTTPS requests and source HTML already delivered to public pages, with no browser automation or hidden API requests.

| Source | Discovery | Detail mapping | Current boundary |
| --- | --- | --- | --- |
| Otodom | `__NEXT_DATA__` rental search items and pagination | `ad` state: identity/status, transaction, rent, fees, deposit, location, advertiser, photos | Public phone-reveal operations are not performed; absent numbers stay absent |
| Gratka | Rental `AggregateOffer` JSON-LD and next-page link | Nuxt reference-table `propertyData` | The configured city must appear explicitly in the location hierarchy |
| Morizon | Rental `AggregateOffer` JSON-LD and next-page link | Nuxt reference-table `propertyData` | Same city check; shared Morizon–Gratka listing identity supports cross-post matching |
| OLX | Disabled | Generic feed/JSON-LD adapters only | Needs accessible source markup/feed and a verified source mapper |

Configuration fields for `mode: portal`:

- `search_urls`: up to ten explicit search seeds; no guessed search URLs or hidden endpoints.
- `listing_urls`: optional specific detail URLs.
- `city`: verified city scope (required by Gratka/Morizon mapping).
- `max_pages`: total discovery-page budget per source/run, capped at ten.
- `max_listings`: new-detail request budget, capped at 500.
- `max_rechecks`: separate oldest-first budget for stored adverts, capped at 500.
- `requests_per_minute`, `allowed_hosts` and optional descriptive `user_agent` control requests.

`--source` selects a configured source without enabling a disabled one. CLI `--max-pages`, `--max-listings` and `--max-rechecks` override budgets. `--recheck-only` skips discovery and refreshes the stored catalog. These budgets are deliberately small by default; `limited: true` in a report means the result is not exhaustive. Increase scope only through reviewed source-specific URLs and request limits. A page returning an unexpected structure is an error, not proof that it contains zero adverts.

Robots policies use Protego so wildcard rules, the longest matching allow/disallow rule and repeated user-agent groups are handled. Both crawl delay and request rate are respected. Unavailable robots, access denial and HTTP 429 stop the source; no credential/proxy rotation is implemented. A malformed detail page is isolated so other records can finish, but the run is marked partial/failed. HTTP redirects are rejected rather than followed automatically. Robots restrictions can stop pagination before the configured budget.

Amounts use whole PLN, rounded half up; area accepts Polish decimal commas. Required rent/area/room fields are validated. Structured fees take precedence. A fallback reads only explicitly labelled PLN/zł amounts in the description; conflicting, percentage-based or relative fees remain unknown. Only complete phone numbers already embedded in the public contact data are fingerprinted. Raw numbers are discarded before SQL, Bigtable and Pub/Sub persistence.

Gratka and Morizon share an internal listing ID. It is kept as private `syndication_key` evidence and can merge cross-posts only with matching city, street, rooms and area and no conflicting floor/location evidence. It is never returned by the public API. Other deduplication still requires the conservative property/contact/image evidence described in the architecture.

## Rechecks and reporting

Local collection queries stored active/unknown adverts in oldest-observation order, independently of current discovery results. Cloud collection uses a Bigtable `recheck#source#observed_at#url_hash` index. Successful publication creates the new queue entry and state before removing the old queue entry; stale orphan entries are cleaned when read. Raw observations are written before Pub/Sub, but state does not advance if publication fails. The queue contract is unit-tested with fake clients; actual Bigtable/Pub/Sub/Dataflow behavior remains a deployment validation task. There is no general raw-event replay daemon yet.

A verified 404/410 or explicit unavailable detail status emits an inactive observation only when a previous valid record exists. Timeouts, malformed pages, blocked requests and disappearance from search results never become inactive observations. Another active source keeps the canonical home active. Inactive adverts can reappear through discovery. In local loop mode partial runs are reported and the worker waits until the next six-hour interval; one-shot mode exits nonzero so CronJobs can retry.

The JSON report records source, started/finished timestamps, search pages, discovered URLs, checked/emitted/ingested counts, skipped records, inactive observations, budget limits and error class/status. Error locations are URL hashes; raw payloads and contacts are not logged. `/v1/sources` exposes stored real-advert counts and latest observation timestamps, not an assertion that the latest collector run succeeded. Reports live in `.local/last-collection.json` locally and structured application logs in cloud jobs.

## Feed contract

The generic feed adapter accepts either a JSON array of `RawListing` objects or `{ "items": [...], "next_url": "https://approved-host/next-page" }`. Every next page must be on an explicitly allowed HTTPS host. Pagination is bounded to 100 pages and 5 MB per page. Fields and validation are defined in `backend/realtoruch/schemas.py`. Required fields are source identity, URL, title, city, area, rooms and base rent. Use `null` for unknown fees or commission. Amounts currently use whole PLN, not grosz.

```json
{
  "items": [{
    "external_id": "supplier-123",
    "url": "https://approved-portal.example/rentals/supplier-123",
    "title": "Two-room apartment",
    "description": "Description supplied by the advertiser.",
    "city": "Warszawa",
    "district": "Mokotów",
    "region": "mazowieckie",
    "address": "Example street 12",
    "lat": 52.2,
    "lon": 21.0,
    "area_m2": 54,
    "rooms": 2,
    "floor": 3,
    "rent_pln": 3400,
    "fees_pln": 650,
    "commission_pln": 0,
    "advertiser_type": "private",
    "status": "active",
    "amenities": ["balcony", "furnished"],
    "images": [],
    "observed_at": "2026-11-07T10:00:00Z"
  }],
  "next_url": null
}
```

After obtaining source access, edit the corresponding entry in `config/sources.json`: set its approved `feed_url`, exact `allowed_hosts`, `token_env` and `enabled: true`. Store the bearer token in the referenced environment variable, never in the URL or tracked JSON. Source `name` overrides the incoming item; demo status is forcibly false. The adapter uses a bounded timeout, source-specific pacing, rejects private/loopback DNS results and redirects, and never forwards bearer tokens to page fetches. Provider payloads that differ from this schema require an explicit mapping adapter; no provider-specific bulk API format is invented here.

Feeds must provide their observation timestamp or represent a fresh check. Replaying a cached response with an old timestamp does not refresh a property. A missing item is not a removal; feed deletions must be explicit `status: inactive` observations with a newer timestamp. The default Helm collector runs every six hours. Change its schedule for the permitted source refresh rate.

## JSON-LD mode

`mode: jsonld` accepts an explicit `listing_urls` list. It checks robots.txt and respects its crawl delay in addition to configured pacing. Robots permission alone is not a data license. The parser handles `Apartment`, `House`, `Residence` and `RealEstateListing` records, including `@graph`, and requires explicit PLN and rental semantics (`LeaseOut` or a monthly price unit). It refuses to guess prices, rooms, area, or whether an offer is a sale.

The worker loads the previous source record from local SQL or the private Bigtable state row, so a confirmed 404/410 can emit an inactive observation without inventing missing property fields. A 403, 429, timeout, malformed page or parser failure preserves previous state and fails the job. The job can retry; idempotent ingestion absorbs duplicate observations. Generic JSON-LD mode remains a conservative baseline. Portal mode uses the source-specific parsers above. Real removal events have not been independently observed during the small live check; removal behavior is covered by fixtures and mocked HTTP responses.

## Extending sources

Add a new disabled source profile and a mapping from a contracted supplier format to `RawListing`. Keep discovery, pagination, normalization and status evidence separate. Add sanitized real fixtures and tests for active, updated, removed, throttled and unavailable responses. Do not use phone fingerprints as property identity without property evidence. Preserve original URLs and per-source terms in the public item.

For a local check with non-demo data:

```sh
DEMO_MODE=false CONNECTORS_CONFIG=config/sources.json .venv/bin/python -m realtoruch.worker migrate
DEMO_MODE=false CONNECTORS_CONFIG=config/sources.json .venv/bin/python -m realtoruch.worker collect
```

Use a separate database from the sample catalog. The production collector uses `--cloud`, writing sanitized observations to Bigtable then Pub/Sub. Dataflow handles canonical SQL writes.
