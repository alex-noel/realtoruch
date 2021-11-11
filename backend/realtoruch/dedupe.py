import math
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .normalization import fold


def address_key(value):
    value = fold(value)
    value = re.sub(r"^(?:ulica|ul\.)\s*", "", value)
    value = re.sub(r"^(?:aleja|aleje|al\.)\s+", "al ", value)
    value = re.sub(r"^(?:plac|pl\.)\s+", "pl ", value)
    value = re.sub(r"\s+(?:m\.?|lok\.?)\s*(\d+\w?)$", r"/\1", value)
    value = re.sub(r"\s*/\s*", "/", value)
    return " ".join(value.replace(",", " ").split())


def image_key(value):
    # Ignore presentation parameters only. Keep host/path and identity/signature
    # parameters; an arbitrary URL query may identify an entirely different photo.
    parts = urlsplit(str(value))
    resize = {"w", "width", "h", "height", "q", "quality", "fit", "crop", "format", "auto"}
    query = urlencode(sorted((key, val) for key, val in parse_qsl(parts.query) if key.lower() not in resize))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def distance_m(a, b):
    if None in (a.lat, a.lon, b.get("lat"), b.get("lon")):
        return None
    lat1, lat2 = math.radians(a.lat), math.radians(b["lat"])
    delta_lat, delta_lon = lat2 - lat1, math.radians(b["lon"] - a.lon)
    h = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def matching_property(candidate, data, sources):
    """Conservative identity: a phone alone is never evidence of the same home."""
    if candidate.is_demo != data["is_demo"] or fold(candidate.city) != fold(data["city"]):
        return None
    if candidate.rooms != data["rooms"] or candidate.property_type != data["property_type"]:
        return None
    if abs(candidate.area_m2 - data["area_m2"]) > max(0.5, candidate.area_m2 * 0.015):
        return None
    if candidate.floor is not None and data["floor"] is not None and candidate.floor != data["floor"]:
        return None
    address = address_key(data["address"])
    candidate_address = address_key(candidate.address)
    same_address = bool(re.search(r"\d", address)) and candidate_address == address
    # A building number by itself is not an apartment identity.
    same_unit = same_address and bool(re.search(r"\d+[a-z]?/\d+[a-z]?$", address))
    distance = distance_m(candidate, data)
    same_phone = bool(data.get("phone_hash")) and any(s.phone_hash == data["phone_hash"] for s in sources)
    images = {image_key(image) for source in sources for image in source.data.get("images", [])}
    same_image = bool(images.intersection(image_key(image) for image in data["images"]))
    if (
        data["source"] in ("gratka", "morizon")
        and data.get("syndication_key")
        and address
        and candidate_address == address
        and (distance is None or distance <= 100)
        and any(
            s.source in ("gratka", "morizon")
            and s.source != data["source"]
            and s.data.get("syndication_key") == data["syndication_key"]
            for s in sources
        )
    ):
        return "Shared Morizon–Gratka listing identity, street, area and rooms"
    # Missing floors are uncertainty, not corroboration. Require both contact
    # and photo with the same known floor, building and nearby coordinates for
    # reposts without a unit number. A street alone is still too broad.
    # Even this remains heuristic, not proof of identity.
    if (same_address and candidate.floor is not None
        and data["floor"] is not None and same_phone and same_image
        and distance is not None and distance <= 50):
        return "Same address, known floor, contact, photo and nearby location"
    if not same_unit or (distance is not None and distance > 100):
        return None
    if same_phone or same_image:
        return "Same unit address, area, rooms and " + (
            "contact fingerprint" if same_phone else "image URL"
        )
    return None
