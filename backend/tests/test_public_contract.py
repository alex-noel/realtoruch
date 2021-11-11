"""T12 API contract checks, including parity on isolated PostgreSQL + ES."""

import copy
import json
import os
from contextlib import nullcontext
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import HttpUrl
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from test_marketplace import account
from test_service_integration import pg_engine  # noqa: F401 - disposable migrated schema fixture

from realtoruch import api, indexing, search, search_transport
from realtoruch.auth import validate_claims
from realtoruch.db import get_session
from realtoruch.ingest import ingest
from realtoruch.models import CollectionRun, Listing, SourceListing, SourcePollState, now
from realtoruch.query import serialize_many

CANARY = "private-canary@example.test"
PRIVATE_URL = "https://example.test/access?token=PRIVATE_CANARY"
PUBLIC_KEYS = {
    "id",
    "title",
    "description",
    "city",
    "district",
    "region",
    "address",
    "lat",
    "lon",
    "area_m2",
    "rooms",
    "floor",
    "rent_pln",
    "fees_pln",
    "deposit_pln",
    "commission_pln",
    "total_monthly_pln",
    "advertiser_type",
    "property_type",
    "status",
    "amenities",
    "images",
    "risk_flags",
    "risk_score",
    "is_demo",
    "first_seen",
    "last_seen",
    "updated_at",
    "sources",
    "contact_adverts",
}
PAGE_KEYS = {"items", "total", "page", "page_size", "engine", "degraded", "consistency", "total_relation"}
SOURCE_KEYS = {
    "name",
    "url",
    "rent_pln",
    "fees_pln",
    "commission_pln",
    "advertiser_type",
    "status",
    "last_checked",
    "match_reason",
}


def index_page(items, *, total=None, page=1, page_size=24):
    return {
        "items": items,
        "total": len(items) if total is None else total,
        "page": page,
        "page_size": page_size,
        "engine": "elasticsearch",
        "degraded": False,
        "consistency": "eventual",
        "total_relation": "index",
    }


def fake_index(monkeypatch, response):
    monkeypatch.setattr(api.settings, "search_service_url", "http://private-search.test/")
    request = httpx.Request("GET", "http://private-search.test/v1/search")
    calls = []

    def stream(method, url, *, params, headers, timeout):
        assert method == "GET" and headers["Accept-Encoding"] == "identity"
        calls.append((url, params, timeout))
        if response == "timeout":
            raise httpx.ReadTimeout("Private transport error " + PRIVATE_URL, request=request)
        if response == "unavailable":
            return nullcontext(httpx.Response(503, json={"detail": PRIVATE_URL}, request=request))
        if response == "invalid_json":
            return nullcontext(httpx.Response(200, content=b"{'broken'!!!", request=request))
        return nullcontext(httpx.Response(200, json=response, request=request))

    monkeypatch.setattr(api.httpx, "stream", stream)
    return calls


def store(session, record):
    listing_id = ingest(session, record)["listing_id"]
    session.commit()
    return listing_id, serialize_many(session, [session.get(Listing, listing_id)])[0]


@pytest.fixture(params=[
    "sqlite",
    pytest.param("postgres", marks=pytest.mark.skipif(
        not os.getenv("TEST_POSTGRES_URL"), reason="Requires isolated PostgreSQL"
    )),
])
def favorite_catalog(request):
    engine = (
        request.getfixturevalue("pg_engine")
        if request.param == "postgres"
        else request.getfixturevalue("session").get_bind()
    )
    return sessionmaker(engine, expire_on_commit=False)


