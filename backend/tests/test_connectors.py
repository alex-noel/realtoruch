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
