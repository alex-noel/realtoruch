import json
import pytest
from realtoruch.connectors import Connector, parse_jsonld, validate_url, load_sources
from realtoruch.search import build_query
from realtoruch.schemas import SearchFilters
from realtoruch.settings import Settings


def test_sources_are_off_until_configured():
    assert {s["name"] for s in load_sources()} >= {"otodom", "olx", "gratka"}
    assert all(not s["enabled"] for s in load_sources())


@pytest.mark.parametrize(
    "url",
    [
        "http://www.otodom.pl/foo",
        "https://localhost/foo",
        "https://www.otodom.pl.evil.test/foo",
        "https://user:secret@www.otodom.pl/foo",
    ],
)
def test_source_hosts_are_exact_and_https_only(url):
    with pytest.raises(ValueError):
        validate_url(url, ["www.otodom.pl"])


def test_source_dns_must_not_resolve_to_metadata_or_private_network(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a: [(2, 1, 6, "", ("169.254.169.254", 443))])
    with pytest.raises(ValueError):
        validate_url("https://www.otodom.pl/test", ["www.otodom.pl"])


def test_structured_listing_requires_explicit_rent_semantics():
    data = {
        "@type": "Apartment",
        "identifier": "listing1",
        "name": "Sunny apartment",
        "address": {"addressLocality": "Warszawa", "streetAddress": "Test 1"},
        "floorSize": {"value": 50},
        "numberOfRooms": 2,
        "offers": {"price": 3500, "priceCurrency": "PLN"},
    }
    html = lambda: '<script type="application/ld+json">' + json.dumps(data) + "</script>"
    with pytest.raises(ValueError, match="rental"):
        parse_jsonld(html(), "otodom", "https://www.otodom.pl/example")
    data["offers"]["businessFunction"] = "http://purl.org/goodrelations/v1#LeaseOut"
    parsed = parse_jsonld(html(), "otodom", "https://www.otodom.pl/example")
    assert parsed.rent_pln == 3500 and parsed.commission_pln is None
    data["offers"]["priceCurrency"] = "EUR"
    with pytest.raises(ValueError, match="PLN"):
        parse_jsonld(html(), "otodom", "https://www.otodom.pl/example")


def test_search_dsl_is_built_from_bounded_fields():
    query = build_query(
        SearchFilters(q='{"script":"danger"}', no_commission=True, bbox="20,52,22,53", max_price=4000)
    )
    assert query["query"]["bool"]["must"][0]["multi_match"]["query"] == '{"script":"danger"}'
    assert {"term": {"commission_pln": 0}} in query["query"]["bool"]["filter"]
    assert {"range": {"rent_pln": {"lte": 4000}}} in query["query"]["bool"]["filter"]


def test_production_refuses_demo_defaults():
    with pytest.raises(ValueError):
        Settings(environment="production")


DETAIL_URL = "https://www.otodom.pl/example"
ROBOTS = b"User-agent: *\nDisallow: /blocked\n"
ETAG = '"fixture-v1"'
LAST_MODIFIED = "Tue, 02 Jan 2024 00:00:00 GMT"


def detail_page(*, rent=3500):
    data = {
        "@type": "Apartment",
        "identifier": "detail-one",
        "name": "Example apartment",
        "description": "A literal &lt;balcony&gt; &amp; bright rooms. Contact 700 100 101",
        "address": {"addressLocality": "Kraków", "streetAddress": "Example 1"},
        "floorSize": {"value": 54},
        "numberOfRooms": 2,
        "offers": {"price": rent, "priceCurrency": "PLN", "businessFunction": "LeaseOut"},
    }
    return ('<script type="application/ld+json">' + json.dumps(data) + "</script>").encode()


class FetchClock:
    def __init__(self):
        from datetime import datetime

        self.instant = datetime(2024, 1, 2, 8)
        self.elapsed = 0

    def now(self):
        return self.instant

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        from datetime import timedelta

        self.instant += timedelta(seconds=seconds)
        self.elapsed += seconds


