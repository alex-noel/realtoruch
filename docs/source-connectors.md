# Connecting listing sources

The default demo profiles in `config/sources.json` remain disabled. The separate `config/sources.live.json` enables bounded public-page collection for Otodom, Gratka and Morizon in Kraków and Warszawa. OLX's public-page parser is verified, but its automatic HTTP transport stays disabled after 403 responses. There is no claim of marketplace-wide coverage.

## Portal mode

Run `make collect`, then `make live` to open real results. The collector uses normal HTTPS requests and source HTML already delivered to public pages, with no browser automation or hidden API requests.

| Source | Discovery | Detail mapping | Current boundary |
| --- | --- | --- | --- |
| Otodom | `__NEXT_DATA__` rental search items and pagination | `ad` state: identity/status, transaction, rent, fees, deposit, location, advertiser, photos | Public phone-reveal operations are not performed; absent numbers stay absent |
| Gratka | Rental `AggregateOffer` JSON-LD and next-page link | Nuxt reference-table `propertyData` | The configured city must appear explicitly in the location hierarchy |
| Morizon | Rental `AggregateOffer` JSON-LD and next-page link | Nuxt reference-table `propertyData` | Same city check; shared Morizon–Gratka listing identity supports cross-post matching |
| OLX | Public rental-card links and next-page link; automatic transport disabled | Public JSON-LD offer + rendered property parameters + location breadcrumbs/map link | Verified on one browser-readable Kraków listing without login; scheduled HTTP/robots requests still return 403. No phone reveal or hidden API calls |

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

### Offline parser contract

Otodom discovery requires an explicit rental `items` array and valid page counters for the requested page. Gratka and Morizon require a rental `AggregateOffer` with an explicit `offers` array. In those shapes, a consistent empty array confirms zero results. A missing array, an unfamiliar same-provider result link or a nonempty aggregate without a recognized listing fails discovery. OLX requires known rendered listing links because the empty-result shape is unverified. Next links stay on the same HTTPS search host and path. Known page-level challenge or consent interstitials fail before any embedded state is used.

Base rent requires PLN and one unambiguous amount. The parsers accept decimal commas, decimal points and space-grouped thousands, including nonbreaking spaces. Amounts round half up to whole PLN. Area retains its decimal fraction. An absent or inexact room count rejects the detail. Otodom and OLX verify the listing city against the configured scope when supplied. Gratka and Morizon require the configured city in the Polish location hierarchy. Advertiser type reflects declarations in the mapped fields. A private declaration leaves commission unknown unless a separate amount is available.

Structured fees take precedence. An ambiguous or unsupported structured amount stays unknown. For absent structured amounts, a fallback reads explicitly labelled PLN or zł amounts in the description. Conflicting, ranged, percentage-based or relative fees remain unknown. Only complete phone numbers already embedded in the public contact data are fingerprinted. Raw numbers are discarded before SQL, Bigtable and Pub/Sub persistence.

The [offline fixture matrix](../backend/tests/fixtures/portals/README.md) lists the supported shapes, synthetic changes and provenance. Other frameworks, altered listing URL formats, unverified OLX empty pages and unsupported status values fail closed. Alternate challenge markup may be reported as unrecognized. This matrix uses no fresh provider requests and does not establish whether the synthetic empty or removal shapes still occur in live pages.

Gratka and Morizon share an internal listing ID. It is kept as private `syndication_key` evidence and can merge cross-posts only with matching city, street, rooms and area and no conflicting floor/location evidence. It is never returned by the public API. Other deduplication still requires the conservative property/contact/image evidence described in the architecture.

## Rechecks and reporting

Local collection queries stored active/unknown adverts in oldest-observation order, independently of current discovery results. Cloud collection uses a Bigtable `recheck#source#observed_at#url_hash` index. Successful publication creates the new queue entry and state before removing the old queue entry; stale orphan entries are cleaned when read. Raw observations are written before Pub/Sub, but state does not advance if publication fails. The queue contract is unit-tested with fake clients; actual Bigtable/Pub/Sub/Dataflow behavior remains a deployment validation task. There is no general raw-event replay daemon yet.