def test_favorites_hide_moderated_homes_but_retain_delisted_homes(
    favorite_catalog, auth_client, record, monkeypatch
):
    moderator_id, moderator = account(auth_client, "favorites-moderator")
    _, renter = account(auth_client, "favorites-renter")
    monkeypatch.setattr(api.settings, "moderator_user_ids", moderator_id)
    monkeypatch.setattr(api.app.state, "validate_claims", validate_claims, raising=False)

    def rental_session():
        with favorite_catalog() as session:
            yield session

    monkeypatch.setitem(api.app.dependency_overrides, get_session, rental_session)
    with favorite_catalog.begin() as session:
        home = ingest(session, record)["listing_id"]
        alias = ingest(session, record.model_copy(update={
            "external_id": "old-alias", "address": "Inna 89", "phone": None,
        }))["listing_id"]
        withdrawn = record.model_copy(update={
            "external_id": "later-withdrawn", "address": "Osobna 49", "phone": None,
        })
        delisted = ingest(session, withdrawn)["listing_id"]
    assert len({home, alias, delisted}) == 3

    with TestClient(api.app) as client:
        merge = client.post(
            f"/v1/moderation/listings/{alias}/merge", headers=moderator,
            json={"target_id": home, "reason": "Reviewed both offers as the same home."},
        )
        assert merge.status_code == 200, merge.text
        for headers, listing_id in ((renter, home), (moderator, home), (renter, delisted)):
            assert client.put(f"/v1/me/favorites/{listing_id}", headers=headers).status_code == 200
        with favorite_catalog.begin() as session:
            ingest(session, withdrawn.model_copy(update={
                "status": "inactive", "observed_at": withdrawn.observed_at + timedelta(minutes=1),
            }))

        def review(action):
            report = client.post(
                f"/v1/listings/{home}/reports", headers=renter,
                json={"reason": "Please review this synthetic listing."},
            )
            assert report.status_code == 201, report.text
            result = client.post(
                f"/v1/moderation/reports/{report.json()['id']}/review", headers=moderator,
                json={"action": action, "reason": "Moderation review of the fixture."},
            )
            assert result.status_code == 200, result.text

        def favorites(headers):
            response = client.get("/v1/me/favorites", headers=headers)
            assert response.status_code == 200, response.text
            return {item["id"]: item["status"] for item in response.json()["items"]}

        review("hide")
        assert client.get(f"/v1/listings/{alias}").status_code == 404
        hidden_favorites = favorites(renter)
        assert client.delete(f"/v1/me/favorites/{alias}", headers=moderator).status_code == 200
        hidden_saves = [
            client.put(f"/v1/me/favorites/{listing_id}", headers=moderator).status_code
            for listing_id in (home, alias)
        ]
        assert (hidden_favorites, hidden_saves) == ({delisted: "inactive"}, [404, 404])

        review("restore")
        assert favorites(renter) == {home: "active", delisted: "inactive"}
        assert favorites(moderator) == {}
        assert client.delete(f"/v1/me/favorites/{delisted}", headers=renter).status_code == 200
        assert favorites(renter) == {home: "active"}


def test_t12_upstream_private_fields_cannot_escape(session, record, client, monkeypatch):
    listing_id, upstream = store(session, record)
    upstream.update(
        title="Untrusted title",
        phone_hash="a" * 64,
        draft={"email": CANARY},
        sources=[{**upstream["sources"][0], "phone": CANARY, "private_reason": PRIVATE_URL}],
        risk_flags=[
            {
                "code": "private_commission",
                "label": "Commission",
                "detail": "Terms",
                "severity": "medium",
                "reviewer": CANARY,
            }
        ],
        contact_adverts=[
            {
                "id": listing_id,
                "name": "A profile",
                "kind": "private",
                "profile_id": listing_id,
                "email": CANARY,
            }
        ],
    )
    calls = fake_index(monkeypatch, {**index_page([upstream]), "account_token": PRIVATE_URL})
    response = client.get("/v1/listings")
    assert response.status_code == 200
    assert len(calls) == 1
    assert set(response.json()) == PAGE_KEYS
    assert response.json()["consistency"] == "sql_checked" and not response.json()["degraded"]
    (item,) = response.json()["items"]
    assert set(item) == PUBLIC_KEYS and set(item["sources"][0]) == SOURCE_KEYS
    assert item["title"] == record.title and item["contact_adverts"] == [] and item["risk_flags"] == []
    assert not any(
        canary in response.text
        for canary in (CANARY, "PRIVATE_CANARY", "phone_hash", "private_reason", "account_token")
    )


