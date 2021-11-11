import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from realtoruch import collection_health, worker
from realtoruch.connectors import Connector, SourceAccessError
from realtoruch.ingest import ingest
from realtoruch.models import Listing, Observation, SourceListing
from realtoruch.portals import (
    ListingUnavailable,
    NotRental,
    ParseCode,
    ParseError,
    decode_nuxt_property,
    discover,
    parse_detail,
)

FIXTURES = Path(__file__).parent / "fixtures/portals"
SEARCH = {
    "otodom": "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/mazowieckie/warszawa/warszawa/warszawa",
    "gratka": "https://gratka.pl/nieruchomosci/mieszkania/warszawa/wynajem",
    "morizon": "https://www.morizon.pl/do-wynajecia/mieszkania/warszawa/",
}
DETAIL = {
    "otodom": "https://www.otodom.pl/pl/oferta/fixture-rental-IDabc123",
    "gratka": "https://gratka.pl/nieruchomosci/fixture-apartment/ob/900001",
    "morizon": "https://www.morizon.pl/oferta/wynajem-fixture-apartment-mzn900001",
}


def fixture(source, page="detail"):
    return (FIXTURES / f"{source}-{page}.html").read_text()


def configured(source="otodom", **overrides):
    return {
        "name": source,
        "mode": "portal",
        "enabled": True,
        "city": "Warszawa",
        "search_urls": [SEARCH[source]],
        "allowed_hosts": [httpx.URL(SEARCH[source]).host],
        "max_pages": 1,
        "max_listings": 3,
        "max_rechecks": 10,
        **overrides,
    }


def change_detail(source, **changes):
    soup = BeautifulSoup(fixture(source), "html.parser")
    node = soup.select_one('script[type="application/json"]')
    state = json.loads(node.get_text())
    if source == "otodom":
        state["props"]["pageProps"]["ad"].update(changes)
    else:
        ad = state[state[0]["propertyData"]]
        for key, value in changes.items():
            state[ad[key]] = value
    node.string = json.dumps(state)
    return str(soup)


@pytest.mark.parametrize("source", SEARCH)
def test_discovery_returns_only_source_listing_urls_and_bounded_next_page(source):
    page = discover(source, fixture(source, "search"), SEARCH[source])
    assert page.urls == [DETAIL[source]]
    assert page.next_url == SEARCH[source] + "?page=2"


@pytest.mark.parametrize("source", SEARCH)
def test_actual_portal_shapes_map_required_fields_without_inventing_fees(source):
    raw = parse_detail(source, fixture(source), DETAIL[source], city="Warszawa")
    assert raw.city == "Warszawa" and raw.rooms == 2 and raw.advertiser_type == "agency"
    assert not raw.is_demo and raw.status == "active" and raw.images
    assert raw.commission_pln is None
    if source == "otodom":
        assert (raw.rent_pln, raw.fees_pln, raw.deposit_pln) == (4500, 1150, 9000)
        assert raw.phone is None  # The source requires reveal; it wasn't in the document.
    else:
        assert raw.rent_pln == 5000 and raw.fees_pln is None and raw.phone == "000000000"
        assert raw.syndication_key == "morizon-gratka:100001"


@pytest.mark.parametrize("source", SEARCH)
def test_wrong_listing_identity_is_rejected(source):
    with pytest.raises(ParseError, match="identity"):
        parse_detail(source, fixture(source), DETAIL[source].replace("fixture", "different"), city="Warszawa")


@pytest.mark.parametrize("source", SEARCH)
def test_sale_and_archived_pages_are_distinguished(source):
    sale = change_detail(
        source,
        **(
            {"adCategory": {"name": "FLAT", "type": "SELL"}}
            if source == "otodom"
            else {"transaction": "SELL"}
        ),
    )
    with pytest.raises(NotRental):
        parse_detail(source, sale, DETAIL[source], city="Warszawa")
    inactive = change_detail(
        source, **({"status": "inactive"} if source == "otodom" else {"presentationType": "ARCHIVED"})
    )
    with pytest.raises(ListingUnavailable):
        parse_detail(source, inactive, DETAIL[source], city="Warszawa")