A verified detail HTTP 404/410 or explicit unavailable detail status emits an inactive observation only when a previous valid record exists. HTML removal must identify the requested URL and match the stored external ID. Otodom uses an inactive, expired or removed ad status or its explicit expiry flag. Gratka and Morizon use an archived presentation or embedded 404/410. OLX requires `OutOfStock` or `Discontinued` plus a matching Product URL and SKU. An OLX availability flag without URL identity fails closed. Timeouts, malformed pages, blocked requests and disappearance from search results never become inactive observations or advance the prior observation timestamp. Another active source keeps the canonical home active. Inactive adverts can reappear through discovery. In local loop mode partial runs are reported and the worker waits until the next six-hour interval; one-shot mode exits nonzero so CronJobs can retry.

The JSON report records source, started/finished timestamps, search pages, discovered URLs, checked/emitted/ingested counts, skipped records, inactive observations, budget limits and error class/status. A portal parser error adds a fixed `code` alongside the existing `discovery` or `detail` stage. Discovery uses `unsupported_url`, `unrecognized_page`, `access_challenge`, `invalid_pagination` or `not_rental`. Detail errors use `unsupported_url`, `unrecognized_page`, `access_challenge`, `invalid_fields`, `invalid_amount`, `unsupported_currency`, `identity_mismatch` or `invalid_location`. An explicitly non-rental detail increments both `skipped` and `skip_reasons.not_rental` without failing the run. These report fields are additive. Error locations use URL hashes. Reports live in `.local/last-collection.json` locally and structured application logs in cloud jobs. They exclude raw markup, URLs, contacts and exception messages.

The local SQL collector records `collection_runs` and `source_poll_state`. A compare-and-set lease prevents two local jobs fetching the same provider at once. A lease expires after 30 minutes without a heartbeat; source failures back off from 15 minutes to six hours. `/v1/sources?city=Kraków` includes sanitized health/status and retry timing as well as stored counts/freshness. Run history expires after 90 days. These SQL coordination records are not yet wired into the cloud collector, which has no SQL identity; its CronJob and structured logs remain the cloud coordination/health boundary.

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

## City budgets and freshness

The live configuration defaults to Kraków and includes explicit `search_urls_by_city` entries for Kraków and Warszawa. Select one using `make collect ARGS="--city Kraków"`; unsupported enabled portal/city combinations fail before collection. `--workers 1|2|3` controls concurrent providers, not concurrent requests to the same portal. The default is three. Each source retains its own robots checks, HTTP client and six-requests/minute pace.

`recheck_interval_minutes` defaults to 360 in the live profiles. Both SQL and the Bigtable recheck queue scope by city and prefer older due records. Fresh discoveries are skipped before consuming the new-listing budget; `fresh_skipped` reports those decisions. `--force-rechecks` explicitly overrides freshness. `--recheck-only` performs no discovery, and a fully fresh catalog can complete with zero outbound requests. Concurrent source failures remain isolated and included in the combined report.

The Bigtable queue key now includes the folded city before the observation timestamp. If upgrading an already populated older cloud queue, rebuild its recheck rows from the retained state payloads before relying on city-scoped scheduled rechecks. No such deployed queue exists in this local verification.

On 11 November 2026, the initial two bounded Kraków runs collected 18 adverts per provider. Three additional reliability cycles, each bounded to two new details per provider, all succeeded and added 18 observations; fresh results were skipped. The final live catalog contains 66 canonical homes, 89 source adverts and 112 observations across Kraków and Warszawa, including one manually imported OLX offer. These short checks are not multi-day reliability or exhaustive coverage evidence.

## OLX browser snapshot import

The ordinary public OLX search and listing page were readable in Chrome without an account. Its visible JSON-LD, parameters and map link supplied rent, fees, area, rooms, declared advertiser type, city/district and an approximate location. The parser requires explicit rental/PLN semantics and required fields; it does not invent unknown room counts, address or phone numbers. Its search/detail regression fixtures are synthetic shapes based on that observation.

An operator can save a freshly viewed public detail page and import it without network requests:

```sh
.venv/bin/python scripts/import_html.py --source olx --city Kraków \
  --url 'https://www.olx.pl/d/oferta/ACTUAL-LISTING.html' \
  --html .local/olx-public-detail.html
```

The file must be at most 5 MB and less than 24 hours old. Its modification time becomes the observation timestamp; keep captures private and capture again before rechecking. This is a manual ingestion path, not a working scheduled scraper. Automatic robots/search requests still returned 403 on the same day. No OLX account, session cookies, proxy rotation or access-control bypass was used. Approved feeds or an accessible collection path are still needed for continuous OLX updates.
