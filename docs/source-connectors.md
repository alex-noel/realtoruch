# Connecting listing sources

All source profiles are disabled initially. The user does not yet have API/feed access. The app does not claim to pull live marketplace-wide data, and it does not scrape undocumented APIs or bypass access controls.

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

The worker loads the previous source record from local SQL or the private Bigtable state row, so a confirmed 404/410 can emit an inactive observation without inventing missing property fields. A 403, 429, timeout, malformed page or parser failure preserves previous state and fails the job. The job can retry; idempotent ingestion absorbs duplicate observations. This is a conservative baseline and must be verified against each source's real markup. The portals' current production markup and removal behavior have not been validated with access credentials.

## Extending sources

Add a new disabled source profile and a mapping from a contracted supplier format to `RawListing`. Keep discovery, pagination, normalization and status evidence separate. Add sanitized real fixtures and tests for active, updated, removed, throttled and unavailable responses. Do not use phone fingerprints as property identity without property evidence. Preserve original URLs and per-source terms in the public item.

For a local check with non-demo data:

```sh
DEMO_MODE=false CONNECTORS_CONFIG=config/sources.json .venv/bin/python -m realtoruch.worker migrate
DEMO_MODE=false CONNECTORS_CONFIG=config/sources.json .venv/bin/python -m realtoruch.worker collect
```

Use a separate database from the sample catalog. The production collector uses `--cloud`, writing sanitized observations to Bigtable then Pub/Sub. Dataflow handles canonical SQL writes.