def test_city_scope_and_nuxt_reference_validation():
    with pytest.raises(ParseError, match="city scope"):
        parse_detail("gratka", fixture("gratka"), DETAIL["gratka"], city="Kraków")
    with pytest.raises(ParseError):
        decode_nuxt_property([{"propertyData": 1}, {"self": 1}])
    with pytest.raises(ParseError):
        decode_nuxt_property([{"propertyData": 9}])


def test_polish_decimal_comma_area_preserves_fractional_square_meters():
    html = change_detail("gratka", area="47,40")
    raw = parse_detail("gratka", html, DETAIL["gratka"], city="Warszawa")
    assert raw.area_m2 == 47.4


def test_cross_posted_gratka_and_morizon_merge_without_a_building_number(session, client):
    for source in ("gratka", "morizon"):
        ingest(session, parse_detail(source, fixture(source), DETAIL[source], city="Warszawa"))
    session.commit()
    assert len(session.scalars(select(Listing)).all()) == 1
    assert len(session.scalars(select(SourceListing)).all()) == 2
    result = client.get("/v1/listings").json()
    assert result["total"] == 1 and len(result["items"][0]["sources"]) == 2
    serialized = json.dumps(result)
    assert (
        "phone_hash" not in serialized
        and "000000000" not in serialized
        and "000 000 000" not in serialized
        and "syndication_key" not in serialized
    )
    assert not result["items"][0]["is_demo"]


def test_shared_contact_without_syndication_identity_does_not_merge(session):
    first = parse_detail("gratka", fixture("gratka"), DETAIL["gratka"], city="Warszawa")
    second = parse_detail("morizon", fixture("morizon"), DETAIL["morizon"], city="Warszawa")
    ingest(session, first)
    ingest(session, second.model_copy(update={"syndication_key": "morizon-gratka:100002"}))
    session.commit()
    assert len(session.scalars(select(Listing)).all()) == 2


def test_portal_worker_discovers_ingests_then_rechecks_missing_adverts(session, monkeypatch):
    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    monkeypatch.setattr(worker, "load_sources", lambda: [configured("gratka"), configured("morizon")])

    def fetch(connector, url, **kwargs):
        source = connector.config["name"]
        return 200, fixture(source, "search" if url == SEARCH[source] else "detail").encode()

    monkeypatch.setattr(Connector, "fetch", fetch)
    reports = worker.collect()
    assert [r["ingested"] for r in reports] == [1, 1]
    assert [r["status"] for r in reports] == ["succeeded", "succeeded"]
    monkeypatch.setattr(worker, "load_sources", lambda: [configured("morizon", search_urls=[])])
    monkeypatch.setattr(Connector, "fetch", lambda *a, **kw: (410, b""))
    reports = worker.collect()
    assert reports[0]["inactive"] == 1
    session.expire_all()
    assert session.scalar(select(Listing)).status == "active"  # Gratka still active.
    assert len(session.scalars(select(Observation)).all()) == 3
    monkeypatch.setattr(worker, "load_sources", lambda: [configured("gratka", search_urls=[])])
    worker.collect()
    session.expire_all()
    assert session.scalar(select(Listing)).status == "inactive"


def test_parser_failure_is_reported_and_does_not_hide_other_source_results(session, monkeypatch):
    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    monkeypatch.setattr(worker, "load_sources", lambda: [configured("otodom"), configured("gratka")])

    def fetch(connector, url, **kwargs):
        source = connector.config["name"]
        body = fixture(source, "search" if url == SEARCH[source] else "detail")
        if url == DETAIL["otodom"]:
            body = "<html>Unexpected markup</html>"
        return 200, body.encode()

    monkeypatch.setattr(Connector, "fetch", fetch)
    with pytest.raises(worker.CollectionFailed) as failure:
        worker.collect()
    assert [r["status"] for r in failure.value.reports] == ["failed", "succeeded"]
    assert session.scalar(select(Listing)).rent_pln == 5000


def test_access_denial_stops_source_and_preserves_previous_state(session, monkeypatch):
    raw = parse_detail("otodom", fixture("otodom"), DETAIL["otodom"])
    ingest(session, raw)
    session.commit()
    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    monkeypatch.setattr(worker, "load_sources", lambda: [configured()])
    calls = []

    def denied(connector, url, **kwargs):
        calls.append(url)
        raise SourceAccessError("throttled", 429)

    monkeypatch.setattr(Connector, "fetch", denied)
    with pytest.raises(worker.CollectionFailed) as failure:
        worker.collect()
    assert len(calls) == 1 and failure.value.reports[0]["errors"][0]["http_status"] == 429
    session.expire_all()
    assert session.scalar(select(Listing)).status == "active"
    assert len(session.scalars(select(Observation)).all()) == 1