def test_t12_other_public_reads_allowlist(session, record, client, monkeypatch):
    from realtoruch import connectors

    listing_id, _ = store(
        session,
        record.model_copy(
            update={
                "description": f"Nice home. Email {CANARY} or call 700 100 101.",
                "images": [
                    HttpUrl(PRIVATE_URL),
                    HttpUrl("https://example.test/photo.jpg#token=PRIVATE_CANARY"),
                ],
                "amenities": ["balcony", "long" * 200],
            }
        ),
    )
    source = session.scalar(select(SourceListing))
    source.match_reason = f"Private moderator note: {CANARY}"
    source.url += "#phone_hash=PRIVATE_CANARY"
    ingest(session, record.model_copy(update={"city": "Kraków", "external_id": "other-city", "phone": None}))
    session.add(
        CollectionRun(
            source=record.source,
            city=record.city,
            status="failed",
            finished_at=now(),
            report={
                "errors": [
                    {
                        "kind": "SourceAccessError",
                        "stage": "discovery",
                        "http_status": 403,
                        "url": PRIVATE_URL,
                        "message": CANARY,
                    },
                    {"kind": CANARY, "stage": PRIVATE_URL, "http_status": PRIVATE_URL},
                    {},
                    CANARY,
                ],
                "provider_token": PRIVATE_URL,
            },
        )
    )
    session.commit()
    monkeypatch.setattr(
        connectors,
        "load_sources",
        lambda: [
            {
                "name": record.source,
                "mode": "portal",
                "enabled": False,
                "disabled_reason": PRIVATE_URL,
                "url": PRIVATE_URL,
                "recheck_interval_minutes": 360,
            }
        ],
    )
    detail, history, summary, sources = (
        client.get(path)
        for path in (
            f"/v1/listings/{listing_id}",
            "/v1/market/history",
            "/v1/market/summary",
            "/v1/sources?city=Warszawa",
        )
    )
    for response in detail, history, summary, sources:
        assert response.status_code == 200
        assert (
            CANARY not in response.text
            and "700 100 101" not in response.text
            and "PRIVATE_CANARY" not in response.text
        )
    home = detail.json()
    assert set(home) == PUBLIC_KEYS | {"history"} and set(home["history"][0]) == {
        "at",
        "rent_pln",
        "fees_pln",
        "status",
    }
    assert home["images"] == ["https://example.test/photo.jpg"] and home["amenities"] == ["balcony"]
    assert home["sources"][0]["url"] == str(record.url)
    assert home["sources"][0]["match_reason"] == "Imported source advert"
    assert set(history.json()) == {"points", "methodology", "city", "district", "region"}
    assert set(history.json()["points"][0]) == {
        "month",
        "median_rent_pln",
        "median_per_m2",
        "sample_size",
        "is_demo",
    }
    assert set(summary.json()) == {
        "homes",
        "source_listings",
        "duplicates_removed",
        "private_homes",
        "median_rent_pln",
        "demo",
        "districts",
        "cities",
    }
    (health,) = sources.json()["sources"]
    assert set(health) == {
        "name",
        "mode",
        "enabled",
        "disabled_reason",
        "status",
        "last_observed_at",
        "stored_adverts",
        "health",
        "cadence_minutes",
    }
    assert health["disabled_reason"] == "Source collection is disabled."
    assert health["cadence_minutes"] == 360 and health["stored_adverts"] == 1 and health["last_observed_at"]
    (krakow,) = client.get("/v1/sources?city=Krakow").json()["sources"]
    assert krakow["stored_adverts"] == 1 and krakow["health"] is None
    (absent,) = client.get("/v1/sources?city=Poznań").json()["sources"]
    assert absent["stored_adverts"] == 0 and absent["last_observed_at"] is None
    (unfiltered,) = client.get("/v1/sources").json()["sources"]
    assert unfiltered["stored_adverts"] == 2
    assert health["health"]["errors"] == [
        {"kind": "SourceAccessError", "stage": "discovery", "http_status": 403},
        {"kind": "other", "stage": "other", "http_status": None},
        {"kind": "other", "stage": "other", "http_status": None},
    ]