def fake_collector(monkeypatch, factory, handler, *, config=None):
    import httpx
    from realtoruch import collection_health, connectors, worker

    clock = FetchClock()
    attempts = []
    source = {
        "name": "otodom", "enabled": True, "mode": "jsonld", "city": "Kraków",
        "listing_urls": [DETAIL_URL], "allowed_hosts": ["www.otodom.pl"], "requests_per_minute": 60,
        **(config or {}),
    }
    monkeypatch.setattr(connectors, "time", clock)
    monkeypatch.setattr(connectors, "uniform", lambda *_: 0.125)
    for module in (collection_health, connectors, worker):
        monkeypatch.setattr(module, "now", clock.now)
    monkeypatch.setattr(connectors, "validate_url", lambda *_: None)
    monkeypatch.setattr(worker, "Session", factory)
    monkeypatch.setattr(worker, "load_sources", lambda: [source])
    original = Connector.__init__

    def transport(request):
        attempts.append((clock.now(), request))
        return handler(request)

    def init(connector, *args, **kwargs):
        original(connector, *args, **kwargs)
        connector.client.close()
        connector.client = httpx.Client(transport=httpx.MockTransport(transport))

    monkeypatch.setattr(Connector, "__init__", init)
    return clock, attempts, source


@pytest.fixture
def collector_factory(session):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(session.bind, expire_on_commit=False)


def test_t04_304_uses_validated_payload_and_keeps_daily_history(monkeypatch, collector_factory):
    from datetime import timedelta

    import httpx
    from sqlalchemy import func, select
    from realtoruch import worker
    from realtoruch.alerts import process_alerts
    from realtoruch.models import AlertEvent, CollectionFetchState, Listing, Notification, Observation, SavedSearch, SourceListing

    page = detail_page()
    detail_attempts = []

    class No304Body(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("A 304 body must not be consumed")

    def handler(request):
        if request.url.path == "/robots.txt":
            assert "if-none-match" not in request.headers
            return httpx.Response(200, content=ROBOTS)
        detail_attempts.append(request)
        if len(detail_attempts) == 1:
            assert "if-none-match" not in request.headers
            return httpx.Response(200, content=page, headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})
        assert request.headers["If-None-Match"] == ETAG
        assert request.headers["If-Modified-Since"] == LAST_MODIFIED
        return httpx.Response(304, stream=No304Body())

    clock, _, _ = fake_collector(monkeypatch, collector_factory, handler)
    with collector_factory.begin() as db:
        db.add(SavedSearch(user_id="fixture-user", name="fixture", city_key="krakow", filters={"city": "Kraków"}))

    before = worker.collect()[0]
    assert before["network_attempts"] == 2 and before["body_bytes"] == len(ROBOTS) + len(page)
    assert before["conditional_attempts"] == 0 and before["robots_attempts"] == 1
    with collector_factory.begin() as db:
        source = db.scalar(select(SourceListing))
        initial = source.observed_at
        state = db.scalar(select(CollectionFetchState)).validators
        assert state["etag"] == ETAG and state["last_modified"] == LAST_MODIFIED
        assert "<balcony> & bright" in source.data["description"]
        assert "700 100 101" not in str(state) and "_fetch" not in source.data
        process_alerts(db)
        assert db.scalar(select(func.count()).select_from(Notification)) == 1

    for next_day in (False, True, False):
        if next_day:
            clock.sleep(timedelta(days=1).total_seconds())
        after = worker.collect()[0]
        assert after["network_attempts"] == 2 and after["body_bytes"] == len(ROBOTS)
        assert after["conditional_attempts"] == after["responses_304"] == after["reused_304"] == 1
        assert after["retry_attempts"] == 0 and after["ingested"] == 1
        with collector_factory.begin() as db:
            source = db.scalar(select(SourceListing))
            assert source.observed_at > initial
            assert source.observed_at == db.scalar(select(Listing.last_seen))
            assert "<balcony> & bright" in source.data["description"]
            observations = db.scalars(select(Observation).order_by(Observation.observed_at)).all()
            assert len(observations) == 1 + int(source.observed_at.date() != initial.date())
            if len(observations) == 2:
                assert observations[-1].changed is False
            assert db.scalar(select(func.count()).select_from(AlertEvent)) == 1
            process_alerts(db)
            assert db.scalar(select(func.count()).select_from(Notification)) == 1