def test_robots_wildcards_longest_allow_and_duplicate_groups(monkeypatch):
    connector = Connector(configured("gratka", requests_per_minute=60))
    called = []

    def handle(request):
        called.append(str(request.url))
        body = "User-agent: *\nDisallow: *page=*\nAllow: *page=2$\n\nUser-agent: *\nDisallow: /api\n"
        return httpx.Response(200, text=body if request.url.path == "/robots.txt" else "ok")

    connector.client.close()
    connector.client = httpx.Client(
        transport=httpx.MockTransport(handle), headers={"User-Agent": "Realtoruch/0.2"}
    )
    monkeypatch.setattr("realtoruch.connectors.validate_url", lambda *args: None)
    monkeypatch.setattr("realtoruch.connectors.time.sleep", lambda _: None)
    assert connector.fetch(SEARCH["gratka"] + "?page=2", page=True)[0] == 200
    with pytest.raises(SourceAccessError, match="robots"):
        connector.fetch(SEARCH["gratka"] + "?page=11", page=True)
    with pytest.raises(SourceAccessError, match="robots"):
        connector.fetch("https://gratka.pl/api", page=True)
    assert len(called) == 2
    connector.close()


def test_broken_page_does_not_starve_later_detail_and_enforces_limits(monkeypatch):
    connector = Connector(
        configured(
            "otodom",
            search_urls=[],
            max_listings=2,
            listing_urls=[
                DETAIL["otodom"].replace("fixture", "broken"),
                DETAIL["otodom"],
                DETAIL["otodom"].replace("fixture", "extra"),
            ],
        )
    )
    called = []

    def fetch(url, **kwargs):
        called.append(url)
        return 200, b"<html>bad</html>" if "broken" in url else fixture("otodom").encode()

    monkeypatch.setattr(connector, "fetch", fetch)
    assert len(list(connector.records())) == 1
    assert len(called) == 2 and len(connector.report["errors"]) == 1
    connector.close()


def test_price_change_is_observed_and_keeps_canonical_identity(session, monkeypatch):
    raw = parse_detail("gratka", fixture("gratka"), DETAIL["gratka"], city="Warszawa")
    first = ingest(session, raw)
    session.commit()
    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    monkeypatch.setattr(worker, "load_sources", lambda: [configured("gratka", search_urls=[])])
    soup = BeautifulSoup(fixture("gratka"), "html.parser")
    node = soup.select_one("#__NUXT_DATA__")
    data = json.loads(node.get_text())
    ad = data[data[0]["propertyData"]]
    data[data[ad["price"]]["amount"]] = "4800.00"
    node.string = json.dumps(data)
    monkeypatch.setattr(Connector, "fetch", lambda *args, **kwargs: (200, str(soup).encode()))
    worker.collect()
    session.expire_all()
    listing = session.scalar(select(Listing))
    assert listing.id == first["listing_id"] and listing.rent_pln == 4800
    assert len(session.scalars(select(Observation).where(Observation.changed.is_(True))).all()) == 2


def test_sources_api_reports_real_observations_without_sensitive_evidence(session, client):
    raw = parse_detail("gratka", fixture("gratka"), DETAIL["gratka"], city="Warszawa")
    ingest(session, raw)
    session.commit()
    response = client.get("/v1/sources")
    assert response.status_code == 200
    source = next(row for row in response.json()["sources"] if row["name"] == "gratka")
    assert source["stored_adverts"] == 1 and source["last_observed_at"]
    assert "phone" not in response.text


def test_crosspost_identity_cannot_override_conflicting_floor(session):
    first = parse_detail("gratka", fixture("gratka"), DETAIL["gratka"], city="Warszawa")
    second = parse_detail("morizon", fixture("morizon"), DETAIL["morizon"], city="Warszawa")
    ingest(session, first)
    ingest(session, second.model_copy(update={"floor": 8}))
    session.commit()
    assert len(session.scalars(select(Listing)).all()) == 2


