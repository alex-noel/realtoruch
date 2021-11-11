"""Pure parsers for public portal HTML. No JavaScript or hidden API execution."""

import base64
import binascii
import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from .schemas import RawListing

PORTAL_HOSTS = {
    "olx": {"www.olx.pl", "olx.pl"},
    "otodom": {"www.otodom.pl", "otodom.pl"},
    "gratka": {"gratka.pl", "www.gratka.pl"},
    "morizon": {"www.morizon.pl", "morizon.pl"},
}
PROPERTY_TYPES = {"FLAT": "apartment", "HOUSE": "house", "ROOM": "room"}


class ParseCode(str, Enum):
    UNSUPPORTED_URL = "unsupported_url"
    UNRECOGNIZED_PAGE = "unrecognized_page"
    ACCESS_CHALLENGE = "access_challenge"
    INVALID_PAGINATION = "invalid_pagination"
    INVALID_FIELDS = "invalid_fields"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    INVALID_AMOUNT = "invalid_amount"
    IDENTITY_MISMATCH = "identity_mismatch"
    INVALID_LOCATION = "invalid_location"
    NOT_RENTAL = "not_rental"
    LISTING_UNAVAILABLE = "listing_unavailable"


class ParseError(ValueError):
    """A bounded diagnostic whose message never includes source content."""

    def __init__(self, message, *, code=ParseCode.UNRECOGNIZED_PAGE):
        super().__init__(message)
        self.code = code


class NotRental(ParseError):
    def __init__(self, message):
        super().__init__(message, code=ParseCode.NOT_RENTAL)


class ListingUnavailable(ParseError):
    """Explicit source evidence that a known advert is no longer active."""

    def __init__(self, message, *, external_id=None):
        super().__init__(message, code=ParseCode.LISTING_UNAVAILABLE)
        self.external_id = external_id


@dataclass
class Discovery:
    urls: list[str]
    next_url: str | None = None


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def portal_url(source: str, url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in PORTAL_HOSTS.get(source, ())
        and not parsed.username
        and not parsed.password
        and parsed.port in (None, 443)
    )


def listing_url(source: str, url: str) -> bool:
    if not portal_url(source, url):
        return False
    return bool(
        re.search(
            {
                "olx": r"^/d/oferta/[^/]+-CID\d+-ID[a-zA-Z0-9]+\.html$",
                "otodom": r"^/pl/oferta/[^/]+-ID[a-zA-Z0-9]+$",
                "gratka": r"^/nieruchomosci/[^/]+/ob/\d+$",
                "morizon": r"^/oferta/[^/]+-mzn\d+$",
            }[source],
            urlparse(url).path.rstrip("/"),
        )
    )


def json_script(soup, selector):
    node = soup.select_one(selector)
    if node is None:
        raise ParseError("Expected embedded listing state is missing")
    try:
        return json.loads(node.get_text())
    except (ValueError, RecursionError):
        raise ParseError("Embedded listing state is invalid") from None


def schema_nodes(soup):
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(node.get_text())
        except (ValueError, RecursionError):
            continue
        if isinstance(value, dict):
            graph = value.get("@graph", [value])
            if isinstance(graph, list):
                yield from graph
        elif isinstance(value, list):
            yield from value


def check_access_page(soup):
    # Detect page-level interstitials even when they contain stale embedded listing data.
    title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
    if title in {
        "access denied",
        "attention required!",
        "attention required! | cloudflare",
        "just a moment...",
        "just a moment…",
        "verify you are human",
        "consent required",
    } or soup.select_one(
        '#challenge-form, #cf-challenge-running, form[action^="/cdn-cgi/challenge-platform/"]'
    ):
        raise ParseError("Source returned an access or consent interstitial", code=ParseCode.ACCESS_CHALLENGE)


def check_rental(transaction):
    if transaction in ("SELL", "SALE"):
        raise NotRental("Unsupported transaction or property type")
    if transaction != "RENT":
        raise ParseError("Unrecognized rental transaction")