def seed_collection_runs(session):
    clock = now().replace(microsecond=0)
    completed = clock - timedelta(hours=1)
    session.add(
        SourcePollState(source="otodom", last_success_at=clock, retry_after=clock + timedelta(minutes=10))
    )
    for city, status, limited, finished in (
        ("Warszawa", "succeeded", False, completed),
        ("Warszawa", "succeeded", True, clock - timedelta(minutes=20)),
        ("Kraków", "failed", False, clock - timedelta(minutes=10)),
    ):
        session.add(
            CollectionRun(
                source="otodom",
                city=city,
                status=status,
                started_at=finished - timedelta(minutes=2),
                finished_at=finished,
                report={"limited": limited},
            )
        )
    return completed.isoformat() + "Z"


def assert_city_freshness(client, completed):
    def health(params):
        response = client.get("/v1/sources", params=params)
        assert response.status_code == 200, response.text
        return next(source["health"] for source in response.json()["sources"] if source["name"] == "otodom")

    warsaw = health({"city": "Warszawa"})
    krakow = health({"city": "Krakow"})
    global_health = health({})
    assert warsaw["status"] == "succeeded" and warsaw["limited"] and warsaw["last_success_at"] == completed
    assert krakow["status"] == "failed" and krakow["last_success_at"] is None
    assert global_health["last_success_at"] == completed
    assert krakow["retry_after"] == warsaw["retry_after"] and warsaw["retry_after"] is not None


def test_t12_source_freshness_requires_complete_success_in_requested_city(session, client):
    completed = seed_collection_runs(session)
    session.commit()
    assert_city_freshness(client, completed)


@pytest.mark.parametrize(
    "case",
    [
        "timeout",
        "unavailable",
        "invalid_json",
        "wrong_shape",
        "nested_type",
        "bad_count",
        "wrong_page",
        "bad_port",
        "url_control_char",
        "url_invalid_utf8",
    ],
)
def test_t12_invalid_upstream_uses_sql(case, session, record, client, monkeypatch):
    listing_id, item = store(session, record)
    response = case
    if case == "wrong_shape":
        response = {"items": "not an array"}
    elif case == "nested_type":
        response = index_page([item])
        item["sources"][0]["fees_pln"] = "500"
    elif case == "bad_count":
        response = index_page([item], total=5)
    elif case == "wrong_page":
        response = index_page([item], page=2)
    elif case in ("bad_port", "url_control_char", "url_invalid_utf8"):
        item["sources"][0]["url"] = {
            "bad_port": "https://example.test:99999/item",
            "url_control_char": "https://example.test/item\n",
            "url_invalid_utf8": "https://example.test/%FF",
        }[case]
        response = index_page([item])
    calls = fake_index(monkeypatch, response)
    result = client.get("/v1/listings").json()
    assert len(calls) == 1 and [i["id"] for i in result["items"]] == [listing_id]
    assert result["total"] == 1
    assert (result["degraded"], result["consistency"], result["total_relation"]) == (True, "sql", "exact")


@pytest.mark.parametrize(
    "params",
    [
        {"polygon": "[[19.9,50.0],[20.1,50.1],[19.9,50.1],[20.1,50.0]]"},
        {"bbox": "19.9,50.1,20,50.0"},
        {"page_size": 101},
        {"page": 102, "page_size": 100},
        {"page": 101, "page_size": 100},
        {"min_area": "inf"},
    ],
)
def test_t12_both_routes_reject_invalid_queries_before_io(client, monkeypatch, params):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid query reached the catalog")

    monkeypatch.setattr(api, "fetch_index_page", unexpected)
    monkeypatch.setattr(api, "catalog_read_budget", unexpected)
    monkeypatch.setattr(search, "es_client", unexpected)
    monkeypatch.setattr(api.settings, "search_service_url", "http://private-search.test")
    result = client.get("/v1/listings", params=params)
    other = TestClient(search.app).get("/v1/search", params=params)
    assert result.status_code == other.status_code == 422
    assert result.json() == other.json()