@pytest.mark.parametrize("invalid", ["unknown", "missing", "mismatched_url", "drift", "deleted", "inactive"])
def test_t04_orphan_304_cannot_invent_or_restore_listing(monkeypatch, collector_factory, invalid):
    import httpx
    from sqlalchemy import func, select
    from realtoruch import worker
    from realtoruch.models import CollectionFetchState, Listing, Observation, SourceListing

    replies = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        status, body = replies.pop(0)
        if status == 304:
            assert "If-None-Match" not in request.headers
        return httpx.Response(status, content=body, headers={"ETag": ETAG})

    _, attempts, _ = fake_collector(monkeypatch, collector_factory, handler)
    if invalid != "unknown":
        replies.append((200, detail_page()))
        worker.collect()
        with collector_factory.begin() as db:
            source = db.scalar(select(SourceListing))
            if invalid == "mismatched_url":
                source.data = {**source.data, "url": DETAIL_URL + "-different"}
            elif invalid == "missing":
                source.data = None
            elif invalid == "deleted":
                for obs in db.scalars(select(Observation)):
                    db.delete(obs)
                db.flush()
                db.delete(db.scalar(select(CollectionFetchState)))
                db.delete(source)
            elif invalid == "inactive":
                source.status = "inactive"
                source.data = {**source.data, "status": "inactive"}
        if invalid == "drift":
            replies.append((200, b"<html>No listing schema</html>"))
            with pytest.raises(worker.CollectionFailed):
                worker.collect()
            # Clear ordinary failure backoff to exercise a subsequent fixture response.
            from realtoruch.models import SourcePollState
            with collector_factory.begin() as db:
                db.get(SourcePollState, "otodom").retry_after = None
                assert db.scalar(select(CollectionFetchState)) is None

    with collector_factory() as db:
        initial_homes = db.scalar(select(func.count()).select_from(Listing))
        initial_observation = db.scalar(select(SourceListing.observed_at))
    attempts.clear()
    replies.extend(((304, b""), (304, b"")))
    with pytest.raises(worker.CollectionFailed) as error:
        worker.collect()
    report = error.value.reports[0]
    assert report["network_attempts"] == len(attempts) == 3
    assert report["conditional_attempts"] == report["reused_304"] == report["ingested"] == 0
    assert report["responses_304"] == 2 and report["retry_attempts"] == 1 and report["errors"][0]["http_status"] == 304
    with collector_factory() as db:
        assert db.scalar(select(func.count()).select_from(Listing)) == initial_homes
        assert db.scalar(select(SourceListing.observed_at)) == initial_observation


def test_t04_mismatched_304_retries_unconditionally_within_the_same_budget(monkeypatch, collector_factory):
    import httpx
    from sqlalchemy import select
    from realtoruch import worker
    from realtoruch.models import SourceListing

    statuses = iter([200, 304, 200])

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        status = next(statuses)
        if status == 304:
            assert request.headers["If-None-Match"] == ETAG
            return httpx.Response(304, headers={"ETag": '"fixture-v2"'})
        assert "If-None-Match" not in request.headers
        return httpx.Response(200, content=detail_page(rent=3200), headers={"ETag": ETAG})

    fake_collector(monkeypatch, collector_factory, handler)
    worker.collect()
    report = worker.collect()[0]
    assert report["network_attempts"] == 3 and report["conditional_attempts"] == report["retry_attempts"] == 1
    assert report["responses_304"] == 1 and report["reused_304"] == 0
    with collector_factory() as db:
        assert db.scalar(select(SourceListing)).data["rent_pln"] == 3200


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("retry_after", ["37", "Tue, 02 Jan 2024 08:00:38 GMT"])
def test_t04_retry_after_survives_restart(monkeypatch, collector_factory, status, retry_after):
    from datetime import datetime, timedelta

    import httpx
    from realtoruch import worker
    from realtoruch.models import SourcePollState

    replies = iter([httpx.Response(status, headers={"Retry-After": retry_after}),
                    httpx.Response(200, json=[])])

    clock, attempts, _ = fake_collector(monkeypatch, collector_factory, lambda _: next(replies),
                                        config={"mode": "feed", "feed_url": DETAIL_URL})
    with pytest.raises(worker.CollectionFailed) as error:
        worker.collect()
    deadline = datetime(2024, 1, 2, 8, 0, 38)
    assert error.value.reports[0]["retry_after"] == deadline.isoformat() + "Z"
    assert error.value.reports[0]["network_attempts"] == 1 and clock.elapsed == 1
    with collector_factory() as db:
        assert db.get(SourcePollState, "otodom").retry_after == deadline
    clock.sleep((deadline - clock.now() - timedelta(seconds=1)).total_seconds())
    assert worker.collect()[0]["reason"] == "backoff"
    assert len(attempts) == 1
    clock.sleep(1)
    assert worker.collect()[0]["status"] == "succeeded"
    assert attempts[1][0] >= deadline