def test_otodom_pagination_response_must_match_the_requested_page():
    with pytest.raises(ParseError, match="different page"):
        discover("otodom", fixture("otodom", "search"), SEARCH["otodom"] + "?page=2")


def test_only_explicit_unambiguous_description_costs_are_used():
    from realtoruch.portals import description_costs

    costs = description_costs(
        "<p>Opłaty administracyjne - 960 PLN</p><p>Administrative fees - 960 PLN</p>"
        "<p>Kaucja: 5 000 zł. Prowizja 50%. Czynsz najmu 3300 PLN.</p>"
    )
    assert costs == {"fees_pln": 960, "deposit_pln": 5000, "commission_pln": None}
    assert description_costs("Kaucja w wysokości miesięcznych opłat. Prowizja do negocjacji.") == {
        "fees_pln": None,
        "deposit_pln": None,
        "commission_pln": None,
    }
    assert (
        description_costs("Czynsz administracyjny: 900 PLN. Administrative fee: 1000 PLN.")["fees_pln"]
        is None
    )
    assert description_costs("Prowizja: 500 PLN – 600 PLN. Commission: 500 PLN.")["commission_pln"] is None
    assert description_costs("Prowizja: 0 PLN.")["commission_pln"] == 0


@pytest.mark.parametrize("explicit", [False, True])
def test_fresh_adverts_do_not_use_the_new_listing_budget(monkeypatch, explicit):
    from types import SimpleNamespace

    from realtoruch.models import now

    fresh = DETAIL["otodom"].replace("fixture", "fresh")
    config = configured(max_listings=1, recheck_interval_minutes=360)
    if explicit:
        config.update(search_urls=[], listing_urls=[fresh, DETAIL["otodom"]])
    connector = Connector(
        config, previous_lookup=lambda url: {"observed_at": now().isoformat()} if url == fresh else None
    )
    calls = []
    monkeypatch.setattr(
        "realtoruch.connectors.discover",
        lambda *args: SimpleNamespace(urls=[fresh, DETAIL["otodom"]], next_url=None),
    )

    def fetch(url, **kwargs):
        calls.append(url)
        return 200, fixture("otodom").encode()

    monkeypatch.setattr(connector, "fetch", fetch)
    try:
        assert len(list(connector.records())) == 1
        assert fresh not in calls
        assert connector.report["checked"] == 1 and connector.report["fresh_skipped"] == 1
    finally:
        connector.close()


def test_rechecks_are_scoped_to_city_and_freshness(session, record, monkeypatch):
    from datetime import timedelta

    from realtoruch.models import now

    ingest(session, record)
    ingest(session, record.model_copy(update={"city": "Kraków", "external_id": "krakow-old"}))
    ingest(
        session,
        record.model_copy(
            update={
                "city": "Kraków",
                "external_id": "krakow-new",
                "address": "Another 42",
                "observed_at": now() - timedelta(minutes=1),
            }
        ),
    )
    session.commit()
    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    _, due = worker.source_state(configured(city="Kraków", recheck_interval_minutes=360), False)
    assert [item["previous"]["external_id"] for item in due] == ["krakow-old"]


PORTAL_CASES = {
    "otodom": ("90000001", 4500, 1150, 9000, 35, "agency", "Warszawa", "Wola", 52.235523, 20.992165),
    "gratka": ("900001", 5000, None, None, 51, "agency", "Warszawa", "Śródmieście", 52.2167206, 21.0169635),
    "morizon": (
        "mzn900001",
        5000,
        None,
        None,
        51,
        "agency",
        "Warszawa",
        "Śródmieście",
        52.2167206,
        21.0169635,
    ),
    "olx": ("1234567890", 2550, 450, None, 53, "private", "Kraków", "Krowodrza", 50.07159, 19.91757),
}
PORTAL_SEARCH = {**SEARCH, "olx": "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/"}
PORTAL_DETAIL = {**DETAIL, "olx": "https://www.olx.pl/d/oferta/synthetic-rental-CID3-IDabc123.html"}
MISSING = object()


