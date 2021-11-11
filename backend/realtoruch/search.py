from time import monotonic
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query

from .geometry import EPSILON, parse_polygon
from .schemas import (
    SORT_FIELDS,
    PublicError,
    PublicListing,
    PublicSearchFilters,
    PublicSearchPage,
    SearchFilters,
)
from .search_transport import IDENTITY_ENCODING, read_search_json
from .security import install_http
from .settings import get_settings

settings = get_settings()
app = FastAPI(
    title="Realtoruch · Public search",
    version="0.1.0",
    description="Read-only search backed by private Elasticsearch. Arbitrary Elasticsearch DSL and administrative routes are not exposed.",
)
install_http(app)
INDEX = "rentals-search"

# Lucene indexes rounded-down coordinates. Prune with a padded indexed
# envelope, then apply the same inclusive ray test as SQL to source doubles.
LOCATION_SCRIPT = """
def x = params._source.lon;
def y = params._source.lat;
if (!(x instanceof Number) || !(y instanceof Number) ||
    x < params.west || x > params.east || y < params.south || y > params.north) {
    emit(false); return;
}
def ring = params.ring;
if (ring.isEmpty()) { emit(true); return; }
boolean inside = false;
double eps = params.epsilon;
for (int i = 0; i < ring.size(); i++) {
    def a = ring[i]; def b = ring[(i + 1) % ring.size()];
    double dx = b[0] - a[0]; double dy = b[1] - a[1];
    double det = dx * (y - a[1]) - dy * (x - a[0]);
    if (Math.abs(det) <= eps && x >= Math.min(a[0], b[0]) - eps &&
        x <= Math.max(a[0], b[0]) + eps && y >= Math.min(a[1], b[1]) - eps &&
        y <= Math.max(a[1], b[1]) + eps) { emit(true); return; }
    if (dy != 0 && y >= Math.min(a[1], b[1]) && y < Math.max(a[1], b[1]) &&
        x < a[0] + (y - a[1]) * dx / dy) { inside = !inside; }
}
emit(inside);
"""


def add_geometry(filters, runtime, f):
    if not (f.bbox or f.polygon):
        return
    ring = parse_polygon(f.polygon) if f.polygon else []
    west, south, east, north = map(float, f.bbox.split(",")) if f.bbox else (-180, -90, 180, 90)
    if ring:
        x, y = zip(*ring)
        west, south, east, north = (
            max(west, min(x)),
            max(south, min(y)),
            min(east, max(x)),
            min(north, max(y)),
        )
    if west > east or south > north:
        filters.append({"match_none": {}})
        return
    pad = 1e-6  # Larger than both geo-point quantization steps (~1e-7 degrees).
    filters.append(
        {
            "geo_shape": {
                "location": {
                    "shape": {
                        "type": "envelope",
                        "coordinates": [
                            [max(-180, west - pad), min(90, north + pad)],
                            [min(180, east + pad), max(-90, south - pad)],
                        ],
                    },
                    "relation": "intersects",
                }
            }
        }
    )
    runtime["exact_location_match"] = {
        "type": "boolean",
        "script": {
            "source": LOCATION_SCRIPT,
            "params": {
                "west": west,
                "south": south,
                "east": east,
                "north": north,
                "ring": ring,
                "epsilon": EPSILON,
            },
        },
    }
    filters.append({"term": {"exact_location_match": True}})


def es_client():
    if not settings.elasticsearch_url:
        raise RuntimeError("ELASTICSEARCH_URL is required for the search service")
    headers = (
        {"Authorization": "ApiKey " + settings.elasticsearch_api_key}
        if settings.elasticsearch_api_key
        else {}
    )
    import ssl

    verify = (
        ssl.create_default_context(cafile=settings.elasticsearch_ca_file)
        if settings.elasticsearch_ca_file
        else True
    )
    return httpx.Client(base_url=settings.elasticsearch_url, headers=headers, timeout=10, verify=verify)