@pytest.mark.parametrize("failure, attempts_expected", [(403, 1), ("timeout", 2), (502, 2)])
def test_t04_attempt_limits_include_robots_and_keep_provider_pacing(monkeypatch, collector_factory,
                                                                   failure, attempts_expected):
    import httpx
    from realtoruch import worker

    robots = ROBOTS + b"Crawl-delay: 7\nRequest-rate: 1/11\n"

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=robots)
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(failure)

    _, attempts, _ = fake_collector(monkeypatch, collector_factory, handler)
    with pytest.raises(worker.CollectionFailed) as error:
        worker.collect()
    report = error.value.reports[0]
    assert report["network_attempts"] == len(attempts) == attempts_expected + 1
    assert report["robots_attempts"] == 1 and report["retry_attempts"] == attempts_expected - 1
    assert report["ingested"] == 0 and report["body_bytes"] == len(robots)
    gaps = [(right[0] - left[0]).total_seconds() for left, right in zip(attempts, attempts[1:])]
    assert gaps == ([11, 11.125] if attempts_expected == 2 else [11])


def test_t04_robots_delay_survives_new_city_and_new_collector(monkeypatch, collector_factory):
    import httpx
    from realtoruch import worker

    def handler(request):
        assert request.url.path == "/robots.txt"
        return httpx.Response(200, content=b"User-agent: *\nDisallow: /\nCrawl-delay: 31\n")

    clock, attempts, source = fake_collector(monkeypatch, collector_factory, handler)
    with pytest.raises(worker.CollectionFailed):
        worker.collect()
    # Simulate a resumed/new process past the independent error backoff. Only
    # the persisted robots pacing deadline remains; no detail was requested.
    from realtoruch.models import SourcePollState
    with collector_factory.begin() as db:
        state = db.get(SourcePollState, "otodom")
        assert (state.next_allowed_request - clock.now()).total_seconds() == 31
        state.retry_after = None
    source["city"] = "Warszawa"
    with pytest.raises(worker.CollectionFailed):
        worker.collect()
    assert (attempts[1][0] - attempts[0][0]).total_seconds() == 31