def detail_variant(source, changes):
    """Apply synthetic overrides to the provider's existing embedded shape."""
    soup = BeautifulSoup(fixture(source), "html.parser")
    selector = {
        "otodom": "#__NEXT_DATA__",
        "olx": 'script[type="application/ld+json"]',
        "gratka": "#__NUXT_DATA__",
        "morizon": "#__NUXT_DATA__",
    }[source]
    node = soup.select_one(selector)
    state = json.loads(node.get_text())
    for path, value in changes.items():
        if source == "otodom":
            fields = state["props"]["pageProps"]["ad"]
        elif source == "olx":
            fields = state
        else:
            fields = state[state[0]["propertyData"]]
        *parents, field = path.split(".")
        for parent in parents:
            fields = fields[int(parent) if isinstance(fields, list) else parent]
            if isinstance(state, list):
                fields = state[fields]
        if value is MISSING:
            fields.pop(int(field) if isinstance(fields, list) else field)
        elif isinstance(state, list):
            fields[field] = len(state)
            state.append(value)
        else:
            fields[field] = value
    node.string = json.dumps(state)
    return str(soup)


def rent_variant(source, amount, currency="PLN"):
    amount_path, currency_path = {
        "otodom": ("characteristics.0.value", "characteristics.0.currency"),
        "gratka": ("price.amount", "price.currency"),
        "morizon": ("price.amount", "price.currency"),
        "olx": ("offers.price", "offers.priceCurrency"),
    }[source]
    return detail_variant(source, {amount_path: amount, currency_path: currency})


def parse_fixture(source, html=None):
    return parse_detail(
        source,
        html if html is not None else fixture(source),
        PORTAL_DETAIL[source],
        city=PORTAL_CASES[source][6],
    )


@pytest.mark.parametrize("source", PORTAL_CASES)
def test_t05_tc01_active_contract_and_changed_rent(source):
    active = parse_fixture(source)
    assert (
        active.external_id,
        active.rent_pln,
        active.fees_pln,
        active.deposit_pln,
        active.area_m2,
        active.advertiser_type,
        active.city,
        active.district,
        active.lat,
        active.lon,
    ) == PORTAL_CASES[source]
    assert str(active.url) == PORTAL_DETAIL[source]
    assert (active.rooms, active.property_type, active.status, active.commission_pln) == (
        2,
        "apartment",
        "active",
        None,
    )
    changed = parse_fixture(source, rent_variant(source, "4200"))
    assert changed.rent_pln == 4200
    assert active.model_dump(exclude={"rent_pln", "observed_at"}) == changed.model_dump(
        exclude={"rent_pln", "observed_at"}
    )


@pytest.mark.parametrize("source", PORTAL_CASES)
def test_t05_tc02_catalog_empty_pagination_and_access_errors(source, monkeypatch):
    search = PORTAL_SEARCH[source]
    page = discover(source, fixture(source, "search"), search)
    assert page.urls == [PORTAL_DETAIL[source]] and page.next_url == search + "?page=2"

    connector = Connector({"enabled": True, "mode": "portal", "name": source, "search_urls": [search]})
    try:
        if source != "olx":
            empty = discover(source, fixture(source, "empty"), search)
            assert not empty.urls and empty.next_url is None
            monkeypatch.setattr(
                connector, "fetch", lambda *args, **kwargs: (200, fixture(source, "empty").encode())
            )
            assert list(connector.records()) == []
            assert connector.report["search_pages"] == 1 and connector.report["errors"] == []
    finally:
        connector.close()

    cases = [
        (fixture(source, "drift"), ParseCode.UNRECOGNIZED_PAGE),
        ((FIXTURES / "access-challenge.html").read_text(), ParseCode.ACCESS_CHALLENGE),
        ((FIXTURES / "consent-interstitial.html").read_text(), ParseCode.ACCESS_CHALLENGE),
    ]
    if source == "olx":
        cases.append((fixture(source, "empty"), ParseCode.UNRECOGNIZED_PAGE))
    for html, code in cases:
        connector = Connector({"enabled": True, "mode": "portal", "name": source, "search_urls": [search]})
        body = html.encode()
        monkeypatch.setattr(connector, "fetch", lambda *args, body=body, **kwargs: (200, body))
        try:
            with pytest.raises(ParseError) as failure:
                list(connector.records())
            assert failure.value.code is code
            assert connector.report["search_pages"] == connector.report["emitted"] == 0
            assert [(e["stage"], e["code"]) for e in connector.report["errors"]] == [
                ("discovery", code.value)
            ]
        finally:
            connector.close()


