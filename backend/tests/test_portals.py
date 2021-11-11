import json
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from realtoruch import worker
from realtoruch.connectors import Connector, SourceAccessError
from realtoruch.ingest import ingest
from realtoruch.models import Listing, Observation, SourceListing
from realtoruch.portals import (
    ListingUnavailable,
    NotRental,
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
        assert raw.rent_pln == 5000 and raw.fees_pln is None and raw.phone == "700100101"
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
        and "700100101" not in serialized
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