def test_t12_max_supported_window_and_deliberate_sql_mode(client, monkeypatch):
    monkeypatch.setattr(api.settings, "search_service_url", "")
    response = client.get("/v1/listings", params={"page": 100, "page_size": 100})
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 100,
        "page_size": 100,
        "engine": "sqlite",
        "degraded": False,
        "consistency": "sql",
        "total_relation": "exact",
    }


def test_t12_local_quota_supplies_retry_after(client, monkeypatch):
    monkeypatch.setattr(api.settings, "search_service_url", "")
    monkeypatch.setattr(api.settings, "request_limit_per_minute", 1)
    anonymous = TestClient(api.app, client=("t12-isolated-peer", 51000))
    assert anonymous.get("/v1/listings").status_code == 200
    response = anonymous.get("/v1/listings")
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    assert response.json() == {"detail": "Rate limit reached; try again shortly"}


@pytest.mark.parametrize("upstream", ["unavailable", index_page([])], ids=["both-down", "empty-index"])
def test_t12_sql_outage_is_not_empty_success(client, monkeypatch, upstream):
    fake_index(monkeypatch, upstream)

    class UnavailableDatabase:
        def connection(self):
            raise OperationalError("secret SQL " + CANARY, {}, RuntimeError(PRIVATE_URL))

    monkeypatch.setitem(api.app.dependency_overrides, get_session, UnavailableDatabase)
    result = client.get("/v1/listings")
    assert result.status_code == 503
    assert result.json() == {"detail": "Rental catalog is temporarily unavailable"}


@pytest.mark.parametrize("route", ["rest", "direct"])
def test_t12_large_upstream_is_closed_without_reading_the_rest(route, client, monkeypatch):
    monkeypatch.setattr(search_transport, "MAX_SEARCH_RESPONSE_BYTES", 65_536)
    consumed = []

    class LargeSearchResponse(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(2):
                consumed.append("read")
                yield b"a" * 65_536
            pytest.fail("The oversized HTTP response was consumed after exceeding the cap")

        def close(self):
            consumed.append("closed")

    def respond(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, stream=LargeSearchResponse())

    transport = httpx.MockTransport(respond)
    if route == "rest":
        monkeypatch.setattr(api.settings, "search_service_url", "http://private-search.test")
        with httpx.Client(transport=transport) as upstream:
            monkeypatch.setattr(api.httpx, "stream", upstream.stream)
            response = client.get("/v1/listings")
        assert response.status_code == 200 and response.json()["degraded"] is True
    else:
        monkeypatch.setattr(
            search, "es_client", lambda: httpx.Client(base_url="http://fake-es.test", transport=transport)
        )
        response = TestClient(search.app).get("/v1/search")
        assert response.status_code == 503
    assert consumed == ["read", "read", "closed"]


@pytest.mark.parametrize("route", ["rest", "direct"])
def test_t12_small_chunks_do_not_reset_total_search_deadline(route, client, monkeypatch):
    clock = [0]
    reads = []

    class SlowSearchResponse(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(2):
                clock[0] += 3  # Below the per-read timeout, above the total after two reads.
                reads.append(clock[0])
                yield b" "
            pytest.fail("Another small chunk was read after the total deadline")

        def close(self):
            reads.append("closed")

    monkeypatch.setattr(search_transport, "monotonic", lambda: clock[0])
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowSearchResponse()))
    if route == "rest":
        monkeypatch.setattr(api, "monotonic", lambda: clock[0])
        monkeypatch.setattr(api.settings, "search_service_url", "http://private-search.test")
        with httpx.Client(transport=transport) as upstream:
            monkeypatch.setattr(api.httpx, "stream", upstream.stream)
            response = client.get("/v1/listings")
        assert response.status_code == 200 and response.json()["degraded"] is True
    else:
        monkeypatch.setattr(search, "monotonic", lambda: clock[0])
        monkeypatch.setattr(
            search, "es_client", lambda: httpx.Client(base_url="http://fake-es.test", transport=transport)
        )
        response = TestClient(search.app).get("/v1/search")
        assert response.status_code == 503
    assert reads == [3, 6, "closed"]