@pytest.mark.parametrize("source", PORTAL_CASES)
@pytest.mark.parametrize(
    "amount, expected", [("4\xa0999,49", 4999), ("4\u202f999,50", 5000), ("4 999,50", 5000)]
)
def test_t05_tc03_polish_amount_rounding(source, amount, expected):
    assert parse_fixture(source, rent_variant(source, amount)).rent_pln == expected


@pytest.mark.parametrize("source", PORTAL_CASES)
def test_t05_tc03_required_ranges_fail_and_ambiguous_fees_stay_unknown(source):
    with pytest.raises(ParseError) as error:
        parse_fixture(source, rent_variant(source, "4 000–5 000"))
    assert error.value.code is ParseCode.INVALID_AMOUNT

    if source == "otodom":
        html = detail_variant(
            source, {"characteristics.1.value": "500–600", "characteristics.3.value": "50,5"}
        )
    elif source == "olx":
        html = fixture(source).replace("450 zł", "500–600 zł").replace("53 m²", "50,5 m²")
    else:
        # No structured fee in these base captures; inject a range into the description.
        html = detail_variant(source, {"description": "Czynsz administracyjny: 500–600 zł.", "area": "50,5"})
    raw = parse_fixture(source, html)
    assert raw.area_m2 == 50.5 and raw.fees_pln is None and raw.commission_pln is None


@pytest.mark.parametrize("source", PORTAL_CASES)
@pytest.mark.parametrize("scenario", ["sale", "foreign_currency", "missing_rooms"])
def test_t05_tc04_ineligible_detail_does_not_enter_collector(source, scenario, monkeypatch):
    if scenario == "sale":
        transaction = {
            "otodom": {"adCategory.type": "SELL"},
            "olx": {"category": "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/"},
            "gratka": {"transaction": "SELL"},
            "morizon": {"transaction": "SELL"},
        }[source]
        html, code = detail_variant(source, transaction), ParseCode.NOT_RENTAL
    elif scenario == "foreign_currency":
        html, code = rent_variant(source, "4500", "EUR"), ParseCode.UNSUPPORTED_CURRENCY
    else:
        if source == "olx":
            html = fixture(source).replace("<p>Liczba pokoi: 2 pokoje</p>", "")
        else:
            path = "characteristics.7" if source == "otodom" else "numberOfRoomsCount"
            html = detail_variant(source, {path: MISSING})
        code = ParseCode.INVALID_FIELDS

    connector = Connector(
        {
            "enabled": True,
            "mode": "portal",
            "name": source,
            "city": PORTAL_CASES[source][6],
            "listing_urls": [PORTAL_DETAIL[source]],
        }
    )
    monkeypatch.setattr(connector, "fetch", lambda *args, **kwargs: (200, html.encode()))
    try:
        assert list(connector.records()) == []
        if scenario == "sale":
            assert connector.report["skipped"] == 1
            assert connector.report["skip_reasons"] == {code.value: 1}
            assert connector.report["errors"] == []
        else:
            assert [(e["stage"], e["code"]) for e in connector.report["errors"]] == [("detail", code.value)]
        assert connector.report["emitted"] == connector.report["inactive"] == 0
    finally:
        connector.close()