def property_type(estate):
    if estate not in PROPERTY_TYPES:
        raise ParseError("Unrecognized rental property type")
    return PROPERTY_TYPES[estate]


def exact_integer(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ParseError("Expected an exact integer field", code=ParseCode.INVALID_FIELDS)


def next_search_url(soup, url, *, label, selector=None):
    link = soup.select_one(selector) if selector else None
    if link is None:
        link = next((a for a in soup.select("a[href]") if a.get_text(" ", strip=True) == label), None)
    if link is None:
        return None
    try:
        next_url = urljoin(url, link["href"])
        current, following = urlparse(url), urlparse(next_url)
        if (following.scheme, following.netloc, following.path) == (
            current.scheme,
            current.netloc,
            current.path,
        ) and following.query != current.query:
            return urlunparse(following._replace(fragment=""))
    except (KeyError, TypeError, ValueError):
        pass
    raise ParseError(
        "Pagination leaves the configured search or repeats the page", code=ParseCode.INVALID_PAGINATION
    )


def discover_otodom(soup, url):
    props = json_script(soup, "#__NEXT_DATA__")["props"]["pageProps"]
    check_rental(props["transaction"])
    search = props["data"]["searchAds"]
    items = search["items"]
    if not isinstance(items, list):
        raise ParseError("Search items are not a list")
    urls = []
    for item in items:
        try:
            check_rental(item["transaction"])
        except NotRental:
            continue
        property_type(item["estate"])
        slug = item["slug"]
        if not isinstance(slug, str) or not re.fullmatch(r"[^/?#]+-ID[a-zA-Z0-9]+", slug):
            raise ParseError("Rental result is missing its listing slug")
        urls.append(urljoin(url, "/pl/oferta/" + slug))
    try:
        pagination = search["pagination"]
        current = exact_integer(pagination["currentPage"])
        total = exact_integer(pagination["totalPages"])
        requested = exact_integer(dict(parse_qsl(urlparse(url).query)).get("page", "1"))
    except (KeyError, TypeError, ValueError):
        raise ParseError("Search pagination is invalid", code=ParseCode.INVALID_PAGINATION) from None
    if current != requested:
        raise ParseError("Search returned a different page than requested", code=ParseCode.INVALID_PAGINATION)
    if current < 1 or total < 0 or (items and total < current) or (not items and current < total):
        raise ParseError("Search items and pagination disagree", code=ParseCode.INVALID_PAGINATION)
    if current >= total:
        return urls, None
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query["page"] = str(current + 1)
    return urls, urlunparse(parsed._replace(query=urlencode(query), fragment=""))


def discover_olx(soup, url):
    if "/wynajem/" not in urlparse(url).path:
        raise NotRental("Search is not a rental search")
    urls = []
    for link in soup.select("a[href]"):
        value = urljoin(url, link["href"])
        parsed = urlparse(value)
        if parsed.hostname not in PORTAL_HOSTS["olx"] or not parsed.path.startswith("/d/oferta/"):
            continue
        if not listing_url("olx", value):
            raise ParseError("Unrecognized rendered OLX listing link")
        urls.append(value)
    if not urls:
        raise ParseError("Expected rendered OLX listing links are missing")
    return urls, next_search_url(soup, url, label="Dalej")


def discover_aggregate(source, soup, url):
    aggregate = next(
        (
            n["offers"]
            for n in schema_nodes(soup)
            if isinstance(n, dict)
            and isinstance(n.get("offers"), dict)
            and n["offers"].get("@type") == "AggregateOffer"
        ),
        None,
    )
    if aggregate is None:
        raise ParseError("Expected rental search schema is missing")
    function = aggregate.get("businessFunction")
    if function in ("https://purl.org/goodrelations/v1#Sell", "http://purl.org/goodrelations/v1#Sell"):
        raise NotRental("Search is not a rental search")
    if function not in (
        "https://purl.org/goodrelations/v1#LeaseOut",
        "http://purl.org/goodrelations/v1#LeaseOut",
    ):
        raise ParseError("Search does not identify rental offers")
    offers = aggregate["offers"]
    if not isinstance(offers, list):
        raise ParseError("Search offers are not a list")
    urls = []
    for item in offers:
        link = item["url"]
        if not isinstance(link, str) or not link.strip():
            raise ParseError("Search offer is missing its listing URL")
        value = urljoin(url, link)
        parsed = urlparse(value)
        if parsed.hostname not in PORTAL_HOSTS[source]:
            continue
        # Gratka can mix this alternate route into rental results. Its detail
        # and identity contract is unsupported, so never queue it for fetching.
        if (
            source == "gratka"
            and re.fullmatch(r"/nieruchomosci/[^/]+/oi/[0-9]+", parsed.path.rstrip("/"))
            and portal_url(source, value)
        ):
            continue
        if not listing_url(source, value):
            raise ParseError("Unrecognized rental result URL")
        urls.append(value)
    if offers and not urls:
        raise ParseError("Search offers contain no recognized listing URLs")
    next_url = next_search_url(
        soup, url, label="Następna strona", selector='a[rel="next"], a[aria-label="Następna strona"]'
    )
    if not offers and (next_url or aggregate.get("offerCount") not in (None, 0, "0")):
        raise ParseError("Empty search offers conflict with advertised results")
    return urls, next_url


def discover(source: str, html: str, url: str) -> Discovery:
    try:
        if not portal_url(source, url):
            raise ParseError("Unsupported portal search URL", code=ParseCode.UNSUPPORTED_URL)
        soup = BeautifulSoup(html, "html.parser")
        check_access_page(soup)
        if source == "otodom":
            urls, next_url = discover_otodom(soup, url)
        elif source == "olx":
            urls, next_url = discover_olx(soup, url)
        else:
            urls, next_url = discover_aggregate(source, soup, url)
        return Discovery(list(dict.fromkeys(canonical_url(value) for value in urls)), next_url)
    except ParseError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, RecursionError):
        raise ParseError("Source search fields failed validation") from None