@pytest.mark.parametrize(
    "bad_result",
    [
        b"unparseable",
        {"hits": []},
        {"timed_out": True, "_shards": {"failed": 0}},
        {"timed_out": False, "_shards": {"failed": 1}},
    ],
)
def test_t12_search_proxy_rejects_invalid_or_partial_elasticsearch(bad_result, monkeypatch):
    def respond(request):
        if isinstance(bad_result, bytes):
            return httpx.Response(200, content=bad_result)
        return httpx.Response(200, json=bad_result)

    monkeypatch.setattr(
        search,
        "es_client",
        lambda: httpx.Client(
            base_url="http://fake-es.test",
            transport=httpx.MockTransport(respond),
        ),
    )
    result = TestClient(search.app).get("/v1/search")
    assert result.status_code == 503
    assert result.json() == {"detail": "Search is temporarily unavailable"}


real_services = pytest.mark.skipif(
    not all(os.getenv(k) for k in ("TEST_POSTGRES_URL", "TEST_ELASTICSEARCH_URL")),
    reason="Requires isolated PostgreSQL and Elasticsearch instances",
)


@pytest.fixture
def indexed_catalog(pg_engine, monkeypatch):  # noqa: F811
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    name = "t12_" + uuid4().hex
    monkeypatch.setattr(search, "INDEX", name)
    monkeypatch.setattr(search.settings, "elasticsearch_url", os.environ["TEST_ELASTICSEARCH_URL"])
    with search.es_client() as es:
        indexing.create_physical_index(es, name)
        with TestClient(search.app) as direct, TestClient(api.app) as rest:

            def rental_session():
                with factory() as session:
                    yield session

            monkeypatch.setitem(api.app.dependency_overrides, get_session, rental_session)
            monkeypatch.setattr(api.settings, "search_service_url", "http://private-search.test")
            monkeypatch.setattr(
                api.httpx,
                "stream",
                lambda method, url, *, params, headers, timeout: nullcontext(
                    direct.get("/v1/search", params=params)
                ),
            )
            try:
                yield factory, es, name, direct, rest
            finally:
                es.delete(f"/{name}").raise_for_status()


def publish(factory, es, name, ids):
    with factory.begin() as session:
        snapshot = indexing.snapshot(session, ids)
    assert indexing.send_bulk(es, snapshot, name) == {listing_id: (201, True) for listing_id in ids}
    es.post(f"/{name}/_refresh").raise_for_status()


def fixture_home(record, i, **overrides):
    data = {
        "external_id": "t12-" + str(i),
        "address": f"Fixture {i}",
        "city": "Kraków",
        "district": "Podgórze",
        "phone": None,
        "lat": 50.05,
        "lon": 19.95,
        "area_m2": 50.0,
        "rent_pln": 4500,
        "fees_pln": 700,
        "amenities": ["taras/ogród"],
        "commission_pln": 0,
        **overrides,
    }
    return record.model_copy(update=data)


def read_ids(client, route, **params):
    response = client.get(route, params=params)
    assert response.status_code == 200, response.text
    result = response.json()
    return [item["id"] for item in result["items"]], result


