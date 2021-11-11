"""Pure parsers for public portal HTML. No JavaScript or hidden API execution."""

import base64
import binascii
import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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


class ParseError(ValueError):
    """Unexpected source structure; must not become an inactive observation."""


class NotRental(ParseError):
    pass


class ListingUnavailable(ParseError):
    """Explicit source evidence that a known advert is no longer active."""


@dataclass
class Discovery:
    urls: list[str]
    next_url: str | None = None


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def listing_url(source: str, url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in PORTAL_HOSTS[source]:
        return False
    return bool(
        re.search(
            {
                "olx": r"^/d/oferta/[^/]+-CID\d+-ID[a-zA-Z0-9]+\.html$",
                "otodom": r"^/pl/oferta/[^/]+-ID[a-zA-Z0-9]+$",
                "gratka": r"^/nieruchomosci/[^/]+/ob/\d+$",
                "morizon": r"^/oferta/[^/]+-mzn\d+$",
            }[source],
            parsed.path.rstrip("/"),
        )
    )


def json_script(soup, selector):
    node = soup.select_one(selector)
    if node is None:
        raise ParseError("Expected embedded listing state is missing")
    try:
        return json.loads(node.get_text())
    except (ValueError, RecursionError) as exc:
        raise ParseError("Embedded listing state is invalid") from exc


def schema_nodes(soup):
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(node.get_text())
        except ValueError:
            continue
        if isinstance(value, dict):
            yield from value.get("@graph", [value])
        elif isinstance(value, list):
            yield from value


def discover(source: str, html: str, url: str) -> Discovery:
    soup = BeautifulSoup(html, "html.parser")
    if source == "otodom":
        props = json_script(soup, "#__NEXT_DATA__")["props"]["pageProps"]
        if props.get("transaction") != "RENT":
            raise NotRental("Search is not a rental search")
        search = props["data"]["searchAds"]
        urls = [
            urljoin(url, "/pl/oferta/" + item["slug"])
            for item in search["items"]
            if item.get("transaction") == "RENT" and item.get("estate") in PROPERTY_TYPES
        ]
        pagination = search["pagination"]
        current = int(pagination["currentPage"])
        requested = int(dict(parse_qsl(urlparse(url).query)).get("page", "1"))
        if current != requested:
            raise ParseError("Search returned a different page than requested")
        next_url = None
        if current < int(pagination["totalPages"]):
            parsed = urlparse(url)
            query = dict(parse_qsl(parsed.query))
            query["page"] = str(current + 1)
            next_url = urlunparse(parsed._replace(query=urlencode(query), fragment=""))
    elif source == "olx":
        if "/wynajem/" not in urlparse(url).path:
            raise NotRental("Search is not a rental search")
        urls = [urljoin(url, a["href"]) for a in soup.select("a[href]")]
        urls = [value for value in urls if listing_url(source, value)]
        if not urls:
            raise ParseError("Expected rendered OLX listing links are missing")
        next_link = next((a for a in soup.select("a[href]") if a.get_text(" ", strip=True) == "Dalej"), None)
        next_url = urljoin(url, next_link["href"]) if next_link else None
        if next_url and (urlparse(next_url).netloc, urlparse(next_url).path) != (
            urlparse(url).netloc,
            urlparse(url).path,
        ):
            raise ParseError("Pagination leaves the configured search")
    elif source in ("gratka", "morizon"):
        aggregate = next(
            (
                n.get("offers", {})
                for n in schema_nodes(soup)
                if isinstance(n, dict)
                and isinstance(n.get("offers"), dict)
                and n["offers"].get("@type") == "AggregateOffer"
            ),
            None,
        )
        if aggregate is None:
            raise ParseError("Expected rental search schema is missing")
        if not str(aggregate.get("businessFunction", "")).endswith("#LeaseOut"):
            raise NotRental("Search does not identify rental offers")
        urls = [item["url"] for item in aggregate.get("offers", []) if item.get("url")]
        next_link = soup.select_one('a[rel="next"], a[aria-label="Następna strona"]')
        if next_link is None:
            next_link = next(
                (a for a in soup.select("a[href]") if a.get_text(" ", strip=True) == "Następna strona"), None
            )
        next_url = urljoin(url, next_link["href"]) if next_link else None
        if next_url:
            current, following = urlparse(url), urlparse(next_url)
            if (following.netloc, following.path) != (current.netloc, current.path):
                raise ParseError("Pagination leaves the configured search")
    else:
        raise ParseError("No verified portal parser for this source")
    return Discovery(list(dict.fromkeys(canonical_url(u) for u in urls if listing_url(source, u))), next_url)


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


def money(value, currency="PLN"):
    if currency != "PLN":
        raise ParseError("Only explicit PLN prices are supported")
    try:
        number = Decimal(str(value).replace("\xa0", "").replace(" ", "").replace(",", "."))
        if not number.is_finite():
            raise InvalidOperation
        return int(number.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ParseError("Invalid monetary amount") from exc


def public_phone(values):
    # Only complete numbers already present in the fetched public page; no reveal calls.
    for value in values or []:
        if isinstance(value, str) and re.fullmatch(r"\+?[\d\s().-]+", value):
            digits = re.sub(r"\D", "", value)
            if len(digits) == 9 or (len(digits) == 11 and digits.startswith("48")):
                return value
    return None


def optional_fee(fields, key):
    entry = fields.get(key)
    if not entry or entry.get("value") in (None, ""):
        return None
    return money(entry["value"], entry.get("currency"))


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
            r"(\d[\d\s.,]*?)\s*(?:PLN|zł)\b"
        )
        amounts = {money(match[1]) for match in re.finditer(pattern, text, re.IGNORECASE)}
        result[field] = amounts.pop() if len(amounts) == 1 else None
    return result


def parse_otodom(soup, url):
    ad = json_script(soup, "#__NEXT_DATA__")["props"]["pageProps"]["ad"]
    if canonical_url(ad["url"]) != canonical_url(url):
        raise ParseError("Detail identity does not match requested URL")
    if ad.get("status") in ("inactive", "expired", "removed") or ad.get("shouldShowExpiredAdPage") is True:
        raise ListingUnavailable("Source explicitly marks this listing unavailable")
    if ad.get("status") != "active":
        raise ParseError("Unrecognized advert status")
    category = ad["adCategory"]
    if category.get("type") != "RENT" or category.get("name") not in PROPERTY_TYPES:
        raise NotRental("Unsupported transaction or property type")
    fields = {entry["key"]: entry for entry in ad["characteristics"]}
    attributes = ad.get("attributes") or {}
    location = ad["location"]
    places = {p["locationLevel"]: p["name"] for p in location["reverseGeocoding"]["locations"]}
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
    return dict(
        external_id=str(ad["id"]),
        title=ad["title"],
        description=ad.get("description", "")[:20000],
        city=places["city_or_village"],
        district=places.get("district", ""),
        region=places.get("voivodeship", ""),
        address=" ".join(str(s) for s in (street.get("name"), street.get("number")) if s),
        lat=coords.get("latitude"),
        lon=coords.get("longitude"),
        area_m2=float(str(fields["m"]["value"]).replace(",", ".").replace(" ", "")),
        rooms=fields["rooms_num"]["value"],
        floor=floor,
        rent_pln=money(fields["price"]["value"], fields["price"].get("currency")),
        fees_pln=optional_fee(fields, "rent"),
        deposit_pln=optional_fee(fields, "deposit"),
        advertiser_type="private"
        if advertiser == "private"
        else "agency"
        if advertiser == "business"
        else "unknown",
        property_type=PROPERTY_TYPES[category["name"]],
        amenities=sorted(set(amenities)),
        images=[image["large"] for image in ad.get("images", []) if image.get("large")][:30],
        phone=public_phone((ad.get("contactDetails") or {}).get("phones")),
    )


def parse_morizon_gratka(soup, url, expected_city):
    ad = decode_nuxt_property(json_script(soup, "#__NUXT_DATA__"))
    if canonical_url(urljoin(url, ad["url"])) != canonical_url(url):
        raise ParseError("Detail identity does not match requested URL")
    if ad.get("status") in (404, 410) or ad.get("presentationType") == "ARCHIVED":
        raise ListingUnavailable("Source explicitly marks this listing unavailable")
    if ad.get("presentationType") != "ACTIVE" or ad.get("status") != 200:
        raise ParseError("Unrecognized advert status")
    kind = (ad.get("types") or {}).get("mainTypeRoot")
    if ad.get("transaction") != "RENT" or kind not in PROPERTY_TYPES:
        raise NotRental("Unsupported transaction or property type")
    location = ad["location"]
    if location.get("countryCode") != "PL":
        raise ParseError("Only Polish locations are supported")
    places = location["location"]
    # The hierarchy includes counties/communes outside cities. Require a verified scope,
    # rather than incorrectly assigning a county or neighborhood as the city.
    if not expected_city or expected_city not in places:
        raise ParseError("Listing does not match the configured city scope")
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

    def fee(label):
        value = str(details.get(label) or "").strip()
        found = re.fullmatch(r"([\d\s.,]+)\s*(?:zł|PLN)", value)
        return money(found[1]) if found else None

    return dict(
        external_id=str(ad["idOnFrontend"]),
        title=ad["title"],
        description=ad.get("description", "")[:20000],
        city=expected_city,
        region=places[0],
        district=places[city_index + 1] if len(places) > city_index + 1 else "",
        address=" ".join(str(s) for s in (location.get("street"), location.get("number")) if s),
        lat=coords.get("latitude"),
        lon=coords.get("longitude"),
        area_m2=float(str(ad["area"]).replace(",", ".").replace(" ", "").replace("\xa0", "")),
        rooms=ad["numberOfRoomsCount"],
        floor=ad.get("floor"),
        rent_pln=money(ad["price"]["amount"], ad["price"].get("currency")),
        fees_pln=fee("Czynsz"),
        deposit_pln=fee("Kaucja"),
        commission_pln=fee("Prowizja"),
        advertiser_type="agency" if agency else "private" if private else "unknown",
        property_type=PROPERTY_TYPES[kind],
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
    if source not in PORTAL_HOSTS or not listing_url(source, url):
        raise ParseError("Unsupported portal detail URL")
    soup = BeautifulSoup(html, "html.parser")
    try:
        data = (
            parse_olx(soup, city)
            if source == "olx"
            else parse_otodom(soup, url)
            if source == "otodom"
            else parse_morizon_gratka(soup, url, city)
        )
        for key, value in description_costs(data.get("description", "")).items():
            if data.get(key) is None:
                data[key] = value
        return RawListing(source=source, url=canonical_url(url), **data)
    except ParseError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, RecursionError) as exc:
        raise ParseError("Source fields failed validation") from exc


def parse_olx(soup, expected_city=""):
    """Parse public rendered HTML/JSON-LD, never private phone or hidden APIs."""
    from .normalization import fold

    product = next(
        (node for node in schema_nodes(soup) if isinstance(node, dict) and node.get("@type") == "Product"),
        None,
    )
    if not product or not isinstance(product.get("offers"), dict):
        raise ParseError("Expected OLX Product/Offer schema is missing")
    category = str(product.get("category", ""))
    if "/wynajem/" not in category:
        raise NotRental("OLX advert is not a rental")
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
        raise NotRental("Unsupported OLX rental category")
    offer = product["offers"]
    if str(offer.get("availability", "")).endswith(("OutOfStock", "Discontinued")):
        raise ListingUnavailable("OLX explicitly marks the advert unavailable")
    if not str(offer.get("availability", "")).endswith("InStock"):
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
        raise ParseError("OLX city cannot be confirmed from breadcrumbs")
    area = re.fullmatch(r"([\d\s.,]+)\s*m[²2]", values.get("Powierzchnia", ""))
    rooms = values.get("Liczba pokoi", "")
    if rooms == "Kawalerka":
        count = 1
    elif match := re.fullmatch(r"(\d+)\s+poko(?:je|i|j)", rooms):
        count = int(match[1])
    else:
        raise ParseError("OLX room count is not exact")
    if not area:
        raise ParseError("OLX area is missing")
    floor = values.get("Poziom", "")
    floor = 0 if floor.lower() == "parter" else int(floor) if re.fullmatch(r"-?\d+", floor) else None

    def fee(label):
        value = values.get(label, "")
        match = re.fullmatch(r"([\d\s.,]+)\s*(?:zł|PLN)", value)
        return money(match[1]) if match else None

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
        external_id=str(product["sku"]),
        title=product["name"],
        description=product.get("description", "")[:20000],
        city=places[1],
        region=places[0],
        district=places[2] if len(places) > 2 else "",
        address="",
        lat=lat,
        lon=lon,
        area_m2=float(area[1].replace(" ", "").replace("\xa0", "").replace(",", ".")),
        rooms=count,
        floor=floor,
        rent_pln=money(offer["price"], offer.get("priceCurrency")),
        fees_pln=fee("Czynsz (dodatkowo)"),
        deposit_pln=fee("Kaucja"),
        commission_pln=fee("Prowizja"),
        advertiser_type="agency" if agency else "private" if private else "unknown",
        property_type=kind,
        images=product.get("image", [])[:30],
        amenities=[
            tag
            for label, tag in (("Winda", "lift"), ("Umeblowane", "furnished"), ("Zwierzęta", "pets"))
            if values.get(label) == "Tak"
        ],
    )