def decode_nuxt_property(flat):
    """Read Nuxt's devalue reference table, limited to the property's data subtree."""
    if not isinstance(flat, list) or len(flat) > 100000:
        raise ParseError("Invalid Nuxt data table")
    refs = list(
        dict.fromkeys(
            value["propertyData"] for value in flat if isinstance(value, dict) and "propertyData" in value
        )
    )
    if len(refs) != 1:
        raise ParseError("Expected exactly one property payload")
    cache, visiting = {}, set()

    def decode(index, depth=0):
        if not isinstance(index, int) or isinstance(index, bool) or index >= len(flat) or depth > 80:
            raise ParseError("Invalid Nuxt reference")
        if index in (-1, -2):
            return None
        if index < 0 or index in visiting:
            raise ParseError("Unsupported or circular Nuxt reference")
        if index in cache:
            return cache[index]
        visiting.add(index)
        value = flat[index]
        if isinstance(value, dict):
            result = {key: decode(ref, depth + 1) for key, ref in value.items()}
        elif isinstance(value, list):
            if value and isinstance(value[0], str):
                if value[0] not in ("Reactive", "ShallowReactive", "Ref", "ShallowRef") or len(value) != 2:
                    raise ParseError("Unsupported Nuxt wrapper")
                result = decode(value[1], depth + 1)
            else:
                result = [decode(ref, depth + 1) for ref in value]
        else:
            result = value
        visiting.remove(index)
        cache[index] = result
        return result

    return decode(refs[0])


AMOUNT = r"(?:[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+)(?:[.,][0-9]+)?"
AMOUNT_SPACES = str.maketrans("", "", " \u00a0\u202f")