@real_services
def test_t12_real_structured_filters_and_static_pagination(indexed_catalog, record, monkeypatch):
    factory, es, name, direct, rest = indexed_catalog
    observed = now() - timedelta(hours=1)
    specs = [
        {"lon": 19.9, "lat": 50.02},  # south-west vertex
        {"lon": 20.02, "lat": 50.06},  # east edge
        {"lat": 50.1, "commission_pln": None},  # north edge, direct != known zero
        {"lon": 19.9 - 1e-8},  # outside; only the coarse envelope accepts it
        {"area_m2": 49.9999999},  # ES indexed float alone rounds up to 50
        {"rent_pln": 5000},
        {"advertiser_type": "agency"},
        {"property_type": "house"},
        {"district": "Other"},
        {"rooms": 3},
        {"amenities": ["not taras/ogród"]},
        {"status": "inactive"},
    ]
    with factory.begin() as session:
        ids = [ingest(session, fixture_home(record, i, **spec))["listing_id"] for i, spec in enumerate(specs)]
        for i, home_id in enumerate(ids):
            session.get(Listing, home_id).first_seen = observed.replace(microsecond=123000 + i)
    assert len(set(ids)) == len(specs)
    publish(factory, es, name, ids)

    polygon = json.dumps([[19.90, 50.02], [20.02, 50.02], [20.02, 50.10], [19.90, 50.10]])
    filters = {
        "city": "KRAKOW",
        "district": "podgórze",
        "property_type": "apartment",
        "rooms": 2,
        "advertiser": "private",
        "max_price": 5000,
        "max_price_exclusive": True,
        "min_area": 50,
        "amenity": "taras/ogród",
        "hide_suspicious": True,
        "polygon": polygon,
        "sort": "price_asc",
        "page_size": 2,
    }
    expected = sorted(ids[:3])
    for engine in "elasticsearch", "postgresql":
        if engine == "postgresql":
            monkeypatch.setattr(api.settings, "search_service_url", "")
        client, route = (direct, "/v1/search") if engine == "elasticsearch" else (rest, "/v1/listings")
        first, response = read_ids(client, route, **filters, page=1)
        second, _ = read_ids(client, route, **filters, page=2)
        assert response["engine"] == engine and response["total"] == 3
        assert first + second == expected and not set(first) & set(second)
        zero, _ = read_ids(client, route, **filters, no_commission=True)
        assert zero == sorted(ids[:2])
        newest, _ = read_ids(client, route, **{**filters, "sort": "newest", "page_size": 3})
        assert newest == list(reversed(ids[:3]))
        for sort in ("price_desc", "area_desc"):
            equal, _ = read_ids(client, route, **{**filters, "sort": sort, "page_size": 3})
            assert equal == expected
        in_box, _ = read_ids(
            client, route, **{**filters, "polygon": "", "bbox": "19.9,50.02,20.02,50.10", "page_size": 3}
        )
        assert in_box == expected

    # REST serves the same IDs after actual ES selects the page.
    monkeypatch.setattr(api.settings, "search_service_url", "http://private-search.test")
    rest_ids, checked = read_ids(rest, "/v1/listings", **filters)
    assert rest_ids == expected[:2] and checked["consistency"] == "sql_checked"


@real_services
def test_t12_postgres_source_freshness_requires_complete_success_in_requested_city(indexed_catalog):
    factory, _, _, _, rest = indexed_catalog
    with factory.begin() as session:
        completed = seed_collection_runs(session)
    assert_city_freshness(rest, completed)