@pytest.mark.parametrize("source", PORTAL_CASES)
def test_t05_tc05_only_confirmed_removal_changes_observation(source, session, monkeypatch, caplog):
    url = PORTAL_DETAIL[source]
    city = PORTAL_CASES[source][6]
    removal = {
        "otodom": {"status": "inactive"},
        "gratka": {"presentationType": "ARCHIVED"},
        "morizon": {"status": 410},
        "olx": {"offers.availability": "https://schema.org/OutOfStock", "url": url},
    }[source]
    id_field = {"otodom": "id", "olx": "sku"}.get(source, "idOnFrontend")
    unavailable = detail_variant(source, removal)
    mismatch = detail_variant(source, {**removal, id_field: "SYNTHETIC_WRONG_LISTING"})
    missing_url = detail_variant(source, {**removal, "url": "#unavailable"})
    challenge = (FIXTURES / "access-challenge.html").read_text().replace("</body>", unavailable + "</body>")
    canary = "<html>SYNTHETIC_SESSION_TOKEN_000 000 000</html>"

    monkeypatch.setattr(worker, "Session", sessionmaker(session.bind, expire_on_commit=False))
    config = {"name": source, "enabled": True, "mode": "portal", "city": city, "listing_urls": [url]}
    monkeypatch.setattr(worker, "load_sources", lambda: [config])
    caplog.set_level("INFO", logger=worker.log.name)
    poll_time = datetime(2026, 1, 1)
    monkeypatch.setattr(collection_health, "now", lambda: poll_time)

    def stub_fetch(body, *, error=None):
        nonlocal poll_time
        poll_time += timedelta(days=1)  # Let the real persisted retry window expire.

        def fetch(*args, **kwargs):
            if error is not None:
                raise error
            return 200, body.encode()

        monkeypatch.setattr(Connector, "fetch", fetch)

    stub_fetch(unavailable)
    report = worker.collect()[0]
    assert report["skipped"] == 1 and report["emitted"] == report["inactive"] == 0
    assert session.scalar(select(SourceListing)) is None

    active = parse_fixture(source).model_copy(update={"observed_at": datetime(2026, 1, 1)})
    ingest(session, active)
    session.commit()
    for body, transport, kind, status, code in (
        ("", SourceAccessError("SYNTHETIC_AUTHORIZATION_CANARY", 403), "SourceAccessError", 403, None),
        ("", httpx.ReadTimeout("SYNTHETIC_TIMEOUT_CANARY"), "ReadTimeout", None, None),
        (canary, None, "ParseError", None, ParseCode.UNRECOGNIZED_PAGE),
        (mismatch, None, "ParseError", None, ParseCode.IDENTITY_MISMATCH),
        (missing_url, None, "ParseError", None, ParseCode.IDENTITY_MISMATCH),
        (challenge, None, "ParseError", None, ParseCode.ACCESS_CHALLENGE),
    ):
        stub_fetch(body, error=transport)
        with pytest.raises(worker.CollectionFailed) as failure:
            worker.collect()
        report = failure.value.reports[0]
        assert report["emitted"] == report["ingested"] == report["inactive"] == 0
        (error,) = report["errors"]
        assert (error["kind"], error["stage"], error["http_status"], error.get("code")) == (
            kind,
            "detail",
            status,
            code.value if code else None,
        )
        session.expire_all()
        stored = session.scalar(select(SourceListing))
        assert (stored.status, stored.observed_at) == ("active", active.observed_at)
        assert session.scalar(select(Listing)).status == "active"
        assert [row.status for row in session.scalars(select(Observation))] == ["active"]

    stub_fetch(unavailable)
    report = worker.collect()[0]
    assert report["inactive"] == report["ingested"] == 1
    session.expire_all()
    stored = session.scalar(select(SourceListing))
    assert stored.status == "inactive" and stored.observed_at > active.observed_at
    assert session.scalar(select(Listing)).status == "inactive"
    assert [row.status for row in session.scalars(select(Observation).order_by(Observation.observed_at))] == [
        "active",
        "inactive",
    ]
    assert "collection_report" in caplog.text
    for secret in ("SYNTHETIC_", "000 000 000", "000000000", url):
        assert secret not in caplog.text


def test_t05_tc06_reduced_fixtures_contain_only_non_dialable_contact_canaries():
    contact = re.compile(r"(?<!\d)(?:\+?48[ .-]?)?(?:\d[ .-]?){8}\d(?!\d)")
    credentials = re.compile(
        r"(?:authorization|set-cookie|cookie)\s*:|bearer\s+[a-z0-9]|"
        r'["\'](?:session(?:id|_id|_token)?|access_token|refresh_token|csrf_token)["\']\s*:',
        re.IGNORECASE,
    )

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for field in value.values():
                yield from strings(field)
        elif isinstance(value, list):
            for field in value:
                yield from strings(field)

    for path in FIXTURES.glob("*.html"):
        markup = path.read_text()
        assert len(markup.encode()) < 4096 and not credentials.search(markup), path.name
        soup = BeautifulSoup(markup, "html.parser")
        values = []
        for node in soup.select("script"):
            assert node.get("src") is None, path.name
            values.extend(strings(json.loads(node.get_text())))
            node.decompose()
        for value in [str(soup), *values]:
            assert all(re.sub(r"\D", "", match[0]) == "000000000" for match in contact.finditer(value)), (
                path.name
            )