def decimal_amount(value):
    text = str(value).strip()
    if not re.fullmatch(AMOUNT, text):
        raise ParseError("Invalid numeric amount", code=ParseCode.INVALID_AMOUNT)
    return Decimal(text.translate(AMOUNT_SPACES).replace(",", "."))


def money(value, currency="PLN"):
    if currency != "PLN":
        raise ParseError("Only explicit PLN prices are supported", code=ParseCode.UNSUPPORTED_CURRENCY)
    try:
        return int(decimal_amount(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        raise ParseError("Invalid monetary amount", code=ParseCode.INVALID_AMOUNT) from None


def listing_id(value):
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and 0 < len(value) <= 200 and value.strip() == value:
        return value
    raise ParseError("Listing identity is missing", code=ParseCode.INVALID_FIELDS)


def public_phone(values):
    # Only complete numbers already present in the fetched public page; no reveal calls.
    for value in values or []:
        if isinstance(value, str) and re.fullmatch(r"\+?[\d\s().-]+", value):
            digits = re.sub(r"\D", "", value)
            if len(digits) == 9 or (len(digits) == 11 and digits.startswith("48")):
                return value
    return None


def optional_fee(value, currency="PLN"):
    try:
        return money(value, currency)
    except ParseError:
        return None


def labelled_fees(fields, labels):
    result = {}
    for label, key in labels.items():
        value = fields.get(label)
        if value is None or value == "":
            continue
        match = re.fullmatch(rf"({AMOUNT})\s*(?:zł|PLN)", str(value).strip(), re.IGNORECASE)
        result[key] = optional_fee(match[1]) if match else None
    return result


def description_costs(description):
    """Accept only clearly labelled currency amounts; conflicting amounts stay unknown."""
    text = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)
    labels = {
        "fees_pln": r"czynsz\s+administracyjny|opłaty\s+administracyjne|administrative\s+fees?",
        "deposit_pln": r"kaucja(?:\s+zwrotna)?|deposit",
        "commission_pln": r"prowizja|commission",
    }
    result = {}
    for field, label in labels.items():
        pattern = (
            rf"\b(?:{label})\s*(?:wynosi|w wysokości)?\s*[:=–-]?\s*"
            rf"({AMOUNT})(?:(?:\s*(?:PLN|zł)\b)?"
            rf"(?P<range>\s*(?:[-–—]|\bdo\b)\s*{AMOUNT}))?\s*(?:PLN|zł)\b"
        )
        amounts = {
            None if match["range"] else optional_fee(match[1])
            for match in re.finditer(pattern, text, re.IGNORECASE)
        }
        result[field] = amounts.pop() if len(amounts) == 1 else None
    return result


def check_detail_identity(identity, url):
    if (
        not isinstance(identity, str)
        or not urlparse(identity).path
        or canonical_url(urljoin(url, identity)) != canonical_url(url)
    ):
        raise ParseError("Detail identity does not match requested URL", code=ParseCode.IDENTITY_MISMATCH)


def parse_otodom(soup, url, expected_city):
    from .normalization import fold

    ad = json_script(soup, "#__NEXT_DATA__")["props"]["pageProps"]["ad"]
    check_detail_identity(ad.get("url"), url)
    external_id = listing_id(ad["id"])
    if ad.get("status") in ("inactive", "expired", "removed") or ad.get("shouldShowExpiredAdPage") is True:
        raise ListingUnavailable("Source explicitly marks this listing unavailable", external_id=external_id)
    if ad.get("status") != "active":
        raise ParseError("Unrecognized advert status")
    category = ad["adCategory"]
    check_rental(category.get("type"))
    kind = property_type(category.get("name"))
    fields = {entry["key"]: entry for entry in ad["characteristics"]}
    attributes = ad.get("attributes") or {}
    location = ad["location"]
    places = {p["locationLevel"]: p["name"] for p in location["reverseGeocoding"]["locations"]}
    city = places.get("city_or_village")
    if not isinstance(city, str) or not city.strip() or (expected_city and fold(city) != fold(expected_city)):
        raise ParseError("Listing does not match the configured city scope", code=ParseCode.INVALID_LOCATION)
    street = (location.get("address") or {}).get("street") or {}
    coords = location.get("coordinates") or {}
    floor = fields.get("floor_no", {}).get("value")
    floor = (
        0
        if floor == "ground_floor"
        else int(floor[6:])
        if floor and re.fullmatch(r"floor_\d+", floor)
        else None
    )
    tags = set(attributes.get("extras_types") or []) | set(attributes.get("equipment_types") or [])
    amenities = [
        public
        for key, public in {
            "balcony": "balcony",
            "lift": "lift",
            "elevator": "lift",
            "parking": "parking",
            "garage": "parking",
            "furniture": "furnished",
            "dishwasher": "dishwasher",
        }.items()
        if key in tags
    ]
    advertiser = ad.get("advertiserType")
    fees = {}
    for label, key in (("rent", "fees_pln"), ("deposit", "deposit_pln")):
        entry = fields.get(label, {})
        if entry.get("value") not in (None, ""):
            fees[key] = optional_fee(entry["value"], entry.get("currency"))
    return dict(
        external_id=external_id,
        title=ad["title"],
        description=ad.get("description", "")[:20000],
        city=city,
        district=places.get("district", ""),
        region=places.get("voivodeship", ""),
        address=" ".join(str(s) for s in (street.get("name"), street.get("number")) if s),
        lat=coords.get("latitude"),
        lon=coords.get("longitude"),
        area_m2=decimal_amount(fields["m"]["value"]),
        rooms=exact_integer(fields["rooms_num"]["value"]),
        floor=floor,
        rent_pln=money(fields["price"]["value"], fields["price"].get("currency")),
        **fees,
        advertiser_type="private"
        if advertiser == "private"
        else "agency"
        if advertiser == "business"
        else "unknown",
        property_type=kind,
        amenities=sorted(set(amenities)),
        images=[image["large"] for image in ad.get("images", []) if image.get("large")][:30],
        phone=public_phone((ad.get("contactDetails") or {}).get("phones")),
    )


def parse_morizon_gratka(soup, url, expected_city):
    ad = decode_nuxt_property(json_script(soup, "#__NUXT_DATA__"))
    check_detail_identity(ad.get("url"), url)
    external_id = listing_id(ad["idOnFrontend"])
    if ad.get("status") in (404, 410) or ad.get("presentationType") == "ARCHIVED":
        raise ListingUnavailable("Source explicitly marks this listing unavailable", external_id=external_id)
    if ad.get("presentationType") != "ACTIVE" or ad.get("status") != 200:
        raise ParseError("Unrecognized advert status")
    check_rental(ad.get("transaction"))
    kind = property_type((ad.get("types") or {}).get("mainTypeRoot"))
    location = ad["location"]
    if location.get("countryCode") != "PL":
        raise ParseError("Only Polish locations are supported", code=ParseCode.INVALID_LOCATION)
    places = location["location"]
    # The hierarchy includes counties/communes outside cities. Require a verified scope,
    # rather than incorrectly assigning a county or neighborhood as the city.
    if not expected_city or not isinstance(places, list) or expected_city not in places:
        raise ParseError("Listing does not match the configured city scope", code=ParseCode.INVALID_LOCATION)
    city_index = places.index(expected_city)
    coords = (location.get("map") or {}).get("center") or {}
    contact = ad.get("contact") or {}
    company, person = contact.get("company") or {}, contact.get("person") or {}
    agency = company.get("type") == "AGENCY" or person.get("type") == "AGENT"
    private = person.get("type") in ("PRIVATE", "OWNER") and not agency
    photo_ids = {p["id"] for p in ad.get("photos", []) if p.get("id")}
    images = []
    for img in soup.select("img[src]"):
        src = img["src"]
        if src.startswith("https://") and any("/thumb/" + key + "/" in src for key in photo_ids):
            images.append(src)
    for node in schema_nodes(soup):
        if isinstance(node, dict) and node.get("@type") == "Offer" and isinstance(node.get("image"), str):
            images.insert(0, node["image"])
    for photo in ad.get("photos", []):
        try:
            original = base64.b64decode(photo["id"], validate=True).decode("utf-8")
        except (ValueError, KeyError, UnicodeError, binascii.Error):
            continue
        if original.startswith("https://"):
            images.append(original)
    # Choose one rendered URL per photo; all URLs come from source markup.
    unique_images, used = [], set()
    for src in images:
        identity = next(
            (key for key in photo_ids if "/thumb/" + key + "/" in src),
            base64.b64encode(src.encode()).decode(),
        )
        if identity not in used:
            used.add(identity)
            unique_images.append(src)
    tags = {
        v.get("icon")
        for key in ("facilities", "equipments")
        for v in (ad.get(key) or [])
        if isinstance(v, dict)
    }
    details = {entry["label"]: entry.get("value") for entry in ad.get("detailedInformation", [])}

    return dict(
        external_id=external_id,
        title=ad["title"],
        description=ad.get("description", "")[:20000],
        city=expected_city,
        region=places[0],
        district=places[city_index + 1] if len(places) > city_index + 1 else "",
        address=" ".join(str(s) for s in (location.get("street"), location.get("number")) if s),
        lat=coords.get("latitude"),
        lon=coords.get("longitude"),
        area_m2=decimal_amount(ad["area"]),
        rooms=exact_integer(ad["numberOfRoomsCount"]),
        floor=ad.get("floor"),
        rent_pln=money(ad["price"]["amount"], ad["price"].get("currency")),
        **labelled_fees(
            details, {"Czynsz": "fees_pln", "Kaucja": "deposit_pln", "Prowizja": "commission_pln"}
        ),
        advertiser_type="agency" if agency else "private" if private else "unknown",
        property_type=kind,
        images=unique_images[:30],
        amenities=sorted(
            {
                public
                for key, public in {
                    "elevator": "lift",
                    "balcony": "balcony",
                    "parking": "parking",
                    "dishwasher": "dishwasher",
                    "furniture": "furnished",
                }.items()
                if key in tags
            }
        ),
        phone=public_phone(person.get("phones")) or public_phone(company.get("phones")),
        syndication_key=f"morizon-gratka:{ad['id']}",
    )


def parse_detail(source: str, html: str, url: str, *, city: str = "") -> RawListing:
    try:
        if not listing_url(source, url):
            raise ParseError("Unsupported portal detail URL", code=ParseCode.UNSUPPORTED_URL)
        soup = BeautifulSoup(html, "html.parser")
        check_access_page(soup)
        data = (
            parse_olx(soup, url, city)
            if source == "olx"
            else parse_otodom(soup, url, city)
            if source == "otodom"
            else parse_morizon_gratka(soup, url, city)
        )
        if not isinstance(data["title"], str) or not data["title"].strip():
            raise ParseError("Listing title is missing", code=ParseCode.INVALID_FIELDS)
        for key, value in description_costs(data.get("description", "")).items():
            data.setdefault(key, value)
        return RawListing(source=source, url=canonical_url(url), **data)
    except ParseError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, RecursionError):
        raise ParseError("Source fields failed validation", code=ParseCode.INVALID_FIELDS) from None


