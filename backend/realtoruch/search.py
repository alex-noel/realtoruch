import httpx
from fastapi import FastAPI, HTTPException, Query

from .schemas import SearchFilters
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
    for field, value in (
        ("city", f.city),
        ("district", f.district),
        ("advertiser_type", f.advertiser if f.advertiser != "all" else ""),
        ("property_type", f.property_type if f.property_type != "all" else ""),
        ("rooms", f.rooms),
        ("amenities", f.amenity),
    ):
        if value:
            filters.append({"term": {field: value}})
    for field, lower, upper in (("rent_pln", f.min_price, f.max_price), ("area_m2", f.min_area, f.max_area)):
        bounds = {key: value for key, value in (("gte", lower), ("lte", upper)) if value is not None}
        if field == "rent_pln" and f.max_price_exclusive and "lte" in bounds:
            bounds["lt"] = bounds.pop("lte")
        if bounds:
            filters.append({"range": {field: bounds}})
    if f.no_commission:
        filters.append({"term": {"commission_pln": 0}})
    if f.hide_suspicious:
        filters.append({"term": {"risk_score": 0}})
    if f.bbox:
        w, s, e, n = map(float, f.bbox.split(","))
        filters.append(
            {
                "geo_bounding_box": {
                    "location": {"top_left": {"lat": n, "lon": w}, "bottom_right": {"lat": s, "lon": e}}
                }
            }
        )
    if f.polygon:
        from .geometry import parse_polygon

        points = parse_polygon(f.polygon)
        filters.append(
            {
                "geo_shape": {
                    "location": {
                        "shape": {"type": "polygon", "coordinates": [points + points[:1]]},
                        "relation": "intersects",
                    }
                }
            }
        )
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
    sort = {
        "newest": {"first_seen": "desc"},
        "price_asc": {"rent_pln": "asc"},
        "price_desc": {"rent_pln": "desc"},
        "area_desc": {"area_m2": "desc"},
    }[f.sort]
    return {
        "query": query,
        "sort": [sort, {"id": "asc"}],
        "size": f.page_size,
        "from": (f.page - 1) * f.page_size,
        "track_total_hits": True,
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


@app.get("/v1/search")
def search(filters: SearchFilters = Query()):
    if filters.page * filters.page_size > 10000:
        raise HTTPException(422, "Narrow the filters to browse beyond 10,000 results")
    try:
        with es_client() as client:
            response = client.post(f"/{INDEX}/_search", json=build_query(filters))
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, RuntimeError):
        raise HTTPException(503, "Search is temporarily unavailable")
    items = [h["_source"] for h in result["hits"]["hits"]]
    for item in items:
        item.pop("location", None)
    return {
        "items": items,
        "total": result["hits"]["total"]["value"],
        "page": filters.page,
        "page_size": filters.page_size,
        "engine": "elasticsearch",
    }