@real_services
def test_t12_real_stale_index_is_checked_and_fallback_total_is_honest(indexed_catalog, record):
    factory, es, name, direct, rest = indexed_catalog
    with factory.begin() as session:
        ids = [
            ingest(session, fixture_home(record, i, rent_pln=rent))["listing_id"]
            for i, rent in enumerate((4100, 4200, 4300, 4400))
        ]
    publish(factory, es, name, ids)
    # No indexer runs between the committed SQL change and the public reads.
    with factory.begin() as session:
        session.get(Listing, ids[1]).hidden = True  # still marked active
        session.get(Listing, ids[2]).status = "inactive"
        session.get(Listing, ids[3]).rent_pln = 5100
    filters = {"sort": "price_asc", "max_price": 5000}
    index_ids, index_result = read_ids(direct, "/v1/search", **filters)
    assert index_ids == ids and index_result["consistency"] == "eventual"
    first, indexed = read_ids(rest, "/v1/listings", **filters, page_size=1)
    assert first == ids[:1] and indexed["total"] == 4 and indexed["total_relation"] == "index"
    for size in (2, 3, 4):
        checked_ids, result = read_ids(rest, "/v1/listings", **filters, page_size=size)
        assert checked_ids == ids[:1] and result["total"] == 1
        assert (result["degraded"], result["consistency"], result["total_relation"]) == (True, "sql", "exact")
    assert rest.get(f"/v1/listings/{ids[1]}").status_code == 404
    assert rest.get(f"/v1/listings/{ids[2]}").json()["status"] == "inactive"
    with factory.begin() as session:
        session.get(Listing, ids[0]).rent_pln = 4050
    _, changed = read_ids(rest, "/v1/listings", **filters, page_size=1)
    assert changed["degraded"] and changed["items"][0]["rent_pln"] == 4050


@real_services
def test_t12_real_index_canaries_are_removed_at_every_level(indexed_catalog, record):
    factory, es, name, direct, rest = indexed_catalog
    with factory.begin() as session:
        listing_id = ingest(session, fixture_home(record, 1))["listing_id"]
    with factory.begin() as session:
        _, revision, public = indexing.snapshot(session, [listing_id])[0]
    tainted = copy.deepcopy(public)
    tainted.update(email=CANARY, phone_hash="f" * 64, draft={"email": CANARY})
    tainted["sources"][0].update(
        phone=CANARY,
        url_hash=PRIVATE_URL,
        match_reason="Private reason: " + CANARY,
        url=public["sources"][0]["url"] + "#token=PRIVATE_CANARY",
    )
    tainted["risk_flags"] = [
        {
            "code": "private_commission",
            "label": "Commission",
            "detail": "Private reason: " + CANARY,
            "severity": "medium",
            "audit_reason": CANARY,
        }
    ]
    tainted["contact_adverts"] = [
        {"id": listing_id, "name": "A profile", "kind": "private", "profile_id": listing_id, "email": CANARY}
    ]
    indexing.send_bulk(es, [(listing_id, revision, tainted)], name)
    es.post(f"/{name}/_refresh").raise_for_status()
    for client, path in ((direct, "/v1/search"), (rest, "/v1/listings")):
        response = client.get(path)
        assert response.status_code == 200, response.text
        for forbidden in (CANARY, "PRIVATE_CANARY", "phone_hash", "url_hash", "audit_reason", "draft"):
            assert forbidden not in response.text
        (item,) = response.json()["items"]
        assert set(item) == PUBLIC_KEYS and set(item["sources"][0]) == SOURCE_KEYS
        assert response.json()["degraded"] is False
    (item,) = direct.get("/v1/search").json()["items"]
    assert set(item["risk_flags"][0]) == {"code", "label", "detail", "severity"}
    assert set(item["contact_adverts"][0]) == {"id", "name", "kind", "profile_id"}
    assert item["sources"][0]["match_reason"] == "Imported source advert"


@real_services
def test_t12_real_postgres_lock_and_unavailable_search_fail_closed(indexed_catalog):
    factory, _, name, direct, rest = indexed_catalog
    # A missing index makes the proxy unavailable while the physical index
    # owned by the fixture still exists for safe cleanup.
    from unittest.mock import patch

    with patch.object(search, "INDEX", name + "_unavailable"), factory.begin() as holding:
        assert direct.get("/v1/search").status_code == 503
        holding.execute(text("LOCK TABLE listings IN ACCESS EXCLUSIVE MODE"))
        result = rest.get("/v1/listings")
    assert result.status_code == 503
    assert result.json() == {"detail": "Rental catalog is temporarily unavailable"}