def build_query(f: SearchFilters):
    filters = [{"term": {"status": "active"}}]
    runtime = {}
    for field, value in (
        ("city", f.city),
        ("district", f.district),
        ("advertiser_type", f.advertiser if f.advertiser != "all" else ""),
        ("property_type", f.property_type if f.property_type != "all" else ""),
        ("rooms", f.rooms),
        ("amenities", f.amenity),
    ):
        if value:
            match = {"value": value, "case_insensitive": True} if field in ("city", "district") else value
            filters.append({"term": {field: match}})
    if f.min_area is not None or f.max_area is not None or f.sort == "area_desc":
        # The installed projection maps area as a float (32-bit); source and
        # SQL retain the full precision used for inclusive range and ordering.
        runtime["exact_area"] = {
            "type": "double",
            "script": {
                "source": "def a = params._source.area_m2; if (a instanceof Number) { emit(a.doubleValue()); }",
            },
        }
    for field, lower, upper in (
        ("rent_pln", f.min_price, f.max_price),
        ("exact_area", f.min_area, f.max_area),
    ):
        bounds = {key: value for key, value in (("gte", lower), ("lte", upper)) if value is not None}
        if field == "rent_pln" and f.max_price_exclusive and "lte" in bounds:
            bounds["lt"] = bounds.pop("lte")
        if bounds:
            filters.append({"range": {field: bounds}})
    if f.no_commission:
        filters.append({"term": {"commission_pln": 0}})
    if f.hide_suspicious:
        filters.append({"term": {"risk_score": 0}})
    add_geometry(filters, runtime, f)
    query = {"bool": {"filter": filters}}
    if f.q:
        query["bool"]["must"] = [
            {
                "multi_match": {
                    "query": f.q,
                    "fields": ["title^3", "address^2", "district", "description"],
                    "operator": "and",
                }
            }
        ]
    sort_field = SORT_FIELDS[f.sort]
    if f.sort == "newest":
        # Preserve SQL's microseconds without rebuilding the existing date mapping.
        sort_field = "first_seen_micros"
        runtime[sort_field] = {
            "type": "long",
            "script": {
                "source": """
            def at = params._source.first_seen;
            if (at instanceof String) {
                Instant t = Instant.parse(at);
                emit(t.getEpochSecond() * 1000000L + t.getNano() / 1000L);
            }
        """
            },
        }
    elif f.sort == "area_desc":
        sort_field = "exact_area"
    sort = [{sort_field: "asc" if f.sort == "price_asc" else "desc"}, {"id": "asc"}]
    if f.sort == "newest":
        # Keep the indexed coarse sort first; the source sort disambiguates
        # homes that arrived within the same indexed millisecond.
        sort.insert(0, {"first_seen": "desc"})
    return {
        "query": query,
        "sort": sort,
        "size": f.page_size,
        "from": f.offset,
        "track_total_hits": True,
        "timeout": "4s",
        "_source": list(PublicListing.model_fields),
        **({"runtime_mappings": runtime} if runtime else {}),
    }


@app.get("/healthz")
def health():
    return {"status": "ok", "service": "search"}


@app.get("/readyz")
def ready():
    try:
        with es_client() as client:
            client.get("/_cluster/health").raise_for_status()
    except (httpx.HTTPError, RuntimeError):
        raise HTTPException(503, "Search index unavailable")
    return {"status": "ready"}


@app.get(
    "/v1/search",
    response_model=PublicSearchPage,
    responses={429: {"model": PublicError}, 503: {"model": PublicError}},
)
def search(filters: Annotated[PublicSearchFilters, Query()]):
    try:
        deadline = monotonic() + 5
        with (
            es_client() as client,
            client.stream(
                "POST",
                f"/{INDEX}/_search",
                json=build_query(filters),
                params={"allow_partial_search_results": "false"},
                headers=IDENTITY_ENCODING,
                timeout=5,
            ) as response,
        ):
            result = read_search_json(response, deadline=deadline)
        if (
            result["timed_out"] is not False
            or result["_shards"]["failed"] != 0
            or result.get("terminated_early") is True
        ):
            raise ValueError("Index results incomplete")
        hits = result["hits"]["hits"]
        total = result["hits"]["total"]
        if (
            not isinstance(hits, list)
            or len(hits) > filters.page_size
            or total["relation"] != "eq"
            or any(hit["_id"] != hit["_source"]["id"] for hit in hits)
        ):
            raise ValueError("Index results inconsistent")
        return PublicSearchPage.model_validate(
            {
                "items": [hit["_source"] for hit in hits],
                "total": total["value"],
                "page": filters.page,
                "page_size": filters.page_size,
                "engine": "elasticsearch",
                "degraded": False,
                "consistency": "eventual",
                "total_relation": "index",
            }
        ).validate_index_page(filters)
    except (httpx.HTTPError, httpx.InvalidURL, RuntimeError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "Search is temporarily unavailable") from None
