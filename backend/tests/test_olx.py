from pathlib import Path

import pytest

from realtoruch.portals import ListingUnavailable, NotRental, ParseError, discover, parse_detail

FIXTURES = Path(__file__).parent / "fixtures/portals"
URL = "https://www.olx.pl/d/oferta/synthetic-rental-CID3-IDabc123.html"


def test_olx_public_html_parser_and_pagination():
    detail = (FIXTURES / "olx-detail.html").read_text()
    raw = parse_detail("olx", detail, URL, city="Kraków")
    assert raw.rent_pln == 2550 and raw.fees_pln == 450
    assert raw.area_m2 == 53 and raw.rooms == 2 and raw.floor == 1
    assert raw.city == "Kraków" and raw.district == "Krowodrza"
    assert raw.advertiser_type == "private" and raw.phone is None
    assert raw.commission_pln is None and raw.address == ""
    assert raw.lat == 50.07159 and raw.lon == 19.91757
    discovery = discover(
        "olx",
        (FIXTURES / "olx-search.html").read_text(),
        "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/",
    )
    assert discovery.urls == [URL]
    assert discovery.next_url.endswith("?page=2")


@pytest.mark.parametrize(
    "old,new,error",
    [
        ("/wynajem/", "/sprzedaz/", NotRental),
        ("InStock", "OutOfStock", ListingUnavailable),
        ("InStock", "PreOrder", ParseError),
        ("2 pokoje", "4 i więcej", ParseError),
        ('"PLN"', '"EUR"', ParseError),
        ("ad-parameters-container", "unknown-markup", ParseError),
    ],
)
def test_olx_fails_closed_for_unverified_fields(old, new, error):
    with pytest.raises(error):
        parse_detail("olx", (FIXTURES / "olx-detail.html").read_text().replace(old, new), URL, city="Kraków")


def test_olx_never_guesses_a_city_or_empty_search():
    with pytest.raises(ParseError):
        parse_detail("olx", (FIXTURES / "olx-detail.html").read_text(), URL, city="Warszawa")
    with pytest.raises(ParseError):
        discover(
            "olx", "<html>Loading…</html>", "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/"
        )