@pytest.mark.parametrize("mode", ["redirect", "oversize"])
def test_t04_redirect_and_oversize_do_not_persist_partial_or_forward_auth(monkeypatch, collector_factory, mode):
    import httpx
    from sqlalchemy import func, select
    from realtoruch import worker
    from realtoruch.models import CollectionFetchState, Listing

    class LargePage(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * 5_000_000
            yield b"x"
            pytest.fail("Reader must stop at the 5 MB cap")

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        if mode == "redirect":
            assert request.headers["authorization"] == "Bearer fixture-secret"
            return httpx.Response(302, headers={"Location": "https://untrusted.example/"})
        assert "authorization" not in request.headers
        return httpx.Response(200, stream=LargePage(), headers={"ETag": ETAG})

    monkeypatch.setenv("SYNTHETIC_FEED_TOKEN", "fixture-secret")
    config = ({"mode": "feed", "feed_url": DETAIL_URL, "token_env": "SYNTHETIC_FEED_TOKEN"}
              if mode == "redirect" else {})
    _, attempts, _ = fake_collector(monkeypatch, collector_factory, handler, config=config)
    with pytest.raises(worker.CollectionFailed) as error:
        worker.collect()
    report = error.value.reports[0]
    assert report["network_attempts"] == len(attempts) == (1 if mode == "redirect" else 2)
    assert report["body_bytes"] == (0 if mode == "redirect" else len(ROBOTS) + 5_000_001)
    assert {attempt.url.host for _, attempt in attempts} == {"www.otodom.pl"}
    assert "fixture-secret" not in json.dumps(report)
    with collector_factory() as db:
        assert db.scalar(select(func.count()).select_from(CollectionFetchState)) == 0
        assert db.scalar(select(func.count()).select_from(Listing)) == 0


def test_t04_legacy_sql_fetch_is_unconditional_and_public_listing_has_no_private_fields(
    monkeypatch, collector_factory, record, client,
):
    import httpx
    from sqlalchemy import select
    from realtoruch import worker
    from realtoruch.ingest import ingest
    from realtoruch.models import CollectionFetchState, SourceListing

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        assert "If-None-Match" not in request.headers and "If-Modified-Since" not in request.headers
        return httpx.Response(200, content=detail_page(), headers={
            "ETag": ETAG, "Last-Modified": LAST_MODIFIED,
        })

    clock, _, _ = fake_collector(monkeypatch, collector_factory, handler)
    with collector_factory.begin() as db:
        listing = ingest(db, record.model_copy(update={
            "observed_at": clock.now(), "external_id": "detail-one", "city": "Kraków",
        }))["listing_id"]
        assert db.scalar(select(CollectionFetchState)) is None
    report = worker.collect()[0]
    assert report["ingested"] == 1 and report["conditional_attempts"] == 0
    with collector_factory() as db:
        assert db.scalar(select(CollectionFetchState)).validators["etag"] == ETAG
        assert db.scalar(select(SourceListing)).listing_id == listing
    result = client.get(f"/v1/listings/{listing}")
    assert result.status_code == 200
    response = result.text.lower()
    for value in ("_fetch", "etag", "last-modified", "last_modified", "phone_hash", "700100101",
                  "fixture-v1", "validated_at", "authorization"):
        assert value not in response


def test_t04_portal_recheck_preserves_crosspost_price_and_advances_search_revision(monkeypatch, collector_factory):
    from datetime import timedelta

    import httpx
    from sqlalchemy import func, select
    from test_portals import DETAIL, fixture
    from realtoruch import worker
    from realtoruch.ingest import ingest
    from realtoruch.models import AlertEvent, Listing, Observation, SearchRevision, SourceListing
    from realtoruch.schemas import RawListing

    url = DETAIL["otodom"]
    detail_hits = 0

    def handler(request):
        nonlocal detail_hits
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        detail_hits += 1
        assert str(request.url) == url
        if detail_hits == 1:
            page = fixture("otodom").replace('"number": null', '"number": "12/3"')
            return httpx.Response(200, text=page, headers={"ETag": ETAG})
        assert request.headers["If-None-Match"] == ETAG
        return httpx.Response(304)

    clock, _, _ = fake_collector(monkeypatch, collector_factory, handler, config={
        "mode": "portal", "city": "Warszawa", "listing_urls": [url], "max_rechecks": 5,
    })
    worker.collect()
    clock.sleep(30)
    with collector_factory.begin() as db:
        source = db.scalar(select(SourceListing))
        other = RawListing.model_validate({
            **source.data, "source": "olx", "external_id": "crosspost",
            "url": "https://www.olx.pl/example", "rent_pln": 4600, "observed_at": clock.now(),
        })
        listing_id = source.listing_id
        assert ingest(db, other)["listing_id"] == listing_id
        assert db.get(Listing, listing_id).rent_pln == 4600
        revision = db.get(SearchRevision, listing_id).revision
        alerts = db.scalar(select(func.count()).select_from(AlertEvent))

    clock.sleep(timedelta(minutes=10).total_seconds())
    assert worker.collect()[0]["reused_304"] == 1
    with collector_factory() as db:
        listing = db.get(Listing, listing_id)
        source = db.scalar(select(SourceListing).where(SourceListing.source == "otodom"))
        assert listing.rent_pln == 4600
        assert listing.last_seen == source.observed_at > other.observed_at
        assert db.get(SearchRevision, listing_id).revision == revision + 1
        assert db.scalar(select(func.count()).select_from(AlertEvent)) == alerts
        assert db.scalar(select(func.count()).select_from(Observation)) == 2


def test_t04_unsafe_validators_do_not_enter_cache(monkeypatch, collector_factory):
    import httpx
    from sqlalchemy import select
    from realtoruch import worker
    from realtoruch.models import CollectionFetchState

    replies = iter([
        {"ETag": '"700 100 101"', "Last-Modified": "invalid date"},
        {"ETag": '"' + "x" * 256 + '"'},
        {"ETag": ETAG, "Vary": "Authorization"},
        {"ETag": ETAG, "Cache-Control": "no-store"},
        {"ETag": '"700100101"', "Last-Modified": LAST_MODIFIED},
    ])

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        assert "If-None-Match" not in request.headers
        return httpx.Response(200, content=detail_page(), headers=next(replies))

    fake_collector(monkeypatch, collector_factory, handler)
    for _ in range(4):
        worker.collect()
        with collector_factory() as db:
            assert db.scalar(select(CollectionFetchState)) is None
    worker.collect()
    with collector_factory() as db:
        validators = db.scalar(select(CollectionFetchState)).validators
        assert validators["etag"] is None and validators["last_modified"] == LAST_MODIFIED


def test_t04_sqlite_upgrade_keeps_legacy_poll_state_and_can_repeat(collector_factory):
    import hashlib
    import inspect

    from sqlalchemy import text
    from realtoruch.migrations import _baseline_local, upgrade_local
    from realtoruch.models import SourcePollState

    with collector_factory.begin() as db:
        db.add(SourcePollState(source="otodom", lease_id="old-lease", failures=7))
    engine = collector_factory.kw["bind"]
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE collection_fetch_state"))
        connection.execute(text("ALTER TABLE source_poll_state DROP COLUMN next_allowed_request"))
        connection.execute(text(
            "CREATE TABLE realtoruch_local_migrations (database_name VARCHAR(20) NOT NULL, "
            "version VARCHAR(3) NOT NULL, checksum VARCHAR(64) NOT NULL, PRIMARY KEY (database_name, version))"
        ))
        baseline = hashlib.sha256(inspect.getsource(_baseline_local).encode()).hexdigest()
        connection.execute(text(
            "INSERT INTO realtoruch_local_migrations VALUES ('rentals', '001', :checksum)"
        ), {"checksum": baseline})
    upgrade_local(engine)
    upgrade_local(engine)
    with collector_factory() as db:
        state = db.get(SourcePollState, "otodom")
        assert (state.lease_id, state.failures, state.next_allowed_request) == ("old-lease", 7, None)
        assert db.execute(text("SELECT COUNT(*) FROM collection_fetch_state")).scalar_one() == 0
        assert db.execute(text(
            "SELECT checksum FROM realtoruch_local_migrations WHERE database_name='rentals' AND version='001'"
        )).scalar_one() == baseline


@pytest.mark.parametrize("first", [304, "timeout"])
def test_t04_orphan_and_timeout_share_one_retry_budget(monkeypatch, collector_factory, first):
    import httpx
    from realtoruch import worker

    outcomes = iter([first, "timeout" if first == 304 else 304])

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=ROBOTS)
        outcome = next(outcomes)
        if outcome == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(outcome)

    _, attempts, _ = fake_collector(monkeypatch, collector_factory, handler)
    with pytest.raises(worker.CollectionFailed) as error:
        worker.collect()
    assert len(attempts) == error.value.reports[0]["network_attempts"] == 3
    assert error.value.reports[0]["retry_attempts"] == 1
    assert error.value.reports[0]["responses_304"] == 1
    assert error.value.reports[0]["ingested"] == 0