def parse_olx(soup, url, expected_city=""):
    """Parse public rendered HTML/JSON-LD, never private phone or hidden APIs."""
    from .normalization import fold

    product = next(
        (node for node in schema_nodes(soup) if isinstance(node, dict) and node.get("@type") == "Product"),
        None,
    )
    if not product or not isinstance(product.get("offers"), dict):
        raise ParseError("Expected OLX Product/Offer schema is missing")
    category = product.get("category")
    if not isinstance(category, str):
        raise ParseError("OLX rental category is missing")
    if "/sprzedaz/" in category:
        raise NotRental("OLX advert is not a rental")
    if "/wynajem/" not in category:
        raise ParseError("OLX rental category is not recognized")
    kind = (
        "apartment"
        if "/mieszkania/" in category
        else "house"
        if "/domy/" in category
        else "room"
        if "/stancje-pokoje/" in category
        else None
    )
    if not kind:
        raise ParseError("Unsupported OLX rental category")
    offer = product["offers"]
    external_id = listing_id(product["sku"])
    availability = offer.get("availability")
    if isinstance(availability, str):
        availability = availability.removeprefix("https://schema.org/").removeprefix("http://schema.org/")
    identity = product.get("url")
    unavailable = availability in ("OutOfStock", "Discontinued")
    if identity is not None or unavailable:
        check_detail_identity(identity, url)
    if unavailable:
        raise ListingUnavailable("OLX explicitly marks the advert unavailable", external_id=external_id)
    if availability != "InStock":
        raise ParseError("OLX availability is not confirmed")
    parameters = soup.select_one('[data-testid="ad-parameters-container"]')
    if not parameters:
        raise ParseError("Rendered OLX property parameters are missing")
    values = {}
    for node in parameters.select("p"):
        label, _, value = node.get_text(" ", strip=True).partition(":")
        values[label.strip()] = value.strip()
    places = [
        a.get_text(" ", strip=True).removeprefix("Wynajem - ")
        for a in soup.select("nav a[href]")
        if a.get_text(" ", strip=True).startswith("Wynajem - ")
    ]
    if len(places) < 2 or (expected_city and fold(places[1]) != fold(expected_city)):
        raise ParseError("OLX city cannot be confirmed from breadcrumbs", code=ParseCode.INVALID_LOCATION)
    area = re.fullmatch(r"([\d\s.,]+)\s*m[²2]", values.get("Powierzchnia", ""))
    rooms = values.get("Liczba pokoi", "")
    if rooms == "Kawalerka":
        count = 1
    elif match := re.fullmatch(r"(\d+)\s+poko(?:je|i|j)", rooms):
        count = int(match[1])
    else:
        raise ParseError("OLX room count is not exact", code=ParseCode.INVALID_FIELDS)
    if not area:
        raise ParseError("OLX area is missing", code=ParseCode.INVALID_FIELDS)
    floor = values.get("Poziom", "")
    floor = 0 if floor.lower() == "parter" else int(floor) if re.fullmatch(r"-?\d+", floor) else None

    lat, lon = None, None
    link = soup.select_one('a[href^="https://maps.google.com/maps?"]')
    if link:
        coordinates = dict(parse_qsl(urlparse(link["href"]).query)).get("ll", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", coordinates):
            lat, lon = map(float, coordinates.split(","))
    trader = soup.select_one('[data-testid="trader-title"]')
    identity = fold(trader.get_text(" ", strip=True)) if trader else ""
    private = "Prywatne" in values or "osoba prywatna" in identity
    agency = "Firmowe" in values or "firma" in identity
    return dict(
        external_id=external_id,
        title=product["name"],
        description=product.get("description", "")[:20000],
        city=places[1],
        region=places[0],
        district=places[2] if len(places) > 2 else "",
        address="",
        lat=lat,
        lon=lon,
        area_m2=decimal_amount(area[1]),
        rooms=count,
        floor=floor,
        rent_pln=money(offer["price"], offer.get("priceCurrency")),
        **labelled_fees(
            values, {"Czynsz (dodatkowo)": "fees_pln", "Kaucja": "deposit_pln", "Prowizja": "commission_pln"}
        ),
        advertiser_type="agency" if agency else "private" if private else "unknown",
        property_type=kind,
        images=product.get("image", [])[:30],
        amenities=[
            tag
            for label, tag in (("Winda", "lift"), ("Umeblowane", "furnished"), ("Zwierzęta", "pets"))
            if values.get(label) == "Tak"
        ],
    )
